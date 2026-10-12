"""ctr360 fix: D3D9 Clear with no rect array must pass Count=0. Count=1 with a
NULL pRects is undefined and is read as 'one rectangle from NULL' on 360."""
import io

P = r'F:\downloads\temp\python\hermes\ctrport\ctr360\platform\xbox360\native_xbox360_video.c'
s = io.open(P, encoding='utf-8', newline='').read()

pairs = [
    ('IDirect3DDevice9_Clear(s_device, 1, NULL, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);',
     'IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);'),
    ('IDirect3DDevice9_Clear(s_device, 1, NULL, D3DCLEAR_TARGET, color, 1.0f, 0);',
     'IDirect3DDevice9_Clear(s_device, 0, NULL, D3DCLEAR_TARGET, color, 1.0f, 0);'),
]
for old, new in pairs:
    n = s.count(old)
    print('%-30s matches=%d' % (old[20:50], n))
    assert n == 1, n
    s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('Clear counts fixed (1 -> 0)')
