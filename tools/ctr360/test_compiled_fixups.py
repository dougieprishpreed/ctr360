"""Execute the linked PPC startup assignments against a private PE byte copy.

This small straight-line interpreter accepts only the integer instructions used
by these assignments. It does not run the game, GPU, audio or console APIs.
"""
from pathlib import Path
import json
import re
import struct
import subprocess

root = Path(__file__).resolve().parents[2]
out = root/'build-360/results/compiled-fixups'
out.mkdir(parents=True, exist_ok=True)
pe = (root/'build-360/xex/Release/ctr360.exe').read_bytes()
map_text = (root/'build-360/xex/Release/ctr360.map').read_text()
symbols = {name:int(address,16) for name,address in re.findall(
    r'^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{8})\b',map_text,re.M)}
start = symbols['Ctr360_ApplyStaticFixups']
header = struct.unpack_from('<I',pe,0x3c)[0]
count = struct.unpack_from('<H',pe,header+6)[0]
optional = header+24
size = struct.unpack_from('<H',pe,header+20)[0]
base = struct.unpack_from('<I',pe,optional+28)[0]
sections = [struct.unpack_from('<4I',pe,optional+size+i*40+8) for i in range(count)]
def offset(address):
    relative = address-base
    for virtual_size, virtual, raw_size, raw in sections:
        if virtual <= relative < virtual+raw_size:
            return raw+relative-virtual
    raise AssertionError(f'unmapped address {address:08x}')
def signed(value,bits):
    return value-(1<<bits) if value&(1<<(bits-1)) else value
memory = {}
def read(address,n):
    return int.from_bytes(bytes(memory[address+i] if address+i in memory else pe[offset(address+i)] for i in range(n)),'big')
def store(address,n,value):
    for i,b in enumerate((value&((1<<(n*8))-1)).to_bytes(n,'big')):
        memory[address+i] = b
registers = [0]*32
registers[1] = 0x70000000
steps = 0
pc = start
abi_helpers = []
link_register = 0
while steps < 4096:
    instruction = int.from_bytes(pe[offset(pc):offset(pc)+4],'big')
    if instruction == 0x4e800020:  # blr
        break
    op = instruction>>26
    rs=(instruction>>21)&31; ra=(instruction>>16)&31; rb=(instruction>>11)&31
    immediate=instruction&0xffff
    displacement=signed(immediate,16)
    address=((registers[ra] if ra else 0)+displacement)&0xffffffff
    if op == 18:
        target = (signed(instruction&0x03fffffc,26)+(0 if instruction&2 else pc))&0xffffffff
        names = [name for name,address in symbols.items() if address==target]
        if any(name.startswith('__savegprlr_') for name in names) and instruction&1:
            # The SDK helper saves nonvolatile registers/LR to the caller's
            # stack. Those ABI saves do not change the global assignments.
            abi_helpers.extend(names); link_register=pc+4
        elif any(name.startswith('__restgprlr_') for name in names) and not instruction&1:
            abi_helpers.extend(names)
            break  # SDK tail restore returns to the caller.
        else:
            raise AssertionError(f'unexpected startup branch {target:08x}: {names}')
    elif op==31 and ((instruction>>1)&1023)==339:
        spr=ra|(rb<<5)
        assert spr==8, spr
        registers[rs]=link_register
    elif op in (14,15):
        registers[rs]=((registers[ra] if ra else 0)+(displacement<<(16 if op==15 else 0)))&0xffffffff
    elif op in (24,25,26,27,28,29):
        value=immediate<<(16 if op in (25,27,29) else 0)
        registers[ra]=(registers[rs]|value) if op in (24,25) else ((registers[rs]^value) if op in (26,27) else registers[rs]&value)
    elif op in (32,34,40):
        registers[rs]=read(address,{32:4,34:1,40:2}[op])
    elif op in (36,37,38,44):
        store(address,{36:4,37:4,38:1,44:2}[op],registers[rs])
        if op==37: registers[ra]=address
    elif op==31 and ((instruction>>1)&1023) in (151,215,407):
        xo=(instruction>>1)&1023
        indexed=((registers[ra] if ra else 0)+registers[rb])&0xffffffff
        store(indexed,{151:4,215:1,407:2}[xo],registers[rs])
    elif op in (20,21):
        shift=rb; begin=(instruction>>6)&31; end=(instruction>>1)&31
        mask=sum(1<<(31-i) for i in range(32) if (begin<=i<=end if begin<=end else i>=begin or i<=end))
        value=((registers[rs]<<shift)|(registers[rs]>>(32-shift if shift else 32)))&0xffffffff
        registers[ra]=(value&mask) | (registers[ra]&~mask if op==20 else 0)
    elif op==31 and ((instruction>>1)&1023) in (444,316,266):
        xo=(instruction>>1)&1023
        if xo==266: registers[rs]=(registers[ra]+registers[rb])&0xffffffff
        else: registers[ra]=(registers[rs]|registers[rb]) if xo==444 else registers[rs]^registers[rb]
    else:
        raise AssertionError(f'unsupported startup instruction {instruction:08x} at {pc:08x}')
    steps+=1; pc+=4
else:
    raise AssertionError('startup assignment function did not return')

expected={'emSet_Fireball':(0x4a1,4,0),'emSet_fjFire':(0xa1,7,0),'emSet_fjHeat':(0xa1,6,1)}
results={}
for name,values in expected.items():
    address=symbols[name]
    actual=(read(address+8,2),signed(read(address+10,2),16),read(address+12,4))
    assert actual==values,(name,actual,values)
    results[name]={'address':hex(address),'colorFlags':actual[0],'lifespan':actual[1],'rendererType':actual[2]}
# Actual 32-bit header layout is obtained independently from Clang's record dump.
layout_run=subprocess.run(['clang','-fsyntax-only','-m32','-DCTR_NATIVE',
    '-I',str(root/'build-360/gen/include'),'-I',str(root/'build-360/gen/platform/xbox360/sdl_shim'),
    '-Wno-incompatible-function-pointer-types','-Wno-incompatible-pointer-types',
    '-Wno-int-conversion','-Wno-excess-initializers','-Wno-pointer-sign',
    '-x','c','-Xclang','-fdump-record-layouts','-'],
    input='#include <common.h>\nint warpballOffset=__builtin_offsetof(struct Data,emSet_Warpball);\n',
    capture_output=True,text=True,check=True)
layouts=layout_run.stdout
(out/'record-layouts.txt').write_text(layouts)
relative=int(re.search(r'^\s*(\d+)\s*\|\s+struct ParticleEmitter\[11\] emSet_Warpball$',layouts,re.M)[1])
address=symbols['data']+relative
assert signed(read(address+10,2),16)==-1 and read(address+12,4)==1
results['warpball']={'address':hex(address),'lifespan':-1,'rendererType':1}
main=symbols['main']; assets=symbols['NativeAssets_Init']
calls=[]
for address in range(main,main+4096,4):
    word=int.from_bytes(pe[offset(address):offset(address)+4],'big')
    if word>>26==18 and word&1:
        target=(signed(word&0x03fffffc,26)+(0 if word&2 else address))&0xffffffff
        if target in (start,assets): calls.append((address,target))
assert len([p for p,t in calls if t==start])==1,calls
assert min(p for p,t in calls if t==start)<min(p for p,t in calls if t==assets),calls
report={'instructions_executed':steps,'changed_bytes':len(memory),'emitters':results,
        'startup_call_before_assets':True,'calls':[(hex(p),hex(t)) for p,t in calls],
        'ABI_helpers_skipped':abi_helpers,
        'limits':'integer startup assignments only; SDK register save/restore helpers skipped; no gameplay or GPU execution'}
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS actual PPC startup assignments:',json.dumps(results),'instructions=',steps)
