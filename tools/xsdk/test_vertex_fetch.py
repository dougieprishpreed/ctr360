"""Model the pinned Vulkan/Xenos fetch contract, including actual format swizzles."""
import argparse,re,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vulkan',type=Path,required=True);p.add_argument('--xsdk',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[2]
s=(root/'platform/xsdk/native_xsdk_video.c').read_text()
f=(a.vulkan/'src/format.c').read_text()
g=(a.xsdk/'src/gpu_draw.c').read_text()
# The SDK emits the same 8-in-32 endian mode for every vertex stream.
assert re.search(r'VERTEX_FETCH_8IN32 = 1 << 28 \| 2',g)
assert 'const uint32_t size = VERTEX_FETCH_8IN32 |' in g
assert 'typedef struct { GrVertex v; u8 uvMin[2],uvMax[2]; } XvVertex;' in s
assert 'quad?sizeof(XvQuadVertex):sizeof(XvVertex)' in s
assert 'if(quad)attrs[0].format=VK_FORMAT_R32G32B32A32_SFLOAT;' in s
assert 'o->v=vertices[first+i];o->uvMin[0]=u0;o->uvMin[1]=v0;o->uvMax[0]=u1;o->uvMax[1]=v1;' in s
attrs=re.findall(r'\{([0-4]),0,(VK_FORMAT_\w+),([0-9]+)\}',s)
assert len(attrs)==5
formats=[]
for i,name,offset in attrs:
 row=re.search(r'\{ '+name+r', (XSDK_VERTEX_\w+), \{ ([^}]+) \} \}',f)
 assert row,name
 kind,swizzle=row.groups()
 formats.append((int(offset),kind,[{'X':0,'Y':1,'Z':2,'W':3}[v.strip()] for v in swizzle.split(',')]))
def fetch(packed,entry,apply_swizzle=True):
 offset,kind,swizzle=entry
 raw=packed[offset:offset+(8 if kind=='XSDK_VERTEX_SHORT4' else 4)]
 # Xenos reads little-endian lanes after a 32-bit byte reversal.
 raw=b''.join(raw[i:i+4][::-1] for i in range(0,len(raw),4))
 fmt={'XSDK_VERTEX_SHORT4':'<4h','XSDK_VERTEX_UBYTE4':'4B','XSDK_VERTEX_UBYTE4N':'4B','XSDK_VERTEX_BYTE4':'4b'}[kind]
 result=struct.unpack(fmt,raw)
 if apply_swizzle:result=[result[i] for i in swizzle]
 if kind=='XSDK_VERTEX_UBYTE4N':result=[v/255.0 for v in result]
 return list(result)
for byte in range(256):
 signed=byte if byte<128 else byte-256
 fields=[[-32768,32767,-1,63],[byte,255,2,1],[byte,255-byte,128,255],[signed,-128,0,127],[byte,0,255-byte,255]]
 data=struct.pack('>4h8B4b4B',*sum(fields,[]))
 for index,entry in enumerate(formats):
  expected=fields[index]
  if index==2:expected=[v/255.0 for v in expected]
  assert fetch(data,entry)==expected,(index,byte)
 assert fetch(data,formats[1],False)!=fields[1], 'negative control must detect missing byte swizzle'
print('PASS: pinned Vulkan format mappings, 32-bit byte swap, signed shorts/bytes, RGBA, triangle texel range, separate float quad stride; 256 fixtures')
