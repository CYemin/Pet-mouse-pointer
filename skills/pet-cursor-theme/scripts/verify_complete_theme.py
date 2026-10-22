"""Validate every exported frame's format/hotspot and use native Win32 loading."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import hashlib
import json
import struct
import sys
from PIL import Image

OUT=Path(sys.argv[1] if len(sys.argv)>1 else 'output/pet-handdrawn-complete').resolve()
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
assert len(manifest['states'])==17
assert len({s['role'] for s in manifest['states']})==17
user=c.WinDLL('user32',use_last_error=True);gdi=c.WinDLL('gdi32',use_last_error=True)
class ICONINFO(c.Structure):
    _fields_=[('fIcon',w.BOOL),('xHotspot',w.DWORD),('yHotspot',w.DWORD),('hbmMask',w.HBITMAP),('hbmColor',w.HBITMAP)]
class BITMAP(c.Structure):
    _fields_=[('bmType',w.LONG),('bmWidth',w.LONG),('bmHeight',w.LONG),('bmWidthBytes',w.LONG),('bmPlanes',w.WORD),('bmBitsPixel',w.WORD),('bmBits',c.c_void_p)]
class HEADER(c.Structure):
    _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bpp',w.WORD),('compression',w.DWORD),('bytes',w.DWORD),('xp',w.LONG),('yp',w.LONG),('used',w.DWORD),('important',w.DWORD)]
user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT];user.LoadImageW.restype=w.HANDLE
user.GetIconInfo.argtypes=[w.HANDLE,c.POINTER(ICONINFO)];user.GetIconInfo.restype=w.BOOL
user.DestroyCursor.argtypes=[w.HANDLE];user.DestroyCursor.restype=w.BOOL
user.DrawIconEx.argtypes=[w.HDC,c.c_int,c.c_int,w.HANDLE,c.c_int,c.c_int,w.UINT,w.HBRUSH,w.UINT];user.DrawIconEx.restype=w.BOOL
gdi.GetObjectW.argtypes=[w.HANDLE,c.c_int,c.c_void_p];gdi.GetObjectW.restype=c.c_int
gdi.DeleteObject.argtypes=[w.HANDLE];gdi.DeleteObject.restype=w.BOOL
gdi.CreateCompatibleDC.argtypes=[w.HDC];gdi.CreateCompatibleDC.restype=w.HDC
gdi.CreateDIBSection.argtypes=[w.HDC,c.c_void_p,w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD];gdi.CreateDIBSection.restype=w.HBITMAP
gdi.SelectObject.argtypes=[w.HDC,w.HANDLE];gdi.SelectObject.restype=w.HANDLE
gdi.DeleteDC.argtypes=[w.HDC];gdi.DeleteDC.restype=w.BOOL

def chunks(data,start=0):
    while start<len(data):
        tag=data[start:start+4];size=struct.unpack_from('<I',data,start+4)[0]
        assert start+8+size<=len(data),'RIFF chunk overflow'
        yield tag,data[start+8:start+8+size]
        start+=8+size+(size%2)
    assert start==len(data)

def parse_cur(data,n,hot):
    assert struct.unpack_from('<HHH',data)==(0,2,1)
    width,height,_,_,hx,hy,length,offset=struct.unpack_from('<BBBBHHII',data,6)
    assert (width,height)==(n,n)
    assert (hx,hy)==tuple(hot)
    assert offset>=22 and offset+length<=len(data)
    size,bw,bh=struct.unpack_from('<Iii',data,offset)
    assert (size,bw,bh)==(40,n,n*2)

def verify_ani(data,n,s):
    assert data[:4]==b'RIFF' and data[8:12]==b'ACON'
    assert struct.unpack_from('<I',data,4)[0]+8==len(data)
    blocks=dict(chunks(data,12))
    header=struct.unpack('<9I',blocks[b'anih'])
    assert header[0]==36 and header[1]==s['frame_count'] and header[2]==len(s['sequence'])
    assert list(struct.unpack('<'+'I'*len(s['ticks']),blocks[b'rate']))==s['ticks']
    assert list(struct.unpack('<'+'I'*len(s['sequence']),blocks[b'seq ']))==s['sequence']
    assert blocks[b'LIST'][:4]==b'fram'
    cursors=[payload for tag,payload in chunks(blocks[b'LIST'],4) if tag==b'icon']
    assert len(cursors)==s['frame_count']
    for cur in cursors:parse_cur(cur,n,s['hotspots'][str(n)])
    return len(cursors)

def native(path,n,s):
    handle=user.LoadImageW(None,str(path),2,n,n,0x10)
    assert handle,(path,c.get_last_error())
    info=ICONINFO();hashes=[]
    try:
        assert user.GetIconInfo(handle,c.byref(info))
        assert not info.fIcon
        assert (info.xHotspot,info.yHotspot)==tuple(s['hotspots'][str(n)])
        bitmap=BITMAP();assert gdi.GetObjectW(info.hbmColor,c.sizeof(bitmap),c.byref(bitmap))
        assert (bitmap.bmWidth,bitmap.bmHeight)==(n,n)
        dc=gdi.CreateCompatibleDC(None);bits=c.c_void_p()
        header=HEADER(40,n,-n,1,32,0,n*n*4,0,0,0,0)
        dib=gdi.CreateDIBSection(dc,c.byref(header),0,c.byref(bits),None,0)
        assert dib and bits.value
        old=gdi.SelectObject(dc,dib)
        try:
            for step in range(s['frame_count']):
                c.memset(bits,0,n*n*4)
                assert user.DrawIconEx(dc,0,0,handle,n,n,step,None,3)
                gdi.GdiFlush();buffer=c.string_at(bits,n*n*4)
                assert any(buffer),'Empty native frame'
                hashes.append(hashlib.sha256(buffer).hexdigest()[:16])
        finally:
            gdi.SelectObject(dc,old);gdi.DeleteObject(dib);gdi.DeleteDC(dc)
        if s['animated']:assert len(set(hashes))>1,'Animation has no visible frame change'
    finally:
        if info.hbmMask:gdi.DeleteObject(info.hbmMask)
        if info.hbmColor:gdi.DeleteObject(info.hbmColor)
        user.DestroyCursor(handle)
    return hashes

records=[];frames=0;warnings=[]
for s in manifest['states']:
    files=[(OUT/relative,int(n)) for n,relative in s['variants'].items()]+[(OUT/s['file'],48)]
    for path,n in files:
        data=path.read_bytes()
        if s['animated']:frames+=verify_ani(data,n,s)
        else:parse_cur(data,n,s['hotspots'][str(n)]);frames+=1
        hashes=native(path,n,s)
        records.append({'file':str(path.relative_to(OUT)),'role':s['role'],'size':n,
                        'hotspot':s['hotspots'][str(n)],'native_frame_hashes':hashes})
    for n in manifest['sizes']:
        for k in range(s['frame_count']):
            image=Image.open(OUT/f'frames/{s["id"]}-{n}-{k}.png')
            assert image.mode=='RGBA' and image.size==(n,n)
            hot=tuple(s['hotspots'][str(n)])
            if image.getpixel(hot)[3]<50:warnings.append(f'{s["id"]}/{n}/{k}: hotspot on transparent edge; inspect manually')
report={'status':'passed','roles':17,'files_checked':len(records),'embedded_cursor_frames_checked':frames,
 'all_native_loads_and_draws_passed':True,'hotspot_warnings':warnings,'system_settings_modified':False,
 'manual_checks_pending':['Windows desktop scheme installation and restoration','multiple monitors and DPI switching','user evaluation of likeness and click feel'],
 'checks':records}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
