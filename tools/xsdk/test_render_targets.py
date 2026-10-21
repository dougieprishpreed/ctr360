"""Execute the backend's target creation with a strict Vulkan call recorder.
Reject the formerly unsupported tiny attachment as a negative control.
This validates host-side resource requests, not GPU rendering.
"""
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2];s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
body=s[s.index('static void XvImage('):s.index('static VkPipeline XvPipeline(')]
structure=re.search(r'typedef struct \{\s*VkImage image;.*?} XvTarget;',s,re.S).group(0)
calls=re.findall(r'XvImage\(&xv\.\w+,[^;]+;',s)
assert len(calls)==3,calls
c=r"""
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
"""+structure+r"""
enum {XV_WIDTH=1280,XV_HEIGHT=720};
static struct {VkDevice device;VkCommandBuffer command;VkRenderPass passes[3];XvTarget main,off,vram;} xv;
static unsigned images,framebuffers,colorClears,depthClears;
#define XV_CALL(call) do { if((call)!=VK_SUCCESS)exit(42); } while(0)
static void XvLayout(XvTarget *t,VkImageLayout l){t->layout=l;}
VkResult vkCreateImage(VkDevice d,const VkImageCreateInfo *i,const VkAllocationCallbacks *a,VkImage *out){
 (void)d;(void)a;
 assert(i->mipLevels==1 && i->arrayLayers==1 && i->samples==VK_SAMPLE_COUNT_1_BIT);
 if((i->usage&VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT) && (i->extent.width<=16 || i->extent.height<=16))return VK_ERROR_FEATURE_NOT_PRESENT;
 assert(i->extent.width && i->extent.height);*out=(VkImage)(uintptr_t)++images;return VK_SUCCESS;
}
void vkGetImageMemoryRequirements(VkDevice d,VkImage i,VkMemoryRequirements *r){(void)d;(void)i;*r=(VkMemoryRequirements){4096,4096,1};}
VkResult vkAllocateMemory(VkDevice d,const VkMemoryAllocateInfo *i,const VkAllocationCallbacks *a,VkDeviceMemory *m){(void)d;(void)a;assert(i->allocationSize==4096);*m=(VkDeviceMemory)1;return VK_SUCCESS;}
VkResult vkBindImageMemory(VkDevice d,VkImage i,VkDeviceMemory m,VkDeviceSize o){(void)d;assert(i && m && o==0);return VK_SUCCESS;}
VkResult vkCreateImageView(VkDevice d,const VkImageViewCreateInfo *i,const VkAllocationCallbacks *a,VkImageView *v){(void)d;(void)a;assert(i->image);*v=(VkImageView)i->image;return VK_SUCCESS;}
VkResult vkCreateFramebuffer(VkDevice d,const VkFramebufferCreateInfo *i,const VkAllocationCallbacks *a,VkFramebuffer *f){(void)d;(void)a;assert(i->width>16 && i->height>16);assert(i->attachmentCount>=1 && i->attachmentCount<=2);*f=(VkFramebuffer)(uintptr_t)++framebuffers;return VK_SUCCESS;}
void vkCmdClearColorImage(VkCommandBuffer b,VkImage i,VkImageLayout l,const VkClearColorValue *c,uint32_t n,const VkImageSubresourceRange *r){(void)b;assert(i && l==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && n==1 && r->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT);assert(c->float32[0]==0);colorClears++;}
void vkCmdClearDepthStencilImage(VkCommandBuffer b,VkImage i,VkImageLayout l,const VkClearDepthStencilValue *c,uint32_t n,const VkImageSubresourceRange *r){(void)b;assert(i && l==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && n==1);assert(c->depth==1 && c->stencil==0);assert(r->aspectMask==(VK_IMAGE_ASPECT_DEPTH_BIT|VK_IMAGE_ASPECT_STENCIL_BIT));depthClears++;}
void vkCmdPipelineBarrier(VkCommandBuffer b,VkPipelineStageFlags s,VkPipelineStageFlags d,VkDependencyFlags f,uint32_t nm,const VkMemoryBarrier *m,uint32_t nb,const VkBufferMemoryBarrier *bb,uint32_t ni,const VkImageMemoryBarrier *i){(void)b;(void)s;(void)d;(void)f;(void)nm;(void)m;(void)nb;(void)bb;assert(ni==1 && i->image);}
"""+body+'\nint main(int argc,char **argv){(void)argv;\n'+''.join(calls)+r"""
 assert(images==5 && framebuffers==3 && colorClears==3 && depthClears==2);
 if(argc>1){XvTarget old={0};XvImage(&old,1,1,0);return 1;}
 puts("PASS: actual target creation/initialization; 3 color, 2 depth; tiny-target rejection reproduced");return 0;
}
"""
source=a.out/'targets.c';source.write_text(c);exe=(a.out/'targets-test').resolve()
subprocess.run(['cc','-std=gnu17','-I',str(a.vulkan/'third_party/vulkan-headers/include'),str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
assert subprocess.run([str(exe),'old-white-target']).returncode==42
