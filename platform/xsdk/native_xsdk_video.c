/* Experimental Vulkan 1.0 backend for xSDK/vulkan4xenon.
 * PSX textures remain packed bytes; only decoded color is filtered. Submission
 * is serialized for bring-up, with all upload storage retained until its fence.
 */
#include <vulkan/vulkan.h>
#include <vulkan4xenon.h>
#include <platform/native_renderer.h>
#include <platform/native_log.h>
#include <platform/native_config.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ctr_shaders.h"

enum { XV_WIDTH=1280,XV_HEIGHT=720,XV_VERTEX_BYTES=16*1024*1024,XV_UNIFORM_BYTES=2*1024*1024 };
typedef struct { VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;size_t size; } XvBuffer;
typedef struct {
    VkImage image;VkDeviceMemory memory;VkImageView view;
    VkImage depth;VkDeviceMemory depthMemory;VkImageView depthView;
    VkFramebuffer framebuffer;VkImageLayout layout;
    unsigned width,height,pass;
} XvTarget;
typedef struct { float rect[4],scale[4],flags[4],source[4]; } XvUniform;
typedef struct { float position[4],tc[4],color[4],extra[4]; } XvVertex;
static struct {
    VkInstance instance;VkPhysicalDevice physical;VkDevice device;VkQueue queue;
    VkSurfaceKHR surface;VkSwapchainKHR swapchain;unsigned imageCount;
    XvTarget swap[3],main,off,vram,white;
    VkRenderPass passes[3];VkCommandPool pool;VkCommandBuffer command;VkFence fence;
    VkDescriptorSetLayout setLayout;VkPipelineLayout pipelineLayout;VkDescriptorPool descriptors;
    VkDescriptorSet sets[5];VkSampler sampler,linearSampler;
    VkShaderModule shaders[4];VkPipeline pipelines[3][2][5][3];
    XvBuffer vertices,uniforms,staging;
    unsigned vertexCursor,vertexBase,vertexCount,uniformCursor,uniformAlignment;
    XvTarget *target;int recording,inPass;
    XvUniform state;VkRect2D scissor;int clipEnabled,ui,offscreen,drawPrim;
    RECT16 offRect;BlendMode blend;TexFormat format;TextureID texture;
    int mainValid,mainResolved,vramCPUChanged,vramGPUChanged;
    u16 pixels[1024*512],move[1024*512];
} xv;
int g_windowWidth=1280,g_windowHeight=720;
static int xvEdgeAA=1;
int g_dbg_wireframeMode=0,g_dbg_texturelessMode=0,g_cfg_bilinearFiltering=1;
static void XvCheck(VkResult result,const char *operation)
{
    if(result!=VK_SUCCESS) { Platform_LogError("[vulkan] %s failed: %d\n",operation,(int)result);Platform_Exit(1); }
}
#define XV_CALL(call) XvCheck((call),#call)
static void XvBufferCreate(XvBuffer *buffer,size_t bytes,VkBufferUsageFlags usage)
{
    VkBufferCreateInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=bytes,.usage=usage};
    XV_CALL(vkCreateBuffer(xv.device,&info,NULL,&buffer->buffer));
    VkMemoryRequirements requirements;vkGetBufferMemoryRequirements(xv.device,buffer->buffer,&requirements);
    VkMemoryAllocateInfo allocate={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=requirements.size};
    XV_CALL(vkAllocateMemory(xv.device,&allocate,NULL,&buffer->memory));
    XV_CALL(vkBindBufferMemory(xv.device,buffer->buffer,buffer->memory,0));
    XV_CALL(vkMapMemory(xv.device,buffer->memory,0,VK_WHOLE_SIZE,0,(void **)&buffer->map));buffer->size=bytes;
}
static void XvBegin(void)
{
    if(xv.recording)return;
    VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    XV_CALL(vkBeginCommandBuffer(xv.command,&begin));xv.recording=1;
}
static void XvEndPass(void) { if(xv.inPass){vkCmdEndRenderPass(xv.command);xv.inPass=0;} }
static void XvSubmit(void)
{
    if(!xv.recording)return;
    XvEndPass();XV_CALL(vkEndCommandBuffer(xv.command));
    VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&xv.command};
    VkMappedMemoryRange ranges[2]={
        {.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.vertices.memory,.size=VK_WHOLE_SIZE},
        {.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.uniforms.memory,.size=VK_WHOLE_SIZE}};
    if(xv.vertices.memory)XV_CALL(vkFlushMappedMemoryRanges(xv.device,2,ranges));
    XV_CALL(vkQueueSubmit(xv.queue,1,&submit,xv.fence));
    XV_CALL(vkWaitForFences(xv.device,1,&xv.fence,VK_TRUE,UINT64_MAX));
    XV_CALL(vkResetFences(xv.device,1,&xv.fence));
    XV_CALL(vkResetCommandBuffer(xv.command,0));
    xv.recording=0;xv.uniformCursor=0;
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
    VkRenderPassBeginInfo begin={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=xv.passes[target->pass],
        .framebuffer=target->framebuffer,.renderArea={{0,0},{target->width,target->height}}};
    vkCmdBeginRenderPass(xv.command,&begin,VK_SUBPASS_CONTENTS_INLINE);xv.inPass=1;
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
static VkPipeline XvPipeline(unsigned pass,int quad,BlendMode blend,int stencil)
{
    VkPipeline *cached=&xv.pipelines[pass][quad][blend][stencil];if(*cached)return *cached;
    VkPipelineShaderStageCreateInfo stages[2]={
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=xv.shaders[quad?2:0],.pName="main"},
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=xv.shaders[quad?3:1],.pName="main"}};
    VkVertexInputBindingDescription binding={0,sizeof(XvVertex),VK_VERTEX_INPUT_RATE_VERTEX};
    VkVertexInputAttributeDescription attrs[4];for(unsigned i=0;i<4;i++)attrs[i]=(VkVertexInputAttributeDescription){i,0,VK_FORMAT_R32G32B32A32_SFLOAT,i*16};
    VkPipelineVertexInputStateCreateInfo input={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
        .vertexBindingDescriptionCount=1,.pVertexBindingDescriptions=&binding,.vertexAttributeDescriptionCount=quad?1:4,.pVertexAttributeDescriptions=attrs};
    VkPipelineInputAssemblyStateCreateInfo assembly={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=quad?VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP:VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
    VkPipelineViewportStateCreateInfo viewport={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.scissorCount=1};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};
    VkPipelineMultisampleStateCreateInfo samples={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
    VkStencilOpState st={.failOp=VK_STENCIL_OP_KEEP,.passOp=stencil==1?VK_STENCIL_OP_REPLACE:VK_STENCIL_OP_KEEP,
        .depthFailOp=VK_STENCIL_OP_KEEP,.compareOp=stencil==1?VK_COMPARE_OP_ALWAYS:VK_COMPARE_OP_NOT_EQUAL,
        .compareMask=255,.writeMask=255,.reference=1};
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
    if(xv.uniformCursor+stride>XV_UNIFORM_BYTES){XvTarget *target=xv.target;XvSubmit();XvPass(target);}
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
    unsigned texture=from==&xv.vram?0:from==&xv.main?(mode==3?4:1):2;
    XvBindUniform(&state,texture);vkCmdBindPipeline(xv.command,VK_PIPELINE_BIND_POINT_GRAPHICS,XvPipeline(to->pass,1,BM_NONE,0));
    VkDeviceSize quadOffset=XV_VERTEX_BYTES;vkCmdBindVertexBuffers(xv.command,0,1,&xv.vertices.buffer,&quadOffset);
    vkCmdDraw(xv.command,4,1,0,0);
}
static void XvSyncCPU(void)
{
    if(!xv.vramGPUChanged)return;
    XvLayout(&xv.vram,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    VkBufferImageCopy region={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={1024,512,1}};
    vkCmdCopyImageToBuffer(xv.command,xv.vram.image,xv.vram.layout,xv.staging.buffer,1,&region);XvSubmit();
    VkMappedMemoryRange range={.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=xv.staging.memory,.size=VK_WHOLE_SIZE};
    XV_CALL(vkInvalidateMappedMemoryRanges(xv.device,1,&range));
    for(unsigned i=0;i<1024*512;i++)xv.pixels[i]=(u16)(xv.staging.map[4*i]|xv.staging.map[4*i+1]<<8);
    xv.vramGPUChanged=0;
}
void NativeRenderer_UpdateVRAM(void)
{
    if(!xv.vramCPUChanged)return;
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
    for(unsigned i=0;i<3;i++){
        VkAttachmentDescription attachments[2]={
            {.format=i==2?VK_FORMAT_B8G8R8A8_UNORM:VK_FORMAT_R8G8B8A8_UNORM,.samples=VK_SAMPLE_COUNT_1_BIT,
             .loadOp=VK_ATTACHMENT_LOAD_OP_LOAD,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,
             .stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL},
            {.format=VK_FORMAT_D24_UNORM_S8_UINT,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_LOAD,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,
             .stencilLoadOp=VK_ATTACHMENT_LOAD_OP_LOAD,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_STORE,
             .initialLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,.finalLayout=VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL}};
        VkAttachmentReference color={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL},depth={1,VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL};
        VkSubpassDescription subpass={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&color,.pDepthStencilAttachment=i==0?&depth:NULL};
        VkRenderPassCreateInfo info={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=i==0?2:1,.pAttachments=attachments,.subpassCount=1,.pSubpasses=&subpass};
        XV_CALL(vkCreateRenderPass(xv.device,&info,NULL,&xv.passes[i]));
    }
}
static void XvConfig(const char *section,const char *key,const char *value,void *context)
{
    (void)context;if(strcmp(section,"graphics"))return;
    if(strcmp(value,"0") && strcmp(value,"1"))return;
    int enabled=value[0]=='1';
    if(!strcmp(key,"interpolation"))g_nativeHDEnableInterpolation=enabled;
    if(!strcmp(key,"texture_filter"))g_cfg_bilinearFiltering=enabled;
    if(!strcmp(key,"edge_aa"))xvEdgeAA=enabled;
}
int NativeRenderer_InitialiseRender(char *name,int width,int height,int fullscreen)
{
    (void)name;(void)width;(void)height;(void)fullscreen;
    NativeConfig_Read("game:/ctr360.ini",XvConfig,NULL);
    const char *instanceExtensions[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_DISPLAY_EXTENSION_NAME};
    const char *deviceExtensions[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="ctr360 xSDK experimental",.apiVersion=VK_API_VERSION_1_0};
    VkInstanceCreateInfo instance={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app,.enabledExtensionCount=2,.ppEnabledExtensionNames=instanceExtensions};
    XV_CALL(vkCreateInstance(&instance,NULL,&xv.instance));unsigned count=1;XV_CALL(vkEnumeratePhysicalDevices(xv.instance,&count,&xv.physical));
    VkPhysicalDeviceProperties properties;vkGetPhysicalDeviceProperties(xv.physical,&properties);
    xv.uniformAlignment=properties.limits.minUniformBufferOffsetAlignment;
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
    VkCommandBufferAllocateInfo command={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=xv.pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    XV_CALL(vkAllocateCommandBuffers(xv.device,&command,&xv.command));
    VkFenceCreateInfo fence={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};XV_CALL(vkCreateFence(xv.device,&fence,NULL,&xv.fence));
    XvCreatePasses();
    for(unsigned i=0;i<xv.imageCount;i++){
        XvTarget *t=&xv.swap[i];t->image=images[i];t->width=XV_WIDTH;t->height=XV_HEIGHT;t->pass=2;
        VkImageViewCreateInfo view={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=t->image,.viewType=VK_IMAGE_VIEW_TYPE_2D,
            .format=VK_FORMAT_B8G8R8A8_UNORM,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
        XV_CALL(vkCreateImageView(xv.device,&view,NULL,&t->view));
        VkFramebufferCreateInfo fb={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=xv.passes[2],.attachmentCount=1,
            .pAttachments=&t->view,.width=XV_WIDTH,.height=XV_HEIGHT,.layers=1};XV_CALL(vkCreateFramebuffer(xv.device,&fb,NULL,&t->framebuffer));
    }
    XvImage(&xv.main,XV_WIDTH,XV_HEIGHT,1);XvImage(&xv.off,1024,512,1);XvImage(&xv.vram,1024,512,0);XvImage(&xv.white,1,1,0);
    XvBufferCreate(&xv.vertices,XV_VERTEX_BYTES+4*sizeof(XvVertex),VK_BUFFER_USAGE_VERTEX_BUFFER_BIT);
    XvVertex *quad=(XvVertex *)(xv.vertices.map+XV_VERTEX_BYTES);
    memset(quad,0,4*sizeof(*quad));quad[1].position[1]=1;quad[2].position[0]=1;quad[3].position[0]=1;quad[3].position[1]=1;
    XvBufferCreate(&xv.uniforms,XV_UNIFORM_BYTES,VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT);
    XvBufferCreate(&xv.staging,1024*512*4,VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT);
    VkDescriptorSetLayoutBinding bindings[]={
        {.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_VERTEX_BIT|VK_SHADER_STAGE_FRAGMENT_BIT},
        {.binding=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT}};
    VkDescriptorSetLayoutCreateInfo layout={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=2,.pBindings=bindings};
    XV_CALL(vkCreateDescriptorSetLayout(xv.device,&layout,NULL,&xv.setLayout));
    VkPipelineLayoutCreateInfo pl={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&xv.setLayout};XV_CALL(vkCreatePipelineLayout(xv.device,&pl,NULL,&xv.pipelineLayout));
    VkDescriptorPoolSize sizes[]={{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,5},{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,5}};
    VkDescriptorPoolCreateInfo dp={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=5,.poolSizeCount=2,.pPoolSizes=sizes};XV_CALL(vkCreateDescriptorPool(xv.device,&dp,NULL,&xv.descriptors));
    VkSamplerCreateInfo sampler={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_NEAREST,.minFilter=VK_FILTER_NEAREST,
        .mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE};
    XV_CALL(vkCreateSampler(xv.device,&sampler,NULL,&xv.sampler));
    sampler.minFilter=VK_FILTER_LINEAR;sampler.magFilter=VK_FILTER_LINEAR;
    XV_CALL(vkCreateSampler(xv.device,&sampler,NULL,&xv.linearSampler));
    XvTarget *textures[]={&xv.vram,&xv.main,&xv.off,&xv.white,&xv.main};
    for(unsigned i=0;i<5;i++){
        VkDescriptorSetAllocateInfo alloc={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=xv.descriptors,.descriptorSetCount=1,.pSetLayouts=&xv.setLayout};
        XV_CALL(vkAllocateDescriptorSets(xv.device,&alloc,&xv.sets[i]));
        VkDescriptorBufferInfo buffer={xv.uniforms.buffer,0,sizeof(XvUniform)};
        VkDescriptorImageInfo image={i==4?xv.linearSampler:xv.sampler,textures[i]->view,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        VkWriteDescriptorSet writes[]={
            {.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=xv.sets[i],.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,.pBufferInfo=&buffer},
            {.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=xv.sets[i],.dstBinding=1,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&image}};
        vkUpdateDescriptorSets(xv.device,2,writes,0,NULL);
    }
    const uint32_t *code[]={psx_vert_spirv,psx_frag_spirv,quad_vert_spirv,quad_frag_spirv};
    const unsigned bytes[]={PSX_VERT_SPIRV_BYTES,PSX_FRAG_SPIRV_BYTES,QUAD_VERT_SPIRV_BYTES,QUAD_FRAG_SPIRV_BYTES};
    for(unsigned i=0;i<4;i++){VkShaderModuleCreateInfo info={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=bytes[i],.pCode=code[i]};XV_CALL(vkCreateShaderModule(xv.device,&info,NULL,&xv.shaders[i]));}
    /* Pre-create the small state combinations outside the race frame loop. */
    for(unsigned blend=0;blend<5;blend++)for(unsigned mask=1;mask<3;mask++)XvPipeline(0,0,(BlendMode)blend,mask);
    for(unsigned pass=0;pass<3;pass++)XvPipeline(pass,1,BM_NONE,0);
    XvSubmit();xv.state.rect[2]=512;xv.state.rect[3]=216;xv.state.scale[0]=1;xv.vramCPUChanged=1;
    Platform_Log("[vulkan] 720p renderer initialized (experimental)\n");return 1;
}
int NativeRenderer_InitialisePSX(void) { return xv.device!=VK_NULL_HANDLE; }
void NativeRenderer_ResetDevice(void) {}
void NativeRenderer_UpdateSwapIntervalState(int interval) { (void)interval; }
void NativeRenderer_BeginScene(void)
{
    XvSubmit();xv.vertexCursor=0;xv.vertexCount=0;xv.mainValid=0;xv.mainResolved=0;xv.offscreen=0;
    NativeRenderer_UpdateVRAM();XvPass(&xv.main);
    VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_STENCIL_BIT,.clearValue.depthStencil={1,0}};
    VkClearRect rect={.rect={{0,0},{XV_WIDTH,XV_HEIGHT}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&rect);
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
    if(xv.vertexCursor+bytes>XV_VERTEX_BYTES){XvSubmit();xv.vertexCursor=0;}
    xv.vertexBase=xv.vertexCursor;xv.vertexCount=count;
    XvVertex *out=(XvVertex *)(xv.vertices.map+xv.vertexCursor);xv.vertexCursor+=bytes;
    for(int i=0;i<count;i++){
        const GrVertex *v=&vertices[i];out[i]=(XvVertex){
            {v->x,v->y,v->page,v->clut},{v->u,v->v,v->bright,v->dither},
            {v->r/255.0f,v->g/255.0f,v->b/255.0f,v->a/255.0f},{v->tcx,v->tcy,v->_p0,v->_p1}};
    }
}
void NativeRenderer_DrawTriangles(int first,int triangles)
{
    if(first<0 || triangles<=0 || (unsigned)first>xv.vertexCount || (unsigned)triangles>(xv.vertexCount-first)/3)return;
    NativeRenderer_UpdateVRAM();XvLayout(&xv.vram,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    XvTarget *target=xv.offscreen?&xv.off:&xv.main;XvPass(target);
    unsigned width=xv.offscreen?xv.offRect.w:XV_WIDTH,height=xv.offscreen?xv.offRect.h:XV_HEIGHT;
    XvReserveUniform();
    VkViewport viewport={0,0,(float)width,(float)height,0,1};VkRect2D clip={{0,0},{width,height}};
    if(xv.clipEnabled && !xv.offscreen)clip=xv.scissor;
    vkCmdSetViewport(xv.command,0,1,&viewport);vkCmdSetScissor(xv.command,0,1,&clip);
    xv.state.scale[0]=xv.ui && !xv.offscreen?0.75f:1.0f;xv.state.scale[1]=xv.state.rect[2]*0.5f;
    xv.state.scale[2]=xv.offscreen?1.0f:0.0f;xv.state.scale[3]=(float)xv.format;
    xv.state.flags[3]=g_cfg_bilinearFiltering && !xv.ui && !xv.offscreen;
    if(g_dbg_texturelessMode)xv.state.scale[3]=3;
    XvBindUniform(&xv.state,0);
    vkCmdBindPipeline(xv.command,VK_PIPELINE_BIND_POINT_GRAPHICS,XvPipeline(0,0,xv.blend,xv.drawPrim?1:2));
    VkDeviceSize offset=xv.vertexBase;vkCmdBindVertexBuffers(xv.command,0,1,&xv.vertices.buffer,&offset);
    vkCmdDraw(xv.command,triangles*3,1,first,0);if(!xv.offscreen)xv.mainValid=1;
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
}
void NativeRenderer_SetOffscreenState(const RECT16 *rect,int enabled)
{
    if(enabled && xv.offscreen && memcmp(rect,&xv.offRect,sizeof(*rect))==0)return;
    if(!enabled && !xv.offscreen)return;
    if(xv.offscreen)XvPack(&xv.off,xv.offRect.x,xv.offRect.y,xv.offRect.w,xv.offRect.h);
    xv.offscreen=enabled;
    if(enabled){
        if(!XvValidRect(rect->x,rect->y,rect->w,rect->h)){xv.offscreen=0;return;}
        xv.offRect=*rect;NativeRenderer_UpdateVRAM();
        XvQuad(&xv.off,&xv.vram,2,0,0,rect->w,rect->h,rect->x/1024.0f,rect->y/512.0f,rect->w/1024.0f,rect->h/512.0f);
        XvPass(&xv.off);VkClearAttachment clear={.aspectMask=VK_IMAGE_ASPECT_STENCIL_BIT,.clearValue.depthStencil={1,0}};
        VkClearRect cr={.rect={{0,0},{(unsigned)rect->w,(unsigned)rect->h}},.layerCount=1};vkCmdClearAttachments(xv.command,1,&clear,1,&cr);
    }else XvPass(&xv.main);
}
void NativeRenderer_StoreFrameBuffer(int x,int y,int w,int h)
{
    if(xv.offscreen)NativeRenderer_SetOffscreenState(&xv.offRect,0);
    xv.mainResolved=xv.mainValid;
    if(xv.mainValid && !g_nativeHDIntermediate)XvPack(&xv.main,x,y,w,h);
}
void NativeRenderer_PresentVRAMRect(int x,int y,int w,int h)
{
    if(w<=0 || h<=0)return;NativeRenderer_UpdateVRAM();XvSubmit();
    unsigned index=0;XV_CALL(vkAcquireNextImageKHR(xv.device,xv.swapchain,UINT64_MAX,VK_NULL_HANDLE,xv.fence,&index));
    XV_CALL(vkWaitForFences(xv.device,1,&xv.fence,VK_TRUE,UINT64_MAX));XV_CALL(vkResetFences(xv.device,1,&xv.fence));
    if(xv.mainResolved)XvQuad(&xv.swap[index],&xv.main,xvEdgeAA?3:0,0,0,XV_WIDTH,XV_HEIGHT,0,0,1,1);
    else XvQuad(&xv.swap[index],&xv.vram,2,0,0,XV_WIDTH,XV_HEIGHT,x/1024.0f,y/512.0f,w/1024.0f,h/512.0f);
    XvLayout(&xv.swap[index],VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);XvSubmit();
    VkPresentInfoKHR present={.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,.swapchainCount=1,.pSwapchains=&xv.swapchain,.pImageIndices=&index};
    XV_CALL(vkQueuePresentKHR(xv.queue,&present));
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
    for(unsigned p=0;p<3;p++)for(unsigned q=0;q<2;q++)for(unsigned b=0;b<5;b++)for(unsigned st=0;st<3;st++)
        if(xv.pipelines[p][q][b][st])vkDestroyPipeline(xv.device,xv.pipelines[p][q][b][st],NULL);
    for(unsigned i=0;i<4;i++)if(xv.shaders[i])vkDestroyShaderModule(xv.device,xv.shaders[i],NULL);
    XvDestroyTarget(&xv.main);XvDestroyTarget(&xv.off);XvDestroyTarget(&xv.vram);XvDestroyTarget(&xv.white);
    for(unsigned i=0;i<xv.imageCount;i++)XvDestroyTarget(&xv.swap[i]);
    XvBuffer *buffers[]={&xv.vertices,&xv.uniforms,&xv.staging};
    for(unsigned i=0;i<3;i++){vkUnmapMemory(xv.device,buffers[i]->memory);vkDestroyBuffer(xv.device,buffers[i]->buffer,NULL);vkFreeMemory(xv.device,buffers[i]->memory,NULL);}
    vkDestroyDescriptorPool(xv.device,xv.descriptors,NULL);vkDestroySampler(xv.device,xv.sampler,NULL);vkDestroySampler(xv.device,xv.linearSampler,NULL);
    vkDestroyPipelineLayout(xv.device,xv.pipelineLayout,NULL);vkDestroyDescriptorSetLayout(xv.device,xv.setLayout,NULL);
    for(unsigned i=0;i<3;i++)vkDestroyRenderPass(xv.device,xv.passes[i],NULL);
    vkDestroyFence(xv.device,xv.fence,NULL);vkDestroyCommandPool(xv.device,xv.pool,NULL);
    vkDestroySwapchainKHR(xv.device,xv.swapchain,NULL);vkDestroyDevice(xv.device,NULL);
    vkDestroySurfaceKHR(xv.instance,xv.surface,NULL);vkDestroyInstance(xv.instance,NULL);memset(&xv,0,sizeof(xv));
}
