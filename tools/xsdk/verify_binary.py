"""Check architecture, entry point, runtime imports and callback register safety."""
import argparse,json,re,struct,subprocess,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--elf',type=Path,required=True);p.add_argument('--xex',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True)
a=p.parse_args();data=a.elf.read_bytes()
assert data[:7]==b'\x7fELF\x01\x02\x01','expected big-endian ELF32'
assert struct.unpack_from('>H',data,18)[0]==20,'expected PowerPC'
flags=struct.unpack_from('>I',data,36)[0];assert flags & 0x100,'missing xSDK calling convention flag'
entry=struct.unpack_from('>I',data,24)[0]
base=str(a.toolchain/'bin/powerpc-xsdk-elf-')
symbols=subprocess.check_output([base+'nm','-n',str(a.elf)],text=True)
assert re.search(r'^'+format(entry,'08x')+r' [Tt] xsdk_start$',symbols,re.M),'entry is not xSDK startup'
assert not re.search(r'\b(D3DDevice|XAudio2Create|Direct3DCreate9|XapiInitProcess)\b',symbols),'unexpected XDK dependency'
for function in ['XsdkAudioCallback','memcpy','memset']:
 assembly=subprocess.check_output([base+'objdump','-d','--disassemble='+function,str(a.elf)],text=True)
 assert '<'+function+'>:' in assembly,function+' missing'
 # Callback code and its copy routines must avoid the kernel thread's FPRs.
 assert not re.search(r'\b(?:lfs|lfd|stfs|stfd|fadd|fmul|fmr|fdiv|fsub|fcmp)\w*\s',assembly),function+' uses floating point'
xex=a.xex.read_bytes();assert xex[:4]==b'XEX2','not an XEX2 container'
payload,security,headers=struct.unpack_from('>I4xII',xex,8)
image_bytes=struct.unpack_from('>I',xex,security+4)[0]
options=dict(struct.unpack_from('>II',xex,24+i*8) for i in range(headers))
assert options[0x10100]==entry,'XEX entry differs from ELF'
fmt=options[0x3ff];size,encryption,compression=struct.unpack_from('>IHH',xex,fmt)
assert encryption==0 and compression==1 and size>=16 and (size-8)%8==0
image=bytearray();position=payload
for offset in range(fmt+8,fmt+size,8):
 raw,zeros=struct.unpack_from('>II',xex,offset)
 assert raw<=len(xex)-position and len(image)+raw+zeros<=image_bytes,'invalid XEX data/zero run'
 image+=xex[position:position+raw]+bytes(zeros);position+=raw
assert position==len(xex) and len(image)<=image_bytes
image+=bytes(image_bytes-len(image))
pe=struct.unpack_from('<I',image,0x3c)[0]
assert image[:2]==b'MZ' and image[pe:pe+4]==b'PE\0\0','invalid loaded PE image'
# Verify the independent page hash chain after expanding all zero runs.
pages=struct.unpack_from('>I',xex,security+0x180)[0]
assert pages*65536==image_bytes
digest=xex[security+0x114:security+0x128]
for page in range(pages):
 desc=xex[security+0x184+page*24:security+0x184+(page+1)*24]
 assert len(desc)==24 and struct.unpack_from('>I',desc)[0]>>4==1
 assert hashlib.sha1(image[page*65536:(page+1)*65536]+desc).digest()==digest,'XEX loaded-page hash mismatch'
 digest=desc[4:24]
assert digest==bytes(20)
report={'elf':'ELF32 PowerPC big-endian','xsdk_abi':True,'entry':hex(entry),'entry_symbol':'xsdk_start',
 'audio_callback_integer_only':True,'microsoft_sdk_dependencies':False,'xex_bytes':a.xex.stat().st_size,
 'xex_sha256':hashlib.sha256(xex).hexdigest(),'loaded_image_bytes':image_bytes,
 'loaded_image_sha256':hashlib.sha256(image).hexdigest(),'xex_page_hashes_verified':True,'hardware_tested':False}
(a.xex.parent/'binary-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
