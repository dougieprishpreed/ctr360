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
assert a.xex.read_bytes()[:4]==b'XEX2','not an XEX2 container'
report={'elf':'ELF32 PowerPC big-endian','xsdk_abi':True,'entry':hex(entry),'entry_symbol':'xsdk_start',
 'audio_callback_integer_only':True,'microsoft_sdk_dependencies':False,'xex_bytes':a.xex.stat().st_size,
 'xex_sha256':hashlib.sha256(a.xex.read_bytes()).hexdigest(),'hardware_tested':False}
(a.xex.parent/'binary-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
