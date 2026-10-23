"""Run actual allocation/pass setup against Vulkan recorders, without a GPU."""
import argparse, subprocess
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--vulkan',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
source=(root/'platform/xsdk/native_xsdk_video.c').read_text()
buffer=source[source.index('static void XvBufferCreate('):source.index('static void XvBegin(')]
passes=source[source.index('static void XvCreatePasses('):source.index('static void XvConfig(')]
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stddef.h>
typedef struct {VkBuffer buffer;VkDeviceMemory memory;unsigned char *map;size_t size;} XvBuffer;
static struct {VkDevice device;VkPhysicalDevice physical;VkRenderPass passes[4];} xv;
static unsigned mask=3,selected,pass;
#define XV_CALL(x) assert((x)==VK_SUCCESS)
VkResult vkCreateBuffer(VkDevice d,const VkBufferCreateInfo *i,const VkAllocationCallbacks *a,VkBuffer *b){*b=(VkBuffer)1;return VK_SUCCESS;}
void vkGetBufferMemoryRequirements(VkDevice d,VkBuffer b,VkMemoryRequirements *r){*r=(VkMemoryRequirements){4096,64,mask};}
void vkGetPhysicalDeviceMemoryProperties(VkPhysicalDevice d,VkPhysicalDeviceMemoryProperties *p){
 *p=(VkPhysicalDeviceMemoryProperties){.memoryTypeCount=2};
 p->memoryTypes[0].propertyFlags=VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
 p->memoryTypes[1].propertyFlags=p->memoryTypes[0].propertyFlags|VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
}
VkResult vkAllocateMemory(VkDevice d,const VkMemoryAllocateInfo *i,const VkAllocationCallbacks *a,VkDeviceMemory *m){selected=i->memoryTypeIndex;assert(mask&(1<<selected));*m=(VkDeviceMemory)1;return VK_SUCCESS;}
VkResult vkBindBufferMemory(VkDevice d,VkBuffer b,VkDeviceMemory m,VkDeviceSize o){return VK_SUCCESS;}
VkResult vkMapMemory(VkDevice d,VkDeviceMemory m,VkDeviceSize o,VkDeviceSize s,VkMemoryMapFlags f,void **p){*p=0;return VK_SUCCESS;}
VkResult vkCreateRenderPass(VkDevice d,const VkRenderPassCreateInfo *i,const VkAllocationCallbacks *a,VkRenderPass *p){
 assert(pass<4);assert(i->pAttachments[0].loadOp==VK_ATTACHMENT_LOAD_OP_LOAD);
 if(pass==0 || pass==3){
  assert(i->attachmentCount==2 && i->pSubpasses->pDepthStencilAttachment);
  VkAttachmentLoadOp load=pass==3?VK_ATTACHMENT_LOAD_OP_CLEAR:VK_ATTACHMENT_LOAD_OP_LOAD;
  assert(i->pAttachments[1].loadOp==load && i->pAttachments[1].stencilLoadOp==load);
 }else assert(i->attachmentCount==1 && !i->pSubpasses->pDepthStencilAttachment);
 *p=(VkRenderPass)(size_t)++pass;return VK_SUCCESS;
}
'''+buffer+passes+r'''
int main(void){
 XvBuffer b;
 XvBufferCreate(&b,2048,VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT);assert(selected==1);
 XvBufferCreate(&b,2048,VK_BUFFER_USAGE_VERTEX_BUFFER_BIT);assert(selected==0);
 XvBufferCreate(&b,2048,VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT);assert(selected==0);
 mask=1;XvBufferCreate(&b,2048,VK_BUFFER_USAGE_TRANSFER_SRC_BIT);assert(selected==0);
 XvCreatePasses();assert(pass==4);return 0;
}
'''
test=a.out/'memory.c';test.write_text(c)
exe=a.out/'memory-test'
subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(test),'-o',str(exe)],check=True)
subprocess.run([str(exe.resolve())],check=True)
print('PASS: cached staging, GPU vertex/uniform buffers, allowed-type fallback, paired clear/load stencil passes')
