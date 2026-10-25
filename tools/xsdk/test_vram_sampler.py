"""Record actual sampler/descriptor setup: packed VRAM wraps, display images clamp."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
s=(Path(__file__).resolve().parents[2]/'platform/xsdk/native_xsdk_video.c').read_text()
start=s.index('    VkSamplerCreateInfo sampler=')
body=s[start:s.index('    Platform_Log("[vulkan] descriptors ready',start)]
c=r'''
#include <vulkan/vulkan.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef struct {float rect[4],scale[4],flags[4],source[4];} XvUniform;
typedef struct {VkImageView view;} XvTarget;
static struct {VkDevice device;VkDescriptorPool descriptors;VkDescriptorSetLayout setLayout;
 VkDescriptorSet sets[4];VkSampler sampler,linearSampler,vramSampler;XvTarget vram,main,off;
 struct {VkBuffer buffer;} uniforms;} xv;
static VkSamplerCreateInfo samplers[4];static unsigned calls,sets,writes;
#define XV_CALL(x) assert((x)==VK_SUCCESS)
VkResult vkCreateSampler(VkDevice d,const VkSamplerCreateInfo *info,const VkAllocationCallbacks *a,VkSampler *p){
 assert(++calls<=3);samplers[calls]=*info;*p=(VkSampler)(uintptr_t)calls;return VK_SUCCESS;
}
VkResult vkAllocateDescriptorSets(VkDevice d,const VkDescriptorSetAllocateInfo *i,VkDescriptorSet *p){
 assert(sets<4);*p=(VkDescriptorSet)(uintptr_t)++sets;return VK_SUCCESS;
}
void vkUpdateDescriptorSets(VkDevice d,uint32_t n,const VkWriteDescriptorSet *w,uint32_t copies,const VkCopyDescriptorSet *c){
 assert(n==2 && writes<4);const VkDescriptorImageInfo *image=w[1].pImageInfo;
 const VkSamplerCreateInfo *s=&samplers[(uintptr_t)image->sampler];
 assert(s->minFilter==(writes==3?VK_FILTER_LINEAR:VK_FILTER_NEAREST) && s->magFilter==s->minFilter);
 assert(s->addressModeU==(writes==0?VK_SAMPLER_ADDRESS_MODE_REPEAT:VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE));
 assert(s->addressModeV==s->addressModeU && s->addressModeW==VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE);
 VkImageView expected[]={xv.vram.view,xv.main.view,xv.off.view,xv.main.view};
 assert(image->imageView==expected[writes] && image->imageLayout==VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);writes++;
}
int main(void){
 xv.vram.view=(VkImageView)1;xv.main.view=(VkImageView)2;xv.off.view=(VkImageView)3;
'''+body+r'''
 assert(calls==3 && sets==4 && writes==4);
 puts("PASS: actual packed-VRAM nearest/repeat sampler; main/offscreen nearest/clamp and FXAA linear/clamp descriptors");
}
'''
def run(source,name):
 f=a.out/(name+'.c');f.write_text(source);exe=a.out/name
 subprocess.run(['cc','-std=c17','-I'+str(a.vulkan/'third_party/vulkan-headers/include'),str(f),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True)
r=run(c,'vram-sampler');assert not r.returncode,r.stderr;print(r.stdout.strip())
bad=c.replace('sampler.addressModeU=sampler.addressModeV=VK_SAMPLER_ADDRESS_MODE_REPEAT','sampler.addressModeU=sampler.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE')
assert bad!=c and run(bad,'clamped-vram-negative').returncode
print('PASS: clamping packed VRAM instead of wrapping rejected')
