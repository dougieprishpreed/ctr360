"""Make the default ctr360.ini with the actual config code, as the game does on its first start.

The store's package has no ctr360.ini, so updates never replace the player's
settings; the game makes one from ctr360.example.ini when it is missing.
"""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',default='cc')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[2]
config=(root/'platform/native_config.c').read_text()
example=(root/'tools/ctr360/ctr360.example.ini').read_bytes()
(a.out/'ctr360.example.ini').write_bytes(example)
c=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
'''+config.replace('#include "platform/native_config.h"','typedef void (*NativeConfigSetting)(const char *section,const char *key,const char *value,void *context);')+r'''
static unsigned graphics;
static void Count(const char *section,const char *key,const char *value,void *context){(void)key;(void)value;(void)context;graphics+=!strcmp(section,"graphics");}
static long Size(const char *path){FILE *f=fopen(path,"rb");long n;if(!f)return -1;fseek(f,0,SEEK_END);n=ftell(f);fclose(f);return n;}
int main(void){
 remove("ctr360.ini");
 assert(NativeConfig_CreateDefault("ctr360.ini","ctr360.example.ini")==1);       /* first start: made */
 assert(Size("ctr360.ini")==Size("ctr360.example.ini") && Size("ctr360.ini")>0);
 assert(NativeConfig_Read("ctr360.ini",Count,NULL)==1 && graphics>=4);           /* and read as settings */
 FILE *f=fopen("ctr360.ini","wb");fputs("[graphics]\nwidescreen = 0\n",f);fclose(f);
 assert(NativeConfig_CreateDefault("ctr360.ini","ctr360.example.ini")==0);       /* the player's file stays */
 assert(Size("ctr360.ini")==(long)strlen("[graphics]\nwidescreen = 0\n"));
 remove("missing.ini");
 assert(NativeConfig_CreateDefault("missing.ini","no-example.ini")==0 && Size("missing.ini")<0);
 printf("PASS: actual config code makes ctr360.ini from the example when missing (%u graphics settings), keeps an existing one, and makes none without an example\n",graphics);
}
'''
def run(text,name):
 source=a.out/(name+'.c');source.write_text(text);exe=a.out/(name+'.exe')
 subprocess.run([a.cc,'-std=gnu17','-w',str(source),'-o',str(exe)],check=True)
 return subprocess.run([str(exe.resolve())],capture_output=True,text=True,cwd=a.out)
r=run(c,'config-default');assert r.returncode==0,r.stdout+r.stderr;print(r.stdout.strip())
created=(a.out/'ctr360.ini').read_bytes()
assert created==b'[graphics]\nwidescreen = 0\n'
never=c.replace('    file = fopen(path, "wb");','    return 0;\n    file = fopen(path, "wb");',1)
assert never!=c and run(never,'config-default-never').returncode!=0
print('PASS: never making ctr360.ini (none for the store install) rejected')
