"""Compile actual RefreshCard ghost metadata functions against native fields."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / "build-360/results/20261011-memcard-metadata"
out.mkdir(exist_ok=True)
source = (root / "game/RefreshCard.c").read_text(encoding="utf-8")

def function(name):
    start = source.rfind("\n", 0, source.index(name + "(")) + 1
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"

prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int16_t s16;typedef uint16_t u16;typedef uint32_t u32;
struct GhostProfile {char profile_name[21],SubmitName_name[17];s16 alwaysOne,trackID,characterID;int memcardProfileIndex,trackTime;};
static struct {s16 numGhostProfilesSaved;struct GhostProfile ghostProfile_memcard[7];} state,*sdata=&state;
'''
tests = r'''
int main(void) {
 char name[20]="BASCUS-94426G000000";int i;
 u32 packed=5|(3<<4)|(123456<<9)|(4u<<29);
 struct GhostProfile decoded;
 memset(&decoded,0x7f,sizeof decoded);
 for(i=0;i<6;i++)name[13+i]=(char)RefreshCard_GhostEncodeByte((packed>>(i*6))&63);
 RefreshCard_GhostDecodeProfile(&decoded,name);
 assert(decoded.trackID==3&&decoded.characterID==5&&decoded.trackTime==123456);
 assert(decoded.memcardProfileIndex==4&&decoded.alwaysOne==0&&strcmp(decoded.profile_name,name)==0);
 sdata->numGhostProfilesSaved=7;
 for(i=0;i<7;i++)sdata->ghostProfile_memcard[i].trackID=(i%2)?3:4;
 assert(RefreshCard_CountGhostProfilesForLEV(3)==3);
 assert(RefreshCard_CountGhostProfilesForLEV(4)==4);
 assert(RefreshCard_CountGhostProfilesForLEV(0)==0);
 RefreshCard_GetNumGhostsTotal();assert(sdata->numGhostProfilesSaved==0);
 assert(RefreshCard_CountGhostProfilesForLEV(3)==0);
 puts("PASS native ghost count/track/character/time/index, full-width fields and reset");return 0;
}
'''
code = prelude + "\n".join(function(n) for n in ["RefreshCard_CountGhostProfilesForLEV", "RefreshCard_GetNumGhostsTotal", "RefreshCard_GhostEncodeByte", "RefreshCard_GhostDecodeByte", "RefreshCard_GhostDecodeProfile"]) + tests
(out / "test.c").write_text(code, encoding="utf-8")
subprocess.run(["clang", "-O2", str(out / "test.c"), "-o", str(out / "test.exe")], check=True)
run = subprocess.run([str(out / "test.exe")], check=True, capture_output=True, text=True)
(out / "result.txt").write_text(run.stdout, encoding="utf-8")
print(run.stdout, end="")
