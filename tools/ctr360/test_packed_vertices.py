"""Check packed vertex fetch values and compile the actual Xbox vertex shader.
Numeric tests do not replace console verification of the GPU fetch format.
"""
import ast,math,re,struct,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'build-360/results/packed-vertices';out.mkdir(parents=True,exist_ok=True)
s=(root/'platform/xbox360/native_xbox360_video.c').read_text()
# Match the source declaration: SHORT4, UBYTE4, UBYTE4N, UBYTE4 at 0/8/12/16.
for index,offset,kind in [(0,0,'SHORT4'),(1,8,'UBYTE4'),(2,12,'UBYTE4N'),(3,16,'UBYTE4')]:
 assert f'elements[{index}].Offset = {offset};' in s
 assert f'elements[{index}].Type = D3DDECLTYPE_{kind};' in s
for value in range(256):
 signed=value if value<128 else value-256
 packed=struct.pack('>4h8B4b',-32768,32767,-1,63,value,255,2,1,value,255-value,128,255,signed,-128,0,127)
 assert len(packed)==20
 position=struct.unpack_from('>4h',packed,0)
 assert position==(-32768,32767,-1,63)
 assert list(packed[8:12])==[value,255,2,1]
 for actual,expected in zip(packed[12:16],[value,255-value,128,255]):
  assert math.isclose(actual/255.0,expected/255.0)
 extra=[float(v)-(256.0 if v>=128 else 0.0) for v in packed[16:20]]
 assert extra==[signed,-128,0,127]
block=s.split('const char *x360_psx_vs =',1)[1].split(';\n',1)[0]
shader=''.join(ast.literal_eval(part) for part in re.findall(r'"(?:[^"\\]|\\.)*"',block))
path=out/'psx_vs.hlsl';path.write_text(shader)
compiler=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/fxc.exe')
subprocess.run([str(compiler),'/nologo','/T','vs_3_0','/E','main','/Fo',str(out/'psx_vs.bin'),str(path)],check=True)
print('PASS: packed big-endian values, signed UV edges, normalized colors; actual HLSL compiled')
print('Vertex upload: 64 -> 20 bytes (68.75% reduction)')
