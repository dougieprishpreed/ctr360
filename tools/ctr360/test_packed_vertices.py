"""Check packed vertex fetch values and compile the actual Xbox vertex shader.
Numeric tests do not replace console verification of the GPU fetch format.
"""
import ast,math,re,struct,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/packed-vertices';out.mkdir(parents=True,exist_ok=True)
s=(root/'platform/xbox360/native_xbox360_video.c').read_text()
# Model the actual Xenos fetch: little-endian lanes AFTER declaration byte swap.
# Stock Xbox UBYTE4/UBYTE4N are DWORD-packed, unlike GrVertex byte arrays.
sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK/include/xbox/d3d9types.h').read_text()
def fetch(data, index, broken=False):
 expression=re.search(r'elements\['+str(index)+r'\]\.Type = ([^;]+);',s).group(1)
 kind=re.search(r'D3DDECLTYPE_(SHORT4|UBYTE4N|UBYTE4)\b',expression).group(1)
 definition=re.search(r'D3DDECLTYPE_'+kind+r'\s*= MAKED3DDECLTYPE\(([^;]+)\)',sdk).group(1)
 endian=re.search(r'GPUENDIAN_(\w+)',definition).group(1)
 if ' & ~D3DDECLTYPE_ENDIAN_MASK' in expression and not broken: endian='NONE'
 offset=[0,8,12,16][index]
 assert f'elements[{index}].Offset = {offset};' in s
 raw=data[offset:offset+(8 if kind=='SHORT4' else 4)]
 unit={'NONE':1,'8IN16':2,'8IN32':4}[endian]
 raw=b''.join(raw[i:i+unit][::-1] for i in range(0,len(raw),unit))
 values=list(struct.unpack('<4h',raw)) if kind=='SHORT4' else list(raw)
 return [v/255.0 for v in values] if kind=='UBYTE4N' else values
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
print('PASS: XDK declaration byte swaps, signed UV edges, normalized colors, old-bug negative control; actual HLSL compiled')
print('Vertex upload: 64 -> 20 bytes (68.75% reduction)')
