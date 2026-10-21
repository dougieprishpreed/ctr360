"""Check packed vertex fetch values and compile the actual Xbox vertex shader.
Numeric tests do not replace console verification of the GPU fetch format.
"""
import ast,math,re,struct,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/packed-vertices';out.mkdir(parents=True,exist_ok=True)
s=(root/'platform/xbox360/native_xbox360_video.c').read_text()
# Xenos has ONE endian mode per stream. Component swizzles are per attribute.
# Extract the actual declaration rather than assuming CPU layout == GPU lanes.
declarations=[]
for index in range(4):
 expression=re.search(r'elements\['+str(index)+r'\]\.Type = ([^;]+);',s).group(1)
 args=re.search(r'MAKED3DDECLTYPE2\((.*)\)',expression,re.S).group(1)
 fields=[v.strip() for v in args.split(',')]
 declarations.append(fields)
assert {d[1] for d in declarations}=={'GPUENDIAN_8IN32'}, 'mixed stream endian modes are invalid'
def fetch(data,index,broken=False):
 fmt,endian,sign,number,*swizzle=declarations[index]
 offset=[0,8,12,16][index]
 assert f'elements[{index}].Offset = {offset};' in s
 raw=data[offset:offset+(8 if index==0 else 4)]
 raw=b''.join(raw[i:i+4][::-1] for i in range(0,len(raw),4))
 values=list(struct.unpack('<4h',raw)) if index==0 else list(raw)
 if not broken:values=[values[{'GPUSWIZZLE_X':0,'GPUSWIZZLE_Y':1,'GPUSWIZZLE_Z':2,'GPUSWIZZLE_W':3}[v]] for v in swizzle]
 return [v/255.0 for v in values] if number=='GPUNUMFORMAT_FRACTION' else values
for value in range(256):
 signed=value if value<128 else value-256
 packed=struct.pack('>4h8B4b',-32768,32767,-1,63,value,255,2,1,value,255-value,128,255,signed,-128,0,127)
 assert len(packed)==20
 assert fetch(packed,0)==[-32768,32767,-1,63]
 assert fetch(packed,1)==[value,255,2,1]
 assert fetch(packed,2)==[v/255.0 for v in [value,255-value,128,255]]
 extra=[v-(256 if v>=128 else 0) for v in fetch(packed,3)]
 assert extra==[signed,-128,0,127]
 # Negative control: the old declaration must reproduce the reversed fields.
 assert fetch(packed,1,broken=True)==[1,2,255,value]
 assert fetch(packed,1,broken=True)!=[value,255,2,1]
block=s.split('const char *x360_psx_vs =',1)[1].split(';\n',1)[0]
shader=''.join(ast.literal_eval(part) for part in re.findall(r'"(?:[^"\\]|\\.)*"',block))
path=out/'psx_vs.hlsl';path.write_text(shader)
compiler=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/fxc.exe')
subprocess.run([str(compiler),'/nologo','/T','vs_3_0','/E','main','/Fo',str(out/'psx_vs.bin'),str(path)],check=True)
print('PASS: stream endian mode and declaration swizzles, signed UV edges, normalized colors, missing-swizzle negative control; actual HLSL compiled')
print('Vertex upload: 64 -> 20 bytes (68.75% reduction)')
