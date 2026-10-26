/* Experimental Vulkan 1.0 backend for xSDK/vulkan4xenon.
 * PSX textures remain packed bytes; only decoded color is filtered. A presented
 * frame runs on the GPU while the next is recorded into the other frame slot;
 * uploads, readbacks and storage reuse drain the queue first.
 */
#include <vulkan/vulkan.h>
#include <vulkan4xenon.h>
#include <platform/native_renderer.h>
#include <platform/native_log.h>
#include <platform/native_config.h>
#include <platform/native_precise.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stddef.h>
#include "ctr_shaders.h"

enum { XV_WIDTH=1280,XV_HEIGHT=720,XV_VERTEX_BYTES=16*1024*1024,XV_UNIFORM_BYTES=2*1024*1024,
       XV_VERTEX_SLOT_BYTES=XV_VERTEX_BYTES/2,XV_UNIFORM_SLOT_BYTES=XV_UNIFORM_BYTES/2 };
typedef struct { VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;size_t size; } XvBuffer;
typedef struct {
    VkImage image;VkDeviceMemory memory;VkImageView view;
    VkImage depth;VkDeviceMemory depthMemory;VkImageView depthView;
    VkFramebuffer framebuffer;VkImageLayout layout;
    unsigned width,height,pass;int clearStencil;
} XvTarget;
typedef struct { float rect[4],scale[4],flags[4],source[4]; } XvUniform;
/* Vulkan formats describe fields by address. The pinned Vulkan layer applies
 * Xenos's per-word byte swap and the appropriate byte/halfword swizzles.
 * Do not substitute DWORD-packed formats for these byte arrays. */
/* GrVertex plus its triangle's texel range: U/V minimum, then the exclusive
 * maximum. PSX sampling never leaves that range; filtered taps keep to it. */
typedef struct { GrVertex v; u8 uvMin[2],uvMax[2]; } XvVertex;
typedef struct { float position[4]; } XvQuadVertex;
CTR_STATIC_ASSERT(sizeof(XvVertex) == 24);
CTR_STATIC_ASSERT(offsetof(XvVertex, v.u) == 8);
CTR_STATIC_ASSERT(offsetof(XvVertex, v.r) == 12);
CTR_STATIC_ASSERT(offsetof(XvVertex, v.tcx) == 16);
CTR_STATIC_ASSERT(offsetof(XvVertex, uvMin) == 20);
static struct {
    VkInstance instance;VkPhysicalDevice physical;VkDevice device;VkQueue queue;
    VkSurfaceKHR surface;VkSwapchainKHR swapchain;unsigned imageCount;
    XvTarget swap[3],main,off,vram;
    VkRenderPass passes[4];VkCommandPool pool;VkCommandBuffer command,commands[2];VkFence fence,fences[2],acquireFence;
    unsigned slot;int pending[2],stamped[2];VkQueryPool timestamps;float timestampPeriod;
    VkDescriptorSetLayout setLayout;VkPipelineLayout pipelineLayout;VkDescriptorPool descriptors;
    VkDescriptorSet sets[4];VkSampler sampler,linearSampler,vramSampler;
    VkShaderModule shaders[20];VkPipeline pipelines[3][18][5][3];
    XvBuffer vertices,uniforms,staging;
    unsigned vertexCursor,vertexBase,vertexCount,uniformCursor,uniformAlignment;
    const GrVertex *sourceVertices;
    XvTarget *target;int recording,inPass;
    XvUniform state;VkRect2D scissor;int clipEnabled,ui,offscreen,drawPrim;
    RECT16 offRect;BlendMode blend;TexFormat format;TextureID texture;
    int mainValid,mainResolved,vramCPUChanged,vramGPUChanged;
    u16 pixels[1024*512],move[1024*512];
} xv;
int g_windowWidth=1280,g_windowHeight=720;
static int xvEdgeAA=1;
/* Diagnostics for pixels no draw covers: [debug] reveal_holes clears the main
 * target and the game's background fills to magenta; Back+LB+RB captures the
 * next finished frame (before edge AA) and VRAM to the game folder. */
static int xvRevealHoles,xvCaptureRequested;
static unsigned xvCaptureCount;
static void XvColorCheck(void);
static struct {
    unsigned submits,uploads,reads,draws,passes,shaderDraws[7],quads[4];
    unsigned submitMS,waitMS,frameWaitMS,acquireMS,presentMS;
    unsigned blendDraws[5],uiDraws,feedbackRequests,midpointFeedbackSkips,skippedSTPPasses;
    unsigned gpuFrames,gpuTotalUS,gpuMaxUS,gpuOver16;
    unsigned trisRequested,trisDrawn,trisDropped,trisSkipped;
} xvCost;
int g_dbg_wireframeMode=0,g_dbg_texturelessMode=0,g_cfg_bilinearFiltering=1;
/* CPU palette summaries are valid only while no GPU write overlaps them.
 * Track 16-word blocks: framebuffer writes must not invalidate an unrelated
 * CLUT to their right on the same row. Unknown/mixed palettes keep both draws. */
static struct {
    unsigned generation;
    unsigned char gpuWritten[512*64];
    struct {unsigned generation,key,kind;} cache[64];
} xvPalette;
static void XvPaletteReset(void)
{
    memset(xvPalette.gpuWritten,0,sizeof(xvPalette.gpuWritten));
    if(++xvPalette.generation==0){memset(xvPalette.cache,0,sizeof(xvPalette.cache));xvPalette.generation=1;}
}
static void XvPaletteWritten(int x,int y,int w,int h)
{
    unsigned left=(unsigned)x/16,right=((unsigned)x+w+15)/16;
    for(int row=y;row<y+h;row++)memset(xvPalette.gpuWritten+row*64+left,1,right-left);
}
static unsigned XvPaletteKind(unsigned clut,unsigned format)
{
    unsigned x=(clut&63)*16,y=(clut>>6)&511,blocks=format==TF_4_BIT?1:16;
    for(unsigned i=0;i<blocks;i++)if(xvPalette.gpuWritten[y*64+((x/16+i)&63)])return 0;
    unsigned key=clut|(format<<15),slot=(clut^(clut>>6)^(format*17))&63;
    if(xvPalette.cache[slot].generation==xvPalette.generation && xvPalette.cache[slot].key==key)
        return xvPalette.cache[slot].kind;
    unsigned kind=0;
    for(unsigned i=0;i<blocks*16;i++){
        unsigned word=xv.pixels[y*1024+((x+i)&1023)];
        if(word)kind|=word&32768?2:1;
        if(kind==3)break;
    }
    xvPalette.cache[slot].generation=xvPalette.generation;xvPalette.cache[slot].key=key;xvPalette.cache[slot].kind=kind;
    return kind;
}
static int XvTexturePassNeeded(int first,int triangles)
{
    if(!xv.sourceVertices || xv.format>TF_8_BIT || xv.texture!=1 || g_dbg_texturelessMode ||
       (xv.state.flags[0]!=1 && xv.state.flags[0]!=2))return 1;
    unsigned clut=(u16)xv.sourceVertices[first].clut&32767;
    // DrawSplit keeps STP draws primitive-sized. Be conservative for any
    // caller that combines several CLUTs in one draw.
    for(int i=1;i<triangles*3;i++)if(((u16)xv.sourceVertices[first+i].clut&32767)!=clut)return 1;
    unsigned kind=XvPaletteKind(clut,xv.format);
    return !((xv.state.flags[0]==1 && kind==2) || (xv.state.flags[0]==2 && kind==1));
}
static void XvCheck(VkResult result,const char *operation)
{
    if(result!=VK_SUCCESS) { Platform_LogError("[vulkan] %s failed: %d\n",operation,(int)result);Platform_Exit(1); }
}
#define XV_CALL(call) XvCheck((call),#call)
/* GPU time of each presented frame: two top-of-pipe stamps per slot, at the
 * start of its last command buffer and after its final pass has resolved.
 * A frame split by a drain reports only its last command buffer. */
static void XvStampStart(void)
{
    if(!xv.timestamps)return;
    vkCmdResetQueryPool(xv.command,xv.timestamps,xv.slot*2,2);
    vkCmdWriteTimestamp(xv.command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,xv.timestamps,xv.slot*2);
}
static void XvStampEnd(void)
{
    if(!xv.timestamps)return;
    vkCmdWriteTimestamp(xv.command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,xv.timestamps,xv.slot*2+1);
    xv.stamped[xv.slot]=1;
}
static void XvStampRead(unsigned slot)
{
    uint64_t stamps[2];
    if(!xv.stamped[slot])return;
    xv.stamped[slot]=0;
    if(vkGetQueryPoolResults(xv.device,xv.timestamps,slot*2,2,sizeof(stamps),stamps,sizeof(stamps[0]),VK_QUERY_RESULT_64_BIT)!=VK_SUCCESS ||
       stamps[1]<stamps[0])return;
    unsigned us=(unsigned)((double)(stamps[1]-stamps[0])*xv.timestampPeriod/1000.0);
    xvCost.gpuFrames++;xvCost.gpuTotalUS+=us;if(us>xvCost.gpuMaxUS)xvCost.gpuMaxUS=us;xvCost.gpuOver16+=us>16667;
}
static void XvBufferCreate(XvBuffer *buffer,size_t bytes,VkBufferUsageFlags usage)
{
    VkBufferCreateInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=bytes,.usage=usage};
    XV_CALL(vkCreateBuffer(xv.device,&info,NULL,&buffer->buffer));
    VkMemoryRequirements requirements;vkGetBufferMemoryRequirements(xv.device,buffer->buffer,&requirements);
    /* Transfers are executed by the Vulkan layer on the CPU. Prefer its cached
     * host memory for staging; vertex/uniform storage must remain GPU-visible. */
    VkPhysicalDeviceMemoryProperties properties;vkGetPhysicalDeviceMemoryProperties(xv.physical,&properties);
    unsigned memoryType=0;
    if(!(usage & ~(VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT)))
        for(unsigned i=0;i<properties.memoryTypeCount;i++)
            if((requirements.memoryTypeBits & (1u<<i)) &&
               (properties.memoryTypes[i].propertyFlags & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_CACHED_BIT)) ==
               (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_CACHED_BIT)){memoryType=i;break;}
    VkMemoryAllocateInfo allocate={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=requirements.size,.memoryTypeIndex=memoryType};
    XV_CALL(vkAllocateMemory(xv.device,&allocate,NULL,&buffer->memory));
    XV_CALL(vkBindBufferMemory(xv.device,buffer->buffer,buffer->memory,0));
    XV_CALL(vkMapMemory(xv.device,buffer->memory,0,VK_WHOLE_SIZE,0,(void **)&buffer->map));buffer->size=bytes;
}
static void XvBegin(void)
{
    if(xv.recording)return;
    VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    XV_CALL(vkBeginCommandBuffer(xv.command,&begin));xv.recording=1;
    XvStampStart();
}
static void XvEndPass(void) { if(xv.inPass){vkCmdEndRenderPass(xv.command);xv.inPass=0;} }
/* Each frame slot owns a command buffer, its fence and half of the vertex and
 * uniform storage. The queue replays in order, so a slot's fence also covers
 * every earlier submission. xsdk_present_end flips only after a frame's fence. */
static void XvQueue(void)
{
    XvEndPass();XV_CALL(vkEndCommandBuffer(xv.command));
    VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&xv.command};
    VkMappedMemoryRange ranges[2]={
        {.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.vertices.memory,.size=VK_WHOLE_SIZE},
        {.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.uniforms.memory,.size=VK_WHOLE_SIZE}};
    if(xv.vertices.memory)XV_CALL(vkFlushMappedMemoryRanges(xv.device,2,ranges));
    unsigned started=GetTickCount();
    XV_CALL(vkQueueSubmit(xv.queue,1,&submit,xv.fence));
    xvCost.submits++;xvCost.submitMS+=GetTickCount()-started;
    xv.pending[xv.slot]=1;xv.recording=0;
}
static unsigned XvWait(unsigned slot)
{
    if(!xv.pending[slot])return 0;
    unsigned started=GetTickCount();
    XV_CALL(vkWaitForFences(xv.device,1,&xv.fences[slot],VK_TRUE,UINT64_MAX));
    unsigned waited=GetTickCount()-started;xvCost.waitMS+=waited;
    XvStampRead(slot);
    XV_CALL(vkResetFences(xv.device,1,&xv.fences[slot]));
    XV_CALL(vkResetCommandBuffer(xv.commands[slot],0));
    xv.pending[slot]=0;return waited;
}
/* Drain: the other slot's frame first, then this slot's work. */
static void XvSubmit(void)
{
    XvWait(xv.slot^1);
    if(xv.recording)XvQueue();
    XvWait(xv.slot);
    xv.uniformCursor=xv.slot*XV_UNIFORM_SLOT_BYTES;
}
/* Queue the presented frame without waiting. Record the next one into the
 * other slot once the previously presented frame, its last user, is done. */
static void XvSubmitFrame(void)
{
    XvEndPass();XvStampEnd();
    XvQueue();
    xv.slot^=1;xv.command=xv.commands[xv.slot];xv.fence=xv.fences[xv.slot];
    xvCost.frameWaitMS+=XvWait(xv.slot);
    xv.uniformCursor=xv.slot*XV_UNIFORM_SLOT_BYTES;
}
static void XvLayout(XvTarget *target,VkImageLayout layout)
{
    if(target->layout==layout)return;
    XvBegin();XvEndPass();
    VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,
        .dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,
        .oldLayout=target->layout,.newLayout=layout,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=target->image,
        .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    vkCmdPipelineBarrier(xv.command,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,NULL,0,NULL,1,&barrier);
    target->layout=layout;
}
static void XvPass(XvTarget *target)
{
    XvBegin();if(xv.inPass && xv.target==target)return;
    XvEndPass();XvLayout(target,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);xv.target=target;
    VkClearValue clears[2]={0};clears[1].depthStencil.depth=1;
    VkRenderPassBeginInfo begin={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=xv.passes[target->clearStencil?3:target->pass],
        .framebuffer=target->framebuffer,.renderArea={{0,0},{target->width,target->height}},
        .clearValueCount=target->clearStencil?2:0,.pClearValues=clears};
    target->clearStencil=0;
    vkCmdBeginRenderPass(xv.command,&begin,VK_SUBPASS_CONTENTS_INLINE);xv.inPass=1;xvCost.passes++;
}
static void XvImage(XvTarget *t,unsigned width,unsigned height,int depth)
{
    t->width=width;t->height=height;t->pass=depth?0:1;
    VkImageCreateInfo info={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,
        .format=VK_FORMAT_R8G8B8A8_UNORM,.extent={width,height,1},.mipLevels=1,.arrayLayers=1,
        .samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
        .usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT};
    XV_CALL(vkCreateImage(xv.device,&info,NULL,&t->image));
    VkMemoryRequirements requirements;vkGetImageMemoryRequirements(xv.device,t->image,&requirements);
    VkMemoryAllocateInfo alloc={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=requirements.size};
    XV_CALL(vkAllocateMemory(xv.device,&alloc,NULL,&t->memory));XV_CALL(vkBindImageMemory(xv.device,t->image,t->memory,0));
    VkImageViewCreateInfo view={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=t->image,.viewType=VK_IMAGE_VIEW_TYPE_2D,
        .format=info.format,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    XV_CALL(vkCreateImageView(xv.device,&view,NULL,&t->view));
    if(depth){
        info.format=VK_FORMAT_D24_UNORM_S8_UINT;info.usage=VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        XV_CALL(vkCreateImage(xv.device,&info,NULL,&t->depth));vkGetImageMemoryRequirements(xv.device,t->depth,&requirements);
        alloc.allocationSize=requirements.size;XV_CALL(vkAllocateMemory(xv.device,&alloc,NULL,&t->depthMemory));
        XV_CALL(vkBindImageMemory(xv.device,t->depth,t->depthMemory,0));
        view.image=t->depth;view.format=info.format;view.subresourceRange.aspectMask=VK_IMAGE_ASPECT_DEPTH_BIT|VK_IMAGE_ASPECT_STENCIL_BIT;
        XV_CALL(vkCreateImageView(xv.device,&view,NULL,&t->depthView));
    }
    VkImageView views[]={t->view,t->depthView};
    VkFramebufferCreateInfo fb={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=xv.passes[t->pass],
        .attachmentCount=depth?2:1,.pAttachments=views,.width=width,.height=height,.layers=1};
    XV_CALL(vkCreateFramebuffer(xv.device,&fb,NULL,&t->framebuffer));
    /* Define color and stencil before any LOAD render pass. */
    XvLayout(t,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkClearColorValue zero={{0,0,0,0}};VkImageSubresourceRange range={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    vkCmdClearColorImage(xv.command,t->image,t->layout,&zero,1,&range);
    if(depth){
        VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=t->depth,
            .subresourceRange={VK_IMAGE_ASPECT_DEPTH_BIT|VK_IMAGE_ASPECT_STENCIL_BIT,0,1,0,1}};
        vkCmdPipelineBarrier(xv.command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);
        VkClearDepthStencilValue clear={1,0};vkCmdClearDepthStencilImage(xv.command,t->depth,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&clear,1,&barrier.subresourceRange);
        barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
        barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT|VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
        vkCmdPipelineBarrier(xv.command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT,0,0,NULL,0,NULL,1,&barrier);
    }
}
static VkPipeline XvPipeline(unsigned pass,int shader,BlendMode blend,int stencil)
{
    int quad=shader>=14;
    VkPipeline *cached=&xv.pipelines[pass][shader][blend][stencil];if(*cached)return *cached;
    VkPipelineShaderStageCreateInfo stages[2]={
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=xv.shaders[quad?1:0],.pName="main"},
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=xv.shaders[2+shader],.pName="main"}};
    VkVertexInputBindingDescription binding={0,quad?sizeof(XvQuadVertex):sizeof(XvVertex),VK_VERTEX_INPUT_RATE_VERTEX};
    VkVertexInputAttributeDescription attrs[5]={
        {0,0,VK_FORMAT_R16G16B16A16_SSCALED,0},
        {1,0,VK_FORMAT_R8G8B8A8_USCALED,8},
        {2,0,VK_FORMAT_R8G8B8A8_UNORM,12},
        {3,0,VK_FORMAT_R8G8B8A8_SSCALED,16},
        {4,0,VK_FORMAT_R8G8B8A8_USCALED,20}};
    if(quad)attrs[0].format=VK_FORMAT_R32G32B32A32_SFLOAT;
    VkPipelineVertexInputStateCreateInfo input={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
        .vertexBindingDescriptionCount=1,.pVertexBindingDescriptions=&binding,.vertexAttributeDescriptionCount=quad?1:5,.pVertexAttributeDescriptions=attrs};
    VkPipelineInputAssemblyStateCreateInfo assembly={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=quad?VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP:VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
    VkPipelineViewportStateCreateInfo viewport={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.scissorCount=1};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};
    VkPipelineMultisampleStateCreateInfo samples={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
    VkStencilOpState st={.failOp=VK_STENCIL_OP_REPLACE,.passOp=stencil==1?VK_STENCIL_OP_REPLACE:VK_STENCIL_OP_KEEP,
        .depthFailOp=stencil==1?VK_STENCIL_OP_REPLACE:VK_STENCIL_OP_KEEP,.compareOp=stencil==1?VK_COMPARE_OP_ALWAYS:VK_COMPARE_OP_NOT_EQUAL,
        .compareMask=stencil==1?0x10:255,.writeMask=255,.reference=1};
    VkPipelineDepthStencilStateCreateInfo ds={.sType=VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO,.stencilTestEnable=stencil!=0,.front=st,.back=st};
    VkPipelineColorBlendAttachmentState attach={.colorWriteMask=15,.blendEnable=blend!=BM_NONE,
        .srcColorBlendFactor=VK_BLEND_FACTOR_ONE,.dstColorBlendFactor=VK_BLEND_FACTOR_ONE,.colorBlendOp=VK_BLEND_OP_ADD,
        .srcAlphaBlendFactor=VK_BLEND_FACTOR_ONE,.dstAlphaBlendFactor=VK_BLEND_FACTOR_ZERO,.alphaBlendOp=VK_BLEND_OP_ADD};
    float factor=1;
    if(blend==BM_AVERAGE){attach.srcColorBlendFactor=VK_BLEND_FACTOR_CONSTANT_COLOR;attach.dstColorBlendFactor=VK_BLEND_FACTOR_CONSTANT_COLOR;factor=0.5f;}
    if(blend==BM_SUBTRACT)attach.colorBlendOp=VK_BLEND_OP_REVERSE_SUBTRACT;
    if(blend==BM_ADD_QUATER_SOURCE){attach.srcColorBlendFactor=VK_BLEND_FACTOR_CONSTANT_COLOR;factor=0.25f;}
    VkPipelineColorBlendStateCreateInfo cb={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&attach,.blendConstants={factor,factor,factor,factor}};
    VkDynamicState dynamicStates[]={VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};
    VkPipelineDynamicStateCreateInfo dynamic={.sType=VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,.dynamicStateCount=2,.pDynamicStates=dynamicStates};
    VkGraphicsPipelineCreateInfo info={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=2,.pStages=stages,
        .pVertexInputState=&input,.pInputAssemblyState=&assembly,.pViewportState=&viewport,.pRasterizationState=&raster,
        .pMultisampleState=&samples,.pDepthStencilState=&ds,.pColorBlendState=&cb,.pDynamicState=&dynamic,
        .layout=xv.pipelineLayout,.renderPass=xv.passes[pass]};
    XV_CALL(vkCreateGraphicsPipelines(xv.device,VK_NULL_HANDLE,1,&info,NULL,cached));return *cached;
}
static void XvReserveUniform(void)
{
    unsigned stride=(sizeof(XvUniform)+xv.uniformAlignment-1)&~(xv.uniformAlignment-1);
    if(xv.uniformCursor+stride>(xv.slot+1)*XV_UNIFORM_SLOT_BYTES){XvTarget *target=xv.target;XvSubmit();XvPass(target);}
}
static void XvBindUniform(const XvUniform *state,unsigned texture)
{
    unsigned stride=(sizeof(*state)+xv.uniformAlignment-1)&~(xv.uniformAlignment-1);
    uint32_t offset=xv.uniformCursor;memcpy(xv.uniforms.map+offset,state,sizeof(*state));xv.uniformCursor+=stride;
    vkCmdBindDescriptorSets(xv.command,VK_PIPELINE_BIND_POINT_GRAPHICS,xv.pipelineLayout,0,1,&xv.sets[texture],1,&offset);
}
static void XvQuad(XvTarget *to,XvTarget *from,int mode,int x,int y,int width,int height,float sx,float sy,float sw,float sh)
{
    XvLayout(from,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);XvPass(to);
    XvReserveUniform();
    VkViewport vp={(float)x,(float)y,(float)width,(float)height,0,1};
    VkRect2D clip={{x,y},{width,height}};vkCmdSetViewport(xv.command,0,1,&vp);vkCmdSetScissor(xv.command,0,1,&clip);
    XvUniform state={0};state.scale[3]=(float)mode;
    state.source[0]=sx;state.source[1]=sy;state.source[2]=sw;state.source[3]=sh;
    unsigned texture=from==&xv.vram?0:from==&xv.main?(mode==3?3:1):2;
    XvBindUniform(&state,texture);vkCmdBindPipeline(xv.command,VK_PIPELINE_BIND_POINT_GRAPHICS,XvPipeline(to->pass,14+mode,BM_NONE,0));
    VkDeviceSize quadOffset=XV_VERTEX_BYTES;vkCmdBindVertexBuffers(xv.command,0,1,&xv.vertices.buffer,&quadOffset);
    vkCmdDraw(xv.command,4,1,0,0);
    xvCost.quads[mode]++;
}
static void XvReadTarget(XvTarget *target)
{
    /* vulkan4xenon accepts whole-level image/buffer copies. The 720p main
     * target is larger than PSX VRAM, including its tightly packed row pitch. */
    XV_CALL((size_t)target->width*target->height*4<=xv.staging.size?VK_SUCCESS:VK_ERROR_OUT_OF_HOST_MEMORY);
    XvLayout(target,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    VkBufferImageCopy region={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},
        .imageExtent={target->width,target->height,1}};
    vkCmdCopyImageToBuffer(xv.command,target->image,target->layout,xv.staging.buffer,1,&region);XvSubmit();
    VkMappedMemoryRange range={.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.staging.memory,.size=VK_WHOLE_SIZE};
    XV_CALL(vkInvalidateMappedMemoryRanges(xv.device,1,&range));
}
static void XvSyncCPU(void)
{
    if(!xv.vramGPUChanged)return;
    xvCost.reads++;
    XvReadTarget(&xv.vram);
    for(unsigned i=0;i<1024*512;i++)xv.pixels[i]=(u16)(xv.staging.map[4*i]|xv.staging.map[4*i+1]<<8);
    xv.vramGPUChanged=0;
    XvPaletteReset();
}
void NativeRenderer_UpdateVRAM(void)
{
    if(!xv.vramCPUChanged)return;
    XvPaletteReset();
    xvCost.uploads++;
    /* A previous submit may still read the staging buffer. Never overwrite it
     * until the fence; CPU writes merge with GPU-produced VRAM in Copy/Clear. */
    XvSubmit();
    for(unsigned i=0;i<1024*512;i++){xv.staging.map[4*i]=(u8)xv.pixels[i];xv.staging.map[4*i+1]=(u8)(xv.pixels[i]>>8);xv.staging.map[4*i+2]=0;xv.staging.map[4*i+3]=255;}
    VkMappedMemoryRange range={.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.staging.memory,.size=VK_WHOLE_SIZE};XV_CALL(vkFlushMappedMemoryRanges(xv.device,1,&range));
    XvLayout(&xv.vram,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkBufferImageCopy region={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={1024,512,1}};
    vkCmdCopyBufferToImage(xv.command,xv.staging.buffer,xv.vram.image,xv.vram.layout,1,&region);
    XvLayout(&xv.vram,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);xv.vramCPUChanged=0;
}

static void XvCreatePasses(void)
{
    for(unsigned i=0;i<4;i++){
        VkAttachmentDescription attachments[2]={
            {.format=i==2?VK_FORMAT_B8G8R8A8_UNORM:VK_FORMAT_R8G8B8A8_UNORM,.samples=VK_SAMPLE_COUNT_1_BIT,
             .loadOp=VK_ATTACHMENT_LOAD_OP_LOAD,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,
             .stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL},
            {.format=VK_FORMAT_D24_UNORM_S8_UINT,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=i==3?VK_ATTACHMENT_LOAD_OP_CLEAR:VK_ATTACHMENT_LOAD_OP_LOAD,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,
             .stencilLoadOp=i==3?VK_ATTACHMENT_LOAD_OP_CLEAR:VK_ATTACHMENT_LOAD_OP_LOAD,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_STORE,
             .initialLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,.finalLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL}};
        VkAttachmentReference color={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL},depth={1,VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL};
        VkSubpassDescription subpass={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&color,.pDepthStencilAttachment=(i==0 || i==3)?&depth:NULL};
        VkRenderPassCreateInfo info={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=(i==0 || i==3)?2:1,.pAttachments=attachments,.subpassCount=1,.pSubpasses=&subpass};
        XV_CALL(vkCreateRenderPass(xv.device,&info,NULL,&xv.passes[i]));
    }
}
static void XvConfig(const char *section,const char *key,const char *value,void *context)
{
    (void)context;
    if(!strcmp(section,"debug")){if(!strcmp(key,"reveal_holes"))xvRevealHoles=value[0]=='1';return;}
    if(strcmp(section,"graphics"))return;
    // interpolation = 2 keeps menus, the hub, cutscenes and results at 30 FPS.
    if(!strcmp(key,"interpolation") && !strcmp(value,"2")){g_nativeHDEnableInterpolation=2;return;}
    if(strcmp(value,"0") && strcmp(value,"1"))return;
    int enabled=value[0]=='1';
    if(!strcmp(key,"interpolation"))g_nativeHDEnableInterpolation=enabled;
    if(!strcmp(key,"texture_filter"))g_cfg_bilinearFiltering=enabled;
    if(!strcmp(key,"edge_aa"))xvEdgeAA=enabled;
    if(!strcmp(key,"precise_vertices"))g_nativePreciseVertices=enabled;
}
int NativeRenderer_InitialiseRender(char *name,int width,int height,int fullscreen)
{
    (void)name;(void)width;(void)height;(void)fullscreen;
    g_nativePreciseVertices=1;
    NativeConfig_Read("game:/ctr360.ini",XvConfig,NULL);
    Platform_Log("[graphics] interpolation=%d texture_filter=%d edge_aa=%d precise_vertices=%d reveal_holes=%d\n",
        g_nativeHDEnableInterpolation,g_cfg_bilinearFiltering,xvEdgeAA,g_nativePreciseVertices,xvRevealHoles);
    const char *instanceExtensions[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_DISPLAY_EXTENSION_NAME};
    const char *deviceExtensions[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="ctr360 xSDK experimental",.apiVersion=VK_API_VERSION_1_0};
    VkInstanceCreateInfo instance={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app,.enabledExtensionCount=2,.ppEnabledExtensionNames=instanceExtensions};
    XV_CALL(vkCreateInstance(&instance,NULL,&xv.instance));unsigned count=1;XV_CALL(vkEnumeratePhysicalDevices(xv.instance,&count,&xv.physical));
    VkPhysicalDeviceProperties properties;vkGetPhysicalDeviceProperties(xv.physical,&properties);
    xv.uniformAlignment=properties.limits.minUniformBufferOffsetAlignment;
    xv.timestampPeriod=properties.limits.timestampPeriod;
    if(xv.uniformAlignment<64)xv.uniformAlignment=64;
    float priority=1;VkDeviceQueueCreateInfo queue={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueCount=1,.pQueuePriorities=&priority};
    VkDeviceCreateInfo device={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&queue,.enabledExtensionCount=1,.ppEnabledExtensionNames=deviceExtensions};
    XV_CALL(vkCreateDevice(xv.physical,&device,NULL,&xv.device));vkGetDeviceQueue(xv.device,0,0,&xv.queue);
    VkDisplayPropertiesKHR display;count=1;XV_CALL(vkGetPhysicalDeviceDisplayPropertiesKHR(xv.physical,&count,&display));
    VkDisplayModePropertiesKHR mode;count=1;XV_CALL(vkGetDisplayModePropertiesKHR(xv.physical,display.display,&count,&mode));
    if(mode.parameters.visibleRegion.width!=XV_WIDTH || mode.parameters.visibleRegion.height!=XV_HEIGHT){Platform_LogError("[vulkan] 720p display required\n");return 0;}
    VkDisplaySurfaceCreateInfoKHR surface={.sType=VK_STRUCTURE_TYPE_DISPLAY_SURFACE_CREATE_INFO_KHR,.displayMode=mode.displayMode,
        .transform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,.alphaMode=VK_DISPLAY_PLANE_ALPHA_OPAQUE_BIT_KHR,.imageExtent={XV_WIDTH,XV_HEIGHT}};
    XV_CALL(vkCreateDisplayPlaneSurfaceKHR(xv.instance,&surface,NULL,&xv.surface));
    VkSwapchainCreateInfoKHR swap={.sType=VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,.surface=xv.surface,.minImageCount=2,
        .imageFormat=VK_FORMAT_B8G8R8A8_UNORM,.imageColorSpace=VK_COLOR_SPACE_SRGB_NONLINEAR_KHR,.imageExtent={XV_WIDTH,XV_HEIGHT},
        .imageArrayLayers=1,.imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,.preTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
        .compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,.presentMode=VK_PRESENT_MODE_FIFO_KHR,.clipped=VK_TRUE};
    XV_CALL(vkCreateSwapchainKHR(xv.device,&swap,NULL,&xv.swapchain));
    VkImage images[3];xv.imageCount=3;XV_CALL(vkGetSwapchainImagesKHR(xv.device,xv.swapchain,&xv.imageCount,images));
    VkCommandPoolCreateInfo pool={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT};
    XV_CALL(vkCreateCommandPool(xv.device,&pool,NULL,&xv.pool));
    VkCommandBufferAllocateInfo command={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=xv.pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=2};
    XV_CALL(vkAllocateCommandBuffers(xv.device,&command,xv.commands));
    VkFenceCreateInfo fence={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    for(unsigned i=0;i<2;i++)XV_CALL(vkCreateFence(xv.device,&fence,NULL,&xv.fences[i]));
    XV_CALL(vkCreateFence(xv.device,&fence,NULL,&xv.acquireFence));
    xv.slot=0;xv.command=xv.commands[0];xv.fence=xv.fences[0];
    VkQueryPoolCreateInfo queries={.sType=VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,.queryType=VK_QUERY_TYPE_TIMESTAMP,.queryCount=4};
    if(vkCreateQueryPool(xv.device,&queries,NULL,&xv.timestamps)!=VK_SUCCESS)xv.timestamps=VK_NULL_HANDLE;
    XvCreatePasses();
    for(unsigned i=0;i<xv.imageCount;i++){
        XvTarget *t=&xv.swap[i];t->image=images[i];t->width=XV_WIDTH;t->height=XV_HEIGHT;t->pass=2;
        VkImageViewCreateInfo view={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=t->image,.viewType=VK_IMAGE_VIEW_TYPE_2D,
            .format=VK_FORMAT_B8G8R8A8_UNORM,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
        XV_CALL(vkCreateImageView(xv.device,&view,NULL,&t->view));
        VkFramebufferCreateInfo fb={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=xv.passes[2],.attachmentCount=1,
            .pAttachments=&t->view,.width=XV_WIDTH,.height=XV_HEIGHT,.layers=1};XV_CALL(vkCreateFramebuffer(xv.device,&fb,NULL,&t->framebuffer));
    }
    /* Flat primitives return white in psx.frag; no dummy render target is needed. */
    Platform_Log("[vulkan] creating main, offscreen and VRAM targets\n");
    XvImage(&xv.main,XV_WIDTH,XV_HEIGHT,1);XvImage(&xv.off,1024,512,1);XvImage(&xv.vram,1024,512,0);
    Platform_Log("[vulkan] targets ready; creating upload buffers and descriptors\n");
    XvBufferCreate(&xv.vertices,XV_VERTEX_BYTES+4*sizeof(XvQuadVertex),VK_BUFFER_USAGE_VERTEX_BUFFER_BIT);
    XvQuadVertex *quad=(XvQuadVertex *)(xv.vertices.map+XV_VERTEX_BYTES);
    memset(quad,0,4*sizeof(*quad));quad[1].position[1]=1;quad[2].position[0]=1;quad[3].position[0]=1;quad[3].position[1]=1;
    XvBufferCreate(&xv.uniforms,XV_UNIFORM_BYTES,VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT);
    XvBufferCreate(&xv.staging,XV_WIDTH*XV_HEIGHT*4,VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT);
    VkDescriptorSetLayoutBinding bindings[]={
        {.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_VERTEX_BIT|VK_SHADER_STAGE_FRAGMENT_BIT},
        {.binding=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT}};
    VkDescriptorSetLayoutCreateInfo layout={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=2,.pBindings=bindings};
    XV_CALL(vkCreateDescriptorSetLayout(xv.device,&layout,NULL,&xv.setLayout));
    VkPipelineLayoutCreateInfo pl={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&xv.setLayout};XV_CALL(vkCreatePipelineLayout(xv.device,&pl,NULL,&xv.pipelineLayout));
    VkDescriptorPoolSize sizes[]={{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,4},{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,4}};
    VkDescriptorPoolCreateInfo dp={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=4,.poolSizeCount=2,.pPoolSizes=sizes};XV_CALL(vkCreateDescriptorPool(xv.device,&dp,NULL,&xv.descriptors));
    VkSamplerCreateInfo sampler={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_NEAREST,.minFilter=VK_FILTER_NEAREST,
        .mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE};
    XV_CALL(vkCreateSampler(xv.device,&sampler,NULL,&xv.sampler));
    sampler.minFilter=VK_FILTER_LINEAR;sampler.magFilter=VK_FILTER_LINEAR;
    XV_CALL(vkCreateSampler(xv.device,&sampler,NULL,&xv.linearSampler));
    sampler.minFilter=VK_FILTER_NEAREST;sampler.magFilter=VK_FILTER_NEAREST;
    sampler.addressModeU=sampler.addressModeV=VK_SAMPLER_ADDRESS_MODE_REPEAT;
    XV_CALL(vkCreateSampler(xv.device,&sampler,NULL,&xv.vramSampler));
    XvTarget *textures[]={&xv.vram,&xv.main,&xv.off,&xv.main};
    for(unsigned i=0;i<4;i++){
        VkDescriptorSetAllocateInfo alloc={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=xv.descriptors,.descriptorSetCount=1,.pSetLayouts=&xv.setLayout};
        XV_CALL(vkAllocateDescriptorSets(xv.device,&alloc,&xv.sets[i]));
        VkDescriptorBufferInfo buffer={xv.uniforms.buffer,0,sizeof(XvUniform)};
        VkDescriptorImageInfo image={i==0?xv.vramSampler:i==3?xv.linearSampler:xv.sampler,textures[i]->view,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        VkWriteDescriptorSet writes[]={
            {.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=xv.sets[i],.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,.pBufferInfo=&buffer},
            {.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=xv.sets[i],.dstBinding=1,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&image}};
        vkUpdateDescriptorSets(xv.device,2,writes,0,NULL);
    }
    Platform_Log("[vulkan] descriptors ready; loading bundled shaders\n");
    const uint32_t *code[]={psx_vert_spirv,quad_vert_spirv,
        psx_0_frag_spirv,psx_1_frag_spirv,psx_2_frag_spirv,psx_3_frag_spirv,
        psx_4_frag_spirv,psx_5_frag_spirv,psx_6_frag_spirv,
        psx_7_frag_spirv,psx_8_frag_spirv,psx_9_frag_spirv,psx_10_frag_spirv,
        psx_11_frag_spirv,psx_12_frag_spirv,psx_13_frag_spirv,
        quad_0_frag_spirv,quad_1_frag_spirv,quad_2_frag_spirv,quad_3_frag_spirv};
    const unsigned bytes[]={PSX_VERT_SPIRV_BYTES,QUAD_VERT_SPIRV_BYTES,
        PSX_0_FRAG_SPIRV_BYTES,PSX_1_FRAG_SPIRV_BYTES,PSX_2_FRAG_SPIRV_BYTES,PSX_3_FRAG_SPIRV_BYTES,
        PSX_4_FRAG_SPIRV_BYTES,PSX_5_FRAG_SPIRV_BYTES,PSX_6_FRAG_SPIRV_BYTES,
        PSX_7_FRAG_SPIRV_BYTES,PSX_8_FRAG_SPIRV_BYTES,PSX_9_FRAG_SPIRV_BYTES,PSX_10_FRAG_SPIRV_BYTES,
        PSX_11_FRAG_SPIRV_BYTES,PSX_12_FRAG_SPIRV_BYTES,PSX_13_FRAG_SPIRV_BYTES,
        QUAD_0_FRAG_SPIRV_BYTES,QUAD_1_FRAG_SPIRV_BYTES,QUAD_2_FRAG_SPIRV_BYTES,QUAD_3_FRAG_SPIRV_BYTES};
    for(unsigned i=0;i<20;i++){VkShaderModuleCreateInfo info={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=bytes[i],.pCode=code[i]};XV_CALL(vkCreateShaderModule(xv.device,&info,NULL,&xv.shaders[i]));}
    Platform_Log("[vulkan] shaders ready; creating graphics pipelines\n");
    for(unsigned shader=0;shader<14;shader++)for(unsigned blend=0;blend<5;blend++)for(unsigned mask=1;mask<3;mask++)XvPipeline(0,shader,(BlendMode)blend,mask);
    for(unsigned pass=0;pass<3;pass++)for(unsigned mode=0;mode<4;mode++)XvPipeline(pass,14+mode,BM_NONE,0);
    Platform_Log("[vulkan] pipelines ready; submitting initial clears\n");
    XvSubmit();xv.state.rect[2]=512;xv.state.rect[3]=216;xv.state.scale[0]=1;xv.vramCPUChanged=1;
    XvColorCheck();
    Platform_Log("[vulkan] 720p renderer initialized (experimental)\n");return 1;
}
int NativeRenderer_InitialisePSX(void) { return xv.device!=VK_NULL_HANDLE; }
void NativeRenderer_ResetDevice(void) {}
void NativeRenderer_UpdateSwapIntervalState(int interval) { (void)interval; }
void NativeRenderer_BeginScene(void)
{
    // Work recorded since the last present may use this slot's vertices;
    // drain it before rewinding. Normally the slot is already free.
    if(xv.recording)XvSubmit();
    xv.vertexCursor=xv.slot*XV_VERTEX_SLOT_BYTES;xv.vertexCount=0;xv.mainValid=0;xv.mainResolved=0;xv.offscreen=0;
    NativeRenderer_UpdateVRAM();xv.main.clearStencil=1;XvPass(&xv.main);
    if(xvRevealHoles){
        VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,.clearValue.color.float32={1,0,1,0}};
        VkClearRect rect={.rect={{0,0},{XV_WIDTH,XV_HEIGHT}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
    }
}
void NativeRenderer_EndScene(void) { XvEndPass(); }
void NativeRenderer_EndGpuFrame(void) {}
void NativeRenderer_FinishGpuMeasurements(void) {}
void NativeRenderer_SetUIPass(int enabled) { xv.ui=enabled!=0; }
void NativeRenderer_SetProjection(const RECT16 *draw,const DISPENV *display,int offscreen)
{
    xv.state.rect[2]=(float)(offscreen?draw->w:display->disp.w);
    xv.state.rect[3]=(float)(offscreen?draw->h:display->disp.h);
    if(xv.state.rect[2]<1)xv.state.rect[2]=1;if(xv.state.rect[3]<1)xv.state.rect[3]=1;
}
void NativeRenderer_SetupClipMode(const RECT16 *clip,const DISPENV *display,int enabled)
{
    xv.clipEnabled=enabled && (display->isinter || clip->x!=display->disp.x || clip->y!=display->disp.y || clip->w!=display->disp.w || clip->h!=display->disp.h);
    if(!xv.clipEnabled)return;
    float sx=xv.ui?0.75f:1.0f;
    float dw=display->disp.w>0?display->disp.w:1,dh=display->disp.h>0?display->disp.h:1;
    int left=(int)((((clip->x-display->disp.x)/dw-0.5f)*sx+0.5f)*XV_WIDTH);
    int top=(int)((clip->y-display->disp.y)/dh*XV_HEIGHT);
    int right=left+(int)(clip->w/dw*XV_WIDTH*sx),bottom=top+(int)(clip->h/dh*XV_HEIGHT);
    if(left<0)left=0;if(top<0)top=0;if(right>XV_WIDTH)right=XV_WIDTH;if(bottom>XV_HEIGHT)bottom=XV_HEIGHT;
    xv.scissor=(VkRect2D){{left,top},{right>left?(unsigned)(right-left):0,bottom>top?(unsigned)(bottom-top):0}};
}
void NativeRenderer_SetBlendMode(BlendMode blend) { xv.blend=blend; }
void NativeRenderer_SetStencilMode(int drawPrim) { xv.drawPrim=drawPrim; }
void NativeRenderer_SetTexture(TextureID texture,TexFormat format) { xv.texture=texture;xv.format=format; }
void NativeRenderer_SetOverrideTextureSize(int width,int height) { (void)width;(void)height; }
void NativeRenderer_SetPSXTextureSemiTransPass(int pass) { xv.state.flags[0]=(float)pass; }
void NativeRenderer_SetPSXDrawMaskSet(int set) { xv.state.flags[1]=(float)set; }
void NativeRenderer_SetPSXTextureOutputSTP(int set) { xv.state.flags[2]=(float)set; }
TextureID NativeRenderer_GetVRAMTexture(void) { return 1; }
TextureID NativeRenderer_GetWhiteTexture(void) { return 2; }
void NativeRenderer_UpdateVertexBuffer(const GrVertex *vertices,int count)
{
    if(count<=0)return;if(count>(int)MAX_VERTEX_BUFFER_SIZE)count=MAX_VERTEX_BUFFER_SIZE;
    size_t bytes=count*sizeof(XvVertex);
    if(xv.vertexCursor+bytes>(xv.slot+1)*XV_VERTEX_SLOT_BYTES){XvSubmit();xv.vertexCursor=xv.slot*XV_VERTEX_SLOT_BYTES;}
    xv.vertexBase=xv.vertexCursor;xv.vertexCount=count;
    // Draw calls consume this upload synchronously before the next upload.
    // Read CLUT metadata from cached CPU vertices, never GPU-mapped memory.
    xv.sourceVertices=vertices;
    XvVertex *out=(XvVertex *)(xv.vertices.map+xv.vertexCursor);xv.vertexCursor+=bytes;
    for(int first=0;first<count;first+=3){
        int corners=count-first<3?count-first:3;
        u8 u0=255,v0=255,u1=0,v1=0;
        for(int i=0;i<corners;i++){
            const GrVertex *g=&vertices[first+i];
            if(g->u<u0)u0=g->u;if(g->u>u1)u1=g->u;if(g->v<v0)v0=g->v;if(g->v>v1)v1=g->v;
        }
        for(int i=0;i<corners;i++){
            XvVertex *o=&out[first+i];
            o->v=vertices[first+i];o->uvMin[0]=u0;o->uvMin[1]=v0;o->uvMax[0]=u1;o->uvMax[1]=v1;
        }
    }
}
static void XvDrawTriangles(int first,int triangles,int filtering)
{
    if(triangles>0)xvCost.trisRequested+=triangles;
    if(first<0 || triangles<=0 || (unsigned)first>xv.vertexCount || (unsigned)triangles>(xv.vertexCount-first)/3){
        if(triangles>0)xvCost.trisDropped+=triangles;return;}
    NativeRenderer_UpdateVRAM();
    if(!XvTexturePassNeeded(first,triangles)){xvCost.skippedSTPPasses++;xvCost.trisSkipped+=triangles;return;}
    XvLayout(&xv.vram,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    XvTarget *target=xv.offscreen?&xv.off:&xv.main;XvPass(target);
    unsigned width=xv.offscreen?xv.offRect.w:XV_WIDTH,height=xv.offscreen?xv.offRect.h:XV_HEIGHT;
    XvReserveUniform();
    VkViewport viewport={0,0,(float)width,(float)height,0,1};VkRect2D clip={{0,0},{width,height}};
    if(xv.clipEnabled && !xv.offscreen)clip=xv.scissor;
    vkCmdSetViewport(xv.command,0,1,&viewport);vkCmdSetScissor(xv.command,0,1,&clip);
    xv.state.scale[0]=xv.ui && !xv.offscreen?0.75f:1.0f;xv.state.scale[1]=xv.state.rect[2]*0.5f;
    xv.state.scale[2]=xv.offscreen?1.0f:0.0f;xv.state.scale[3]=(float)xv.format;
    xv.state.flags[3]=filtering;
    if(g_dbg_texturelessMode)xv.state.scale[3]=3;
    XvBindUniform(&xv.state,0);
    /* Untextured splits retain the draw environment's tpage format. Their
     * white texture ID, not that inherited format, selects vertex color. */
    unsigned shader=(xv.texture==NativeRenderer_GetWhiteTexture() || xv.format==TF_32_BIT_RGBA || g_dbg_texturelessMode)?6:2*(unsigned)xv.format+(xv.state.flags[3]>0.5f);
    vkCmdBindPipeline(xv.command,VK_PIPELINE_BIND_POINT_GRAPHICS,XvPipeline(0,shader+(xv.offscreen?7:0),xv.blend,xv.drawPrim?1:2));
    VkDeviceSize offset=xv.vertexBase;vkCmdBindVertexBuffers(xv.command,0,1,&xv.vertices.buffer,&offset);
    xvCost.draws++;xvCost.shaderDraws[shader]++;xvCost.blendDraws[xv.blend]++;xvCost.uiDraws+=xv.ui!=0;
    vkCmdDraw(xv.command,triangles*3,1,first,0);xvCost.trisDrawn+=triangles;if(!xv.offscreen)xv.mainValid=1;
}
void NativeRenderer_DrawTriangles(int first,int triangles)
{
    XvDrawTriangles(first,triangles,g_cfg_bilinearFiltering && !xv.ui && !xv.offscreen);
}

static int XvValidRect(int x,int y,int w,int h) { return x>=0 && y>=0 && w>0 && h>0 && x<=1024-w && y<=512-h; }
void NativeRenderer_CopyVRAM(u16 *src, int x, int y, int w, int h, int dst_x, int dst_y)
{
 s64 sx=x, sy=y, dx=dst_x, dy=dst_y, width=w, height=h;
 int fromVRAM = src == NULL;
 int sourceWidth = fromVRAM ? VRAM_WIDTH : w;
 int sourceHeight = fromVRAM ? VRAM_HEIGHT : h;
 int stride = sourceWidth;
 int firstRow, endRow, rowStep, row;
 if (width <= 0 || height <= 0) return;
 /* Clip both ends before pointer arithmetic. 64-bit temporaries also make
  * invalid extreme coordinates safe without changing valid Load/MoveImage. */
 if (sx < 0) {width += sx; dx -= sx; sx=0;}
 if (sy < 0) {height += sy; dy -= sy; sy=0;}
 if (dx < 0) {width += dx; sx -= dx; dx=0;}
 if (dy < 0) {height += dy; sy -= dy; dy=0;}
 if (width > sourceWidth-sx) width=sourceWidth-sx;
 if (height > sourceHeight-sy) height=sourceHeight-sy;
 if (width > VRAM_WIDTH-dx) width=VRAM_WIDTH-dx;
 if (height > VRAM_HEIGHT-dy) height=VRAM_HEIGHT-dy;
 if (width <= 0 || height <= 0) return;
 x=(int)sx; y=(int)sy; dst_x=(int)dx; dst_y=(int)dy; w=(int)width; h=(int)height;
 if (fromVRAM)
 {
  XvSyncCPU();
  src=xv.pixels;
 }
 XvSyncCPU();
 firstRow=0;endRow=h;rowStep=1;
 if (fromVRAM && dst_y > y && dst_y < y+h) {firstRow=h-1;endRow=-1;rowStep=-1;}
 for (row=firstRow;row!=endRow;row+=rowStep)
  memmove(xv.pixels+(dst_y+row)*VRAM_WIDTH+dst_x,
          src+(y+row)*stride+x,w*sizeof(u16));
 xv.vramCPUChanged=1;
}

void NativeRenderer_ReadVRAM(u16 *dst,int x,int y,int w,int h)
{
    if(!dst || !XvValidRect(x,y,w,h))return;XvSyncCPU();
    for(int row=0;row<h;row++)memcpy(dst+row*w,xv.pixels+(y+row)*1024+x,w*2);
}
int NativeRenderer_GetVRAMStateSize(void) { return sizeof(xv.pixels); }
int NativeRenderer_CaptureVRAMState(void *dst,int size)
{
    if(!dst || size<(int)sizeof(xv.pixels))return 0;XvSyncCPU();memcpy(dst,xv.pixels,sizeof(xv.pixels));return 1;
}
int NativeRenderer_RestoreVRAMState(const void *src,int size)
{
    if(!src || size<(int)sizeof(xv.pixels))return 0;XvSubmit();memcpy(xv.pixels,src,sizeof(xv.pixels));
    xv.vramCPUChanged=1;xv.vramGPUChanged=0;xv.mainValid=0;return 1;
}
void NativeRenderer_ClearVRAM(int x,int y,int w,int h,u8 r,u8 g,u8 b)
{
    if(!XvValidRect(x,y,w,h))return;
    NativeRenderer_UpdateVRAM();XvPass(&xv.vram);
    unsigned color=(r>>3)|((g>>3)<<5)|((b>>3)<<10);
    VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,
        .clearValue.color.float32={(color&255)/255.0f,(color>>8)/255.0f,0,1}};
    VkClearRect rect={.rect={{x,y},{w,h}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
    xv.vramGPUChanged=1;
    XvPaletteWritten(x,y,w,h);
}

void NativeRenderer_Clear(int x,int y,int w,int h,u8 r,u8 g,u8 b)
{
    NativeRenderer_ClearVRAM(x,y,w,h,r,g,b);
    int dx=activeDispEnv.disp.x,dy=activeDispEnv.disp.y,dw=activeDispEnv.disp.w,dh=activeDispEnv.disp.h;
    if(dw<=0 || dh<=0)return;
    int left=x>dx?x:dx,top=y>dy?y:dy,right=x+w<dx+dw?x+w:dx+dw,bottom=y+h<dy+dh?y+h:dy+dh;
    if(right<=left || bottom<=top)return;
    XvPass(&xv.main);
    VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,
        .clearValue.color.float32={(r>>3)*8/255.0f,(g>>3)*8/255.0f,(b>>3)*8/255.0f,0}};
    if(xvRevealHoles){clear.clearValue.color.float32[0]=1;clear.clearValue.color.float32[1]=0;clear.clearValue.color.float32[2]=1;}
    int x0=(left-dx)*XV_WIDTH/dw,y0=(top-dy)*XV_HEIGHT/dh;
    int x1=(right-dx)*XV_WIDTH/dw,y1=(bottom-dy)*XV_HEIGHT/dh;
    VkClearRect rect={.rect={{x0,y0},{x1-x0,y1-y0}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);xv.mainValid=1;
}
static void XvPack(XvTarget *target,int x,int y,int w,int h)
{
    if(!XvValidRect(x,y,w,h))return;
    NativeRenderer_UpdateVRAM();
    float sw=target==&xv.off?(float)w/target->width:1,sh=target==&xv.off?(float)h/target->height:1;
    XvQuad(&xv.vram,target,1,x,y,w,h,0,0,sw,sh);XvLayout(&xv.vram,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);xv.vramGPUChanged=1;
    XvPaletteWritten(x,y,w,h);
}
void NativeRenderer_SetOffscreenState(const RECT16 *rect,int enabled)
{
    if(enabled && xv.offscreen && memcmp(rect,&xv.offRect,sizeof(*rect))==0)return;
    if(!enabled && !xv.offscreen)return;
    if(xv.offscreen)XvPack(&xv.off,xv.offRect.x,xv.offRect.y,xv.offRect.w,xv.offRect.h);
    xv.offscreen=enabled;
    if(enabled){
        if(!XvValidRect(rect->x,rect->y,rect->w,rect->h)){xv.offscreen=0;return;}
        xv.offRect=*rect;NativeRenderer_UpdateVRAM();xv.off.clearStencil=1;
        XvQuad(&xv.off,&xv.vram,2,0,0,rect->w,rect->h,rect->x/1024.0f,rect->y/512.0f,rect->w/1024.0f,rect->h/512.0f);
        XvPass(&xv.off);
    }else XvPass(&xv.main);
}
void NativeRenderer_StoreFrameBuffer(int x,int y,int w,int h)
{
    if(xv.offscreen)NativeRenderer_SetOffscreenState(&xv.offRect,0);
    xv.mainResolved=xv.mainValid;
    if(xv.mainValid && !g_nativeHDIntermediate)XvPack(&xv.main,x,y,w,h);
}
void NativeRenderer_StoreFeedback(int x,int y,int w,int h)
{
    xvCost.feedbackRequests++;
    if(xv.mainValid && g_nativeHDIntermediate)xvCost.midpointFeedbackSkips++;
    NativeRenderer_StoreFrameBuffer(x,y,w,h);
}
void NativeRenderer_RequestCapture(void) { xvCaptureRequested=1; }
static void XvWriteCapture(void)
{
    char path[48];unsigned n=xvCaptureCount++;
    XvReadTarget(&xv.main);
    snprintf(path,sizeof(path),"game:/capture_%03u.bmp",n);FILE *file=fopen(path,"wb");
    if(file){
        /* 24-bit bottom-up BMP; 1280*3 bytes per row needs no padding. */
        unsigned row=XV_WIDTH*3,size=54+row*XV_HEIGHT;
        unsigned char header[54]={'B','M'};
        unsigned fields[][2]={{2,size},{10,54},{14,40},{18,XV_WIDTH},{22,XV_HEIGHT},{34,row*XV_HEIGHT},{38,2835},{42,2835}};
        for(unsigned i=0;i<sizeof(fields)/sizeof(fields[0]);i++)
            for(unsigned k=0;k<4;k++)header[fields[i][0]+k]=(unsigned char)(fields[i][1]>>(8*k));
        header[26]=1;header[28]=24;fwrite(header,1,54,file);
        static unsigned char line[XV_WIDTH*3];
        for(int y=XV_HEIGHT-1;y>=0;y--){
            const unsigned char *src=xv.staging.map+(size_t)y*XV_WIDTH*4;
            for(int x=0;x<XV_WIDTH;x++){line[3*x]=src[4*x+2];line[3*x+1]=src[4*x+1];line[3*x+2]=src[4*x];}
            fwrite(line,1,row,file);
        }
        fclose(file);
    }
    /* VRAM as little-endian 16-bit words, 1024x512, for offline decoding. */
    XvSyncCPU();
    snprintf(path,sizeof(path),"game:/capture_%03u_vram.bin",n);file=fopen(path,"wb");
    if(file){
        static unsigned char words[1024*2];
        for(int y=0;y<512;y++){
            for(int x=0;x<1024;x++){u16 v=xv.pixels[y*1024+x];words[2*x]=(unsigned char)v;words[2*x+1]=(unsigned char)(v>>8);}
            fwrite(words,1,sizeof(words),file);
        }
        fclose(file);
    }
    Platform_Log("[capture] %u game:/capture_%03u.bmp + _vram.bin (main target before edge AA) reveal_holes=%d edge_aa=%d filter=%d precise=%d\n",
        n,n,xvRevealHoles,xvEdgeAA,g_cfg_bilinearFiltering,g_nativePreciseVertices);
}
void NativeRenderer_PresentVRAMRect(int x,int y,int w,int h)
{
    if(w<=0 || h<=0)return;NativeRenderer_UpdateVRAM();
    if(xvCaptureRequested && xv.mainResolved){xvCaptureRequested=0;XvWriteCapture();}
    /* Acquisition can precede this frame's submit: render, resolve and
     * presentation stay in queue order, and the flip waits for the frame's
     * fence. The previous frame may still be drawing; its slot is separate. */
    unsigned started=GetTickCount();
    unsigned index=0;XV_CALL(vkAcquireNextImageKHR(xv.device,xv.swapchain,UINT64_MAX,VK_NULL_HANDLE,xv.acquireFence,&index));
    XV_CALL(vkWaitForFences(xv.device,1,&xv.acquireFence,VK_TRUE,UINT64_MAX));XV_CALL(vkResetFences(xv.device,1,&xv.acquireFence));
    xvCost.acquireMS+=GetTickCount()-started;
    if(xv.mainResolved)XvQuad(&xv.swap[index],&xv.main,xvEdgeAA?3:0,0,0,XV_WIDTH,XV_HEIGHT,0,0,1,1);
    else XvQuad(&xv.swap[index],&xv.vram,2,0,0,XV_WIDTH,XV_HEIGHT,x/1024.0f,y/512.0f,w/1024.0f,h/512.0f);
    XvLayout(&xv.swap[index],VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
    XvSubmitFrame();
    VkPresentInfoKHR present={.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,.swapchainCount=1,.pSwapchains=&xv.swapchain,.pImageIndices=&index};
    started=GetTickCount();XV_CALL(vkQueuePresentKHR(xv.queue,&present));xvCost.presentMS+=GetTickCount()-started;
    static unsigned lastReport=0,frames=0;frames++;
    unsigned now=GetTickCount();
    if(now-lastReport>=5000){
        Platform_Log("[vulkan-perf] frames=%u span=%ums draws=%u passes=%u submits=%u submit=%ums wait=%ums uploads=%u reads=%u\n",
            frames,now-lastReport,xvCost.draws,xvCost.passes,xvCost.submits,xvCost.submitMS,xvCost.waitMS,xvCost.uploads,xvCost.reads);
        Platform_Log("[vulkan-perf-detail] transfer-wait=%ums frame-wait=%ums acquire=%ums flip=%ums shaders=%u,%u,%u,%u,%u,%u,%u quads=%u,%u,%u,%u\n",
            xvCost.waitMS-xvCost.frameWaitMS,xvCost.frameWaitMS,xvCost.acquireMS,xvCost.presentMS,
            xvCost.shaderDraws[0],xvCost.shaderDraws[1],xvCost.shaderDraws[2],xvCost.shaderDraws[3],
            xvCost.shaderDraws[4],xvCost.shaderDraws[5],xvCost.shaderDraws[6],
            xvCost.quads[0],xvCost.quads[1],xvCost.quads[2],xvCost.quads[3]);
        Platform_Log("[vulkan-work] blend-draws=%u,%u,%u,%u,%u ui=%u feedback=%u midpoint-feedback-skips=%u stp-pass-skips=%u tris=%u/%u dropped=%u stp-skipped=%u\n",
            xvCost.blendDraws[0],xvCost.blendDraws[1],xvCost.blendDraws[2],xvCost.blendDraws[3],xvCost.blendDraws[4],
            xvCost.uiDraws,xvCost.feedbackRequests,xvCost.midpointFeedbackSkips,xvCost.skippedSTPPasses,
            xvCost.trisDrawn,xvCost.trisRequested,xvCost.trisDropped,xvCost.trisSkipped);
        if(xvCost.gpuFrames)Platform_Log("[vulkan-gpu] frames=%u avg=%.1fms max=%.1fms over16ms=%u\n",
            xvCost.gpuFrames,xvCost.gpuTotalUS/1000.0/xvCost.gpuFrames,xvCost.gpuMaxUS/1000.0,xvCost.gpuOver16);
        frames=0;lastReport=now;memset(&xvCost,0,sizeof(xvCost));
    }
}
void NativeRenderer_PresentVRAMDisplay(void) { RECT16 r=activeDispEnv.disp;NativeRenderer_PresentVRAMRect(r.x,r.y,r.w,r.h); }
void NativeRenderer_SwapWindow(void) {}
void NativeRenderer_DebugDumpVRAM(int x,int y,int w,int h,const char *tag) { (void)x;(void)y;(void)w;(void)h;(void)tag; }
void NativeRenderer_DebugDumpVRAMRaw(const char *tag) { (void)tag; }
void NativeRenderer_PushDebugLabel(const char *label) { (void)label; }
void NativeRenderer_PopDebugLabel(void) {}
void NativeRenderer_SaveVRAM(const char *path,int x,int y,int w,int h,int framebuffer)
{
    (void)framebuffer;if(!XvValidRect(x,y,w,h))return;XvSyncCPU();FILE *file=fopen(path,"wb");if(!file)return;
    unsigned char header[18]={0};header[2]=2;header[12]=w;header[13]=w>>8;header[14]=h;header[15]=h>>8;header[16]=24;header[17]=0x20;
    fwrite(header,1,18,file);
    for(int row=y;row<y+h;row++)for(int col=x;col<x+w;col++){
        u16 color=xv.pixels[row*1024+col];unsigned char bgr[3]={(color>>10&31)*255/31,(color>>5&31)*255/31,(color&31)*255/31};fwrite(bgr,1,3,file);
    }fclose(file);
}
static void XvClearDiagnosticTarget(XvTarget *target)
{
    XvLayout(target,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkClearColorValue zero={{0,0,0,0}};
    VkImageSubresourceRange range={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    vkCmdClearColorImage(xv.command,target->image,target->layout,&zero,1,&range);
    target->clearStencil=1;
}

/* One boot-only check of actual GPU pixels, never inferred from frame counts.
 * Four known colors exercise packed uploads, palette lookups and vertex fetch.
 * Keep this off-screen; restore the CPU VRAM and renderer state afterwards. */
/* Independent bit-based reference for the diagnostic color/index sweeps.
 * Unlike the old uniform guard test, every lane and many STP/color carries
 * vary across the image. Constant row UVs also exercise boundary stability. */
static unsigned XvSweepWord(unsigned format,unsigned row,unsigned u,unsigned v)
{
    if(format==TF_16_BIT)return ((v&255)<<8)|(u&255);
    return (row<<8)+(format==TF_4_BIT?(u&15)*17:(u&255));
}
static void XvSweepExpected(unsigned format,unsigned filtering,unsigned row,unsigned x,float rgb[3])
{
    float span=format==TF_4_BIT?16.0f:255.0f;
    float u=(x+0.5f)*span/256.0f+1.0f/4096.0f;
    float v=(format==TF_16_BIT?(float)row:0.0f)+1.0f/4096.0f;
    /* Filtered taps keep inside the strip's texel range, whose U maximum is
     * exclusive and whose V is constant along the row. */
    if(filtering){if(u>span-1.0f)u=span-1.0f;v=floorf(v);}
    unsigned tx=(unsigned)floorf(u),ty=(unsigned)floorf(v);
    unsigned nearest=XvSweepWord(format,row,tx,ty);
    rgb[0]=rgb[1]=rgb[2]=0;
    if(!nearest)return;
    float coverage=0,fx=filtering?u-floorf(u):0,fy=filtering?v-floorf(v):0;
    for(unsigned dy=0;dy<2;dy++)for(unsigned dx=0;dx<2;dx++){
        unsigned word=XvSweepWord(format,row,tx+dx,ty+dy);
        float weight=(dx?fx:1-fx)*(dy?fy:1-fy);
        if(!word)continue;
        coverage+=weight;
        for(unsigned channel=0;channel<3;channel++)rgb[channel]+=((word>>(5*channel))&31)*(weight/31.0f);
    }
    if(coverage<0.0001f)coverage=0.0001f;
    for(unsigned channel=0;channel<3;channel++)rgb[channel]=rgb[channel]/coverage*255.0f;
}
static void XvColorSweep(void)
{
    GrVertex vertices[256*6]={0};
    xv.offscreen=1;xv.offRect=(RECT16){0,0,256,256};xv.drawPrim=1;xv.blend=BM_NONE;
    xv.state.rect[2]=xv.state.rect[3]=256;
    memset(xv.state.flags,0,sizeof(xv.state.flags));xv.state.flags[2]=1;
    for(unsigned check=34;check<40;check++){
        unsigned format=(check-34)%3,filtering=check>=37;
        memset(xv.pixels,0,sizeof(xv.pixels));
        for(unsigned row=0;row<256;row++){
            if(format==TF_16_BIT){
                for(unsigned x=0;x<256;x++)xv.pixels[row*1024+x]=(row<<8)|x;
            }else{
                for(unsigned x=0;x<(format==TF_4_BIT?64u:128u);x++){
                    unsigned packed=0;
                    if(format==TF_4_BIT)for(unsigned lane=0;lane<4;lane++)packed|=((x*4+lane)&15)<<(lane*4);
                    else packed=((x*2)&255)|(((x*2+1)&255)<<8);
                    xv.pixels[row*1024+512+x]=(u16)packed;
                }
                for(unsigned i=0;i<(format==TF_4_BIT?16u:256u);i++)
                    xv.pixels[(256+row)*1024+i]=(u16)((row<<8)+(format==TF_4_BIT?i*17:i));
            }
            const unsigned right[6]={0,1,0,0,1,1},bottom[6]={0,0,1,1,0,1};
            for(unsigned i=0;i<6;i++){
                GrVertex *vertex=&vertices[row*6+i];
                vertex->x=right[i]*256;vertex->y=row+bottom[i];
                vertex->u=right[i]*(format==TF_4_BIT?16:255);vertex->v=format==TF_16_BIT?row:0;
                vertex->page=format==TF_16_BIT?0:8;vertex->clut=(256+row)*64;
                vertex->bright=1;vertex->r=vertex->g=vertex->b=vertex->a=255;
            }
        }
        NativeRenderer_SetTexture(NativeRenderer_GetVRAMTexture(),(TexFormat)format);
        xv.vramCPUChanged=1;NativeRenderer_UpdateVRAM();xv.off.clearStencil=1;XvPass(&xv.off);
        VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,.clearValue.color.float32={0,0,0,0}};
        VkClearRect rect={.rect={{0,0},{256,256}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
        NativeRenderer_UpdateVertexBuffer(vertices,256*6);XvDrawTriangles(0,256*2,filtering);XvReadTarget(&xv.off);
        unsigned bad=0,firstX=0,firstY=0;unsigned char firstRGB[3]={0};float firstExpected[3]={0};
        for(unsigned y=0;y<256;y++)for(unsigned x=0;x<256;x++){
            float expected[3];XvSweepExpected(format,filtering,y,x,expected);
            unsigned char *pixel=xv.staging.map+4*(y*xv.off.width+x);
            if(fabsf(pixel[0]-expected[0])>2 || fabsf(pixel[1]-expected[1])>2 || fabsf(pixel[2]-expected[2])>2){
                if(!bad){firstX=x;firstY=y;memcpy(firstRGB,pixel,3);memcpy(firstExpected,expected,sizeof(expected));}
                bad++;
            }
        }
        float center[3];XvSweepExpected(format,filtering,128,128,center);
        unsigned char *sample=xv.staging.map+4*(128*xv.off.width+128);
        Platform_Log("[vulkan-check] check=%u format=%u filter=%u wrong=%u/%u sample=%u,%u,%u expected=%u,%u,%u kind=color-sweep blend=0\n",
            check,format,filtering,bad,65536u,sample[0],sample[1],sample[2],(unsigned)(center[0]+0.5f),(unsigned)(center[1]+0.5f),(unsigned)(center[2]+0.5f));
        if(bad)Platform_Log("[vulkan-sweep] check=%u first=%u,%u got=%u,%u,%u expected=%.1f,%.1f,%.1f\n",
            check,firstX,firstY,firstRGB[0],firstRGB[1],firstRGB[2],firstExpected[0],firstExpected[1],firstExpected[2]);
    }
}
/* Game-like meshes: thousands of small jittered triangles at integral PSX
 * vertices through the world projection onto the 720p main target. Check 40
 * adds 64 per covering triangle to find raster gaps/overlaps at shared edges
 * and vertices. Checks 41-44 map every triangle onto a red 64x64 texel square
 * surrounded by transparent texels over a blue background: any blue is a
 * sample outside the triangles' own UVs. 41/42 start at UV 0 (edge clamp);
 * 43/44 start at 64, which no clamp hides, measuring raw UV drift. 45 ends
 * each filtered range exclusively on opaque blue texels, as PSX data does:
 * any blue there is filtering blending the next image in the page. */
static void XvMeshCheck(void)
{
    enum {COLUMNS=72,ROWS=44,LEFT=102,RIGHT=1178,TOP=69,BOTTOM=651,COUNT=COLUMNS*ROWS*6};
    static s16 gridX[(COLUMNS+1)*(ROWS+1)],gridY[(COLUMNS+1)*(ROWS+1)];
    GrVertex *vertices=malloc(COUNT*sizeof(*vertices));
    if(!vertices){Platform_Log("[vulkan-check] mesh fixture allocation failed\n");return;}
    unsigned seed=0x2545f491u;
    for(unsigned row=0;row<=ROWS;row++)for(unsigned col=0;col<=COLUMNS;col++){
        int jitter=row>0 && row<ROWS && col>0 && col<COLUMNS;
        seed=seed*1664525u+1013904223u;
        gridX[row*(COLUMNS+1)+col]=(s16)(40+col*6+(jitter?(int)(seed>>30)%3-1:0));
        gridY[row*(COLUMNS+1)+col]=(s16)(20+row*4+(jitter?(int)((seed>>27)&3)%3-1:0));
    }
    xv.offscreen=0;xv.drawPrim=1;xv.clipEnabled=0;xv.ui=0;
    xv.state.rect[2]=512;xv.state.rect[3]=216;memset(xv.state.flags,0,sizeof(xv.state.flags));
    for(unsigned check=40;check<46;check++){
        unsigned flat=check==40,filtering=check==42 || check>=44,base=check>=43?64:0,fringe=check==45;
        memset(xv.pixels,0,sizeof(xv.pixels));
        xv.pixels[480*1024+1]=0x001f;xv.pixels[480*1024+2]=0x7c00;
        for(unsigned v=base;v<base+64+fringe;v++)for(unsigned u=base;u<base+64+fringe;u++)
            xv.pixels[v*1024+512+u/4]|=(u16)((u<base+64 && v<base+64?1u:2u)<<((u&3)*4));
        seed=0x9e3779b9u;
        for(unsigned cell=0;cell<COLUMNS*ROWS;cell++){
            unsigned col=cell%COLUMNS,row=cell/COLUMNS,corner[4]={row*(COLUMNS+1)+col,row*(COLUMNS+1)+col+1,(row+1)*(COLUMNS+1)+col,(row+1)*(COLUMNS+1)+col+1};
            seed=seed*1664525u+1013904223u;
            const unsigned order[2][6]={{0,1,2,2,1,3},{0,1,3,0,3,2}};
            for(unsigned i=0;i<6;i++){
                unsigned c=order[seed>>31][i];GrVertex *vertex=&vertices[cell*6+i];
                memset(vertex,0,sizeof(*vertex));
                vertex->x=gridX[corner[c]];vertex->y=gridY[corner[c]];
                vertex->u=(u8)(base+(c&1)*(63+fringe));vertex->v=(u8)(base+(c>>1)*(63+fringe));
                vertex->page=8;vertex->clut=480*64;vertex->bright=1;
                vertex->r=vertex->g=vertex->b=flat?64:255;vertex->a=255;
            }
        }
        NativeRenderer_SetTexture(flat?NativeRenderer_GetWhiteTexture():NativeRenderer_GetVRAMTexture(),TF_4_BIT);
        xv.blend=flat?BM_ADD:BM_NONE;
        xv.vramCPUChanged=1;NativeRenderer_UpdateVRAM();xv.main.clearStencil=1;XvPass(&xv.main);
        VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,.clearValue.color.float32={0,0,flat?0:1,0}};
        VkClearRect rect={.rect={{0,0},{XV_WIDTH,XV_HEIGHT}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
        NativeRenderer_UpdateVertexBuffer(vertices,COUNT);XvDrawTriangles(0,COUNT/3,filtering);XvReadTarget(&xv.main);
        unsigned bad=0,blue=0,firstX=0,firstY=0;unsigned char firstRGB[3]={0};
        for(unsigned y=TOP;y<BOTTOM;y++)for(unsigned x=LEFT;x<RIGHT;x++){
            unsigned char *pixel=xv.staging.map+4*(y*xv.main.width+x);
            int wrong=flat?abs(pixel[0]-64)>2 || abs(pixel[1]-64)>2 || abs(pixel[2]-64)>2:pixel[0]<200 || pixel[1]>16 || pixel[2]>16;
            if(!wrong)continue;
            if(!bad){firstX=x;firstY=y;memcpy(firstRGB,pixel,3);}
            bad++;blue+=flat?pixel[2]<32:pixel[2]>128;
        }
        unsigned char *sample=xv.staging.map+4*(360*xv.main.width+640);
        Platform_Log("[vulkan-check] check=%u format=%u filter=%u wrong=%u/%u sample=%u,%u,%u expected=%u,%u,%u kind=%s blend=%u\n",
            check,0u,filtering,bad,(unsigned)((RIGHT-LEFT)*(BOTTOM-TOP)),sample[0],sample[1],sample[2],flat?64u:255u,flat?64u:0u,flat?64u:0u,
            flat?"mesh-coverage":fringe?"uv-fringe":base?"uv-drift":"uv-edge",(unsigned)xv.blend);
        if(bad)Platform_Log("[vulkan-mesh] check=%u first=%u,%u got=%u,%u,%u %s=%u other=%u\n",
            check,firstX,firstY,firstRGB[0],firstRGB[1],firstRGB[2],flat?"gaps":"blue",blue,bad-blue);
    }
    free(vertices);
}
static void XvColorCheck(void)
{
    const u16 colors[]={0x001f,0x03e0,0x7c00,0x7fff};
    GrVertex vertices[6]={0};
    const unsigned xy[6][2]={{0,0},{32,0},{0,32},{0,32},{32,0},{32,32}};
    for(unsigned i=0;i<6;i++){
        vertices[i].x=vertices[i].u=xy[i][0];vertices[i].y=vertices[i].v=xy[i][1];
        vertices[i].clut=128*64;vertices[i].bright=1;
        vertices[i].r=vertices[i].g=vertices[i].b=vertices[i].a=255;
    }
    xv.offscreen=1;xv.offRect=(RECT16){0,0,32,32};xv.drawPrim=1;
    xv.state.rect[2]=xv.state.rect[3]=32;
    // Start with direct color, then repeat every format with both shaders.
    // A failed first draw must not be misidentified as a 4-bit-only failure.
    const unsigned formats[]={2,0,1,0,1,2,0,1,2,0,1,2,0,0,1,2,0,1,2,0,0,0,0,0,0,1,2,0,1,2,0,1,0,1};
    const unsigned blendExpected[5][3]={{96,64,32},{80,80,80},{160,160,160},{0,32,96},{88,112,136}};
    for(unsigned check=0;check<sizeof(formats)/sizeof(formats[0]);check++){
        unsigned stress=check>=30;
        unsigned format=formats[check],filtering=(check>=6 && check<13) || (check>=16 && check<24) || (check>=27 && check<30) || check>=32;
        unsigned modulation=(check>=13 && check<19) || check>=24,blending=check>=19 && check<24;
        unsigned flat=(check>=9 && check<13) || blending;
        xv.offscreen=check<24;
        memset(xv.pixels,0,sizeof(xv.pixels));
        for(unsigned i=0;i<4;i++)xv.pixels[128*1024+i]=modulation?0x3def:colors[i];
        for(unsigned y=0;y<32;y++)for(unsigned x=0;x<32;x++)
            xv.pixels[y*1024+x]=format==0?0x3210:format==1?((x&1)?0x0302:0x0100):modulation?0x3def:colors[x&3];
        if(stress){
            /* A skewed, screen-filling surface with varying UVs and a CLUT
             * at the far right. Every valid texel is orange; guards are blue.
             * Small aligned fixtures do not exercise these interpolation and
             * dependent-read conditions. Keep its background blue too. */
            for(unsigned i=0;i<1024*512;i++)xv.pixels[i]=0x7c00;
            for(unsigned y=0;y<256;y++)for(unsigned x=0;x<(format?128u:64u);x++)
                xv.pixels[(256+y)*1024+((960+x)&1023)]=format?0x0101:0x1111;
            xv.pixels[128*1024+1009]=0x3def;
            const int slope[6][2]={{-47,-13},{517,23},{29,229},{29,229},{517,23},{551,247}};
            const unsigned uv[6][2]={{2,1},{253,7},{9,249},{9,249},{253,7},{251,255}};
            for(unsigned i=0;i<6;i++){
                vertices[i].x=slope[i][0];vertices[i].y=slope[i][1];vertices[i].u=uv[i][0];vertices[i].v=uv[i][1];
                vertices[i].page=31;vertices[i].clut=128*64+63;
            }
            xv.state.rect[2]=512;xv.state.rect[3]=216;
        }
        /* Exercise the public texture contract as game splits do. Flat
         * polygons must ignore both a stale tpage and non-white VRAM. */
        NativeRenderer_SetTexture(flat && check!=12?NativeRenderer_GetWhiteTexture():NativeRenderer_GetVRAMTexture(),(TexFormat)format);
        g_dbg_texturelessMode=check==12;
        xv.blend=blending?(BlendMode)(check-19):BM_NONE;
        for(unsigned i=0;i<6;i++){
            vertices[i].bright=modulation?2:1;
            vertices[i].r=blending?96:flat?64:255;
            vertices[i].g=blending?64:flat?128:modulation?96:255;
            vertices[i].b=blending?32:flat?192:modulation?32:255;
        }
        xv.vramCPUChanged=1;
        xv.off.clearStencil=1;
        if(!xv.offscreen)xv.main.clearStencil=1;
        if(blending || stress){
            NativeRenderer_UpdateVRAM();XvPass(stress?&xv.main:&xv.off);
            VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.colorAttachment=0,
                .clearValue.color.float32={stress?0:64/255.0f,stress?0:96/255.0f,stress?1:128/255.0f,0}};
            VkClearRect rect={.rect={{0,0},{stress?XV_WIDTH:32,stress?XV_HEIGHT:32}},.layerCount=1};
            vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
        }
        NativeRenderer_UpdateVertexBuffer(vertices,6);XvDrawTriangles(0,2,filtering);
        XvTarget *checked=xv.offscreen?&xv.off:&xv.main;
        XvReadTarget(checked);
        unsigned bad=0,total=0;
        for(unsigned y=stress?96:1;y<(stress?624:31);y++)for(unsigned x=stress?160:1;x<(stress?1120:31);x++){
            total++;
            unsigned color=colors[x&3],next=colors[(x+1)&3];unsigned char *pixel=xv.staging.map+4*(y*checked->width+x);
            unsigned expected[3]={(color&31)*255/31,((color>>5)&31)*255/31,((color>>10)&31)*255/31};
            if(blending)memcpy(expected,blendExpected[check-19],sizeof(expected));
            else if(modulation){expected[0]=247;expected[1]=93;expected[2]=31;}
            else if(flat){expected[0]=64;expected[1]=128;expected[2]=192;}
            else if(filtering)for(unsigned channel=0;channel<3;channel++)
                expected[channel]=(expected[channel]+((next>>(5*channel))&31)*255/31+1)/2;
            if(abs((int)pixel[0]-(int)expected[0])>1 || abs((int)pixel[1]-(int)expected[1])>1 || abs((int)pixel[2]-(int)expected[2])>1)bad++;
        }
        unsigned char *sample=xv.staging.map+4*((stress?360:4)*checked->width+(stress?640:4));
        const unsigned *expectedSample=blending?blendExpected[check-19]:modulation?(const unsigned[]){247,93,31}:flat?(const unsigned[]){64,128,192}:filtering?(const unsigned[]){128,128,0}:(const unsigned[]){255,0,0};
        Platform_Log("[vulkan-check] check=%u format=%u filter=%u wrong=%u/%u sample=%u,%u,%u expected=%u,%u,%u kind=%s blend=%u\n",
            check,format,filtering,bad,total,sample[0],sample[1],sample[2],expectedSample[0],expectedSample[1],expectedSample[2],
            stress?"raster-stress":blending?"blend":modulation?(xv.offscreen?"modulated":"main-modulated"):check==12?"debug-flat":flat?"flat":"textured",(unsigned)xv.blend);
    }
    XvColorSweep();
    XvMeshCheck();
    g_dbg_texturelessMode=0;xv.blend=BM_NONE;
    memset(xv.pixels,0,sizeof(xv.pixels));xv.vramCPUChanged=1;xv.vramGPUChanged=0;
    xv.offscreen=0;xv.drawPrim=0;xv.texture=NativeRenderer_GetVRAMTexture();xv.format=TF_4_BIT;xv.vertexCursor=0;xv.vertexCount=0;
    xv.mainValid=xv.mainResolved=0;
    // Both passes LOAD their color attachment. Do not leave test patterns for
    // the game's first partial screen update to expose during scene startup.
    XvClearDiagnosticTarget(&xv.main);XvClearDiagnosticTarget(&xv.off);
    memset(&xv.state,0,sizeof(xv.state));xv.state.rect[2]=512;xv.state.rect[3]=216;xv.state.scale[0]=1;
    NativeRenderer_UpdateVRAM();XvSubmit();memset(&xvCost,0,sizeof(xvCost));
}

static void XvDestroyTarget(XvTarget *t)
{
    if(t->framebuffer)vkDestroyFramebuffer(xv.device,t->framebuffer,NULL);
    if(t->depthView)vkDestroyImageView(xv.device,t->depthView,NULL);
    if(t->depth)vkDestroyImage(xv.device,t->depth,NULL);
    if(t->depthMemory)vkFreeMemory(xv.device,t->depthMemory,NULL);
    if(t->view)vkDestroyImageView(xv.device,t->view,NULL);
    if(t->memory){vkDestroyImage(xv.device,t->image,NULL);vkFreeMemory(xv.device,t->memory,NULL);}
}
void NativeRenderer_Shutdown(void)
{
    if(!xv.device)return;XvSubmit();vkDeviceWaitIdle(xv.device);
    for(unsigned p=0;p<3;p++)for(unsigned q=0;q<18;q++)for(unsigned b=0;b<5;b++)for(unsigned st=0;st<3;st++)
        if(xv.pipelines[p][q][b][st])vkDestroyPipeline(xv.device,xv.pipelines[p][q][b][st],NULL);
    for(unsigned i=0;i<20;i++)if(xv.shaders[i])vkDestroyShaderModule(xv.device,xv.shaders[i],NULL);
    XvDestroyTarget(&xv.main);XvDestroyTarget(&xv.off);XvDestroyTarget(&xv.vram);
    for(unsigned i=0;i<xv.imageCount;i++)XvDestroyTarget(&xv.swap[i]);
    XvBuffer *buffers[]={&xv.vertices,&xv.uniforms,&xv.staging};
    for(unsigned i=0;i<3;i++){vkUnmapMemory(xv.device,buffers[i]->memory);vkDestroyBuffer(xv.device,buffers[i]->buffer,NULL);vkFreeMemory(xv.device,buffers[i]->memory,NULL);}
    vkDestroyDescriptorPool(xv.device,xv.descriptors,NULL);vkDestroySampler(xv.device,xv.sampler,NULL);vkDestroySampler(xv.device,xv.linearSampler,NULL);
    vkDestroySampler(xv.device,xv.vramSampler,NULL);
    vkDestroyPipelineLayout(xv.device,xv.pipelineLayout,NULL);vkDestroyDescriptorSetLayout(xv.device,xv.setLayout,NULL);
    for(unsigned i=0;i<4;i++)vkDestroyRenderPass(xv.device,xv.passes[i],NULL);
    for(unsigned i=0;i<2;i++)vkDestroyFence(xv.device,xv.fences[i],NULL);
    vkDestroyFence(xv.device,xv.acquireFence,NULL);vkDestroyCommandPool(xv.device,xv.pool,NULL);
    if(xv.timestamps)vkDestroyQueryPool(xv.device,xv.timestamps,NULL);
    vkDestroySwapchainKHR(xv.device,xv.swapchain,NULL);vkDestroyDevice(xv.device,NULL);
    vkDestroySurfaceKHR(xv.instance,xv.surface,NULL);vkDestroyInstance(xv.instance,NULL);memset(&xv,0,sizeof(xv));
}
