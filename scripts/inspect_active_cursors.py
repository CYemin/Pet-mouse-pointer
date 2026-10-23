"""Read-only Win32 check: compare active system cursors with installed files."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import sys
import winreg

ROLES = dict(zip(
    ('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No',
     'SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person'),
    (32512,32651,32650,32514,32515,32513,32631,32648,
     32645,32644,32642,32643,32646,32516,32649,32671,32672)))

user = c.WinDLL('user32', use_last_error=True)
gdi = c.WinDLL('gdi32', use_last_error=True)

class ICONINFO(c.Structure):
    _fields_ = [('fIcon',w.BOOL),('xHotspot',w.DWORD),('yHotspot',w.DWORD),
                ('hbmMask',w.HBITMAP),('hbmColor',w.HBITMAP)]

class BITMAP(c.Structure):
    _fields_ = [('bmType',w.LONG),('bmWidth',w.LONG),('bmHeight',w.LONG),
                ('bmWidthBytes',w.LONG),('bmPlanes',w.WORD),('bmBitsPixel',w.WORD),('bmBits',c.c_void_p)]

class HEADER(c.Structure):
    _fields_ = [('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),
                ('bpp',w.WORD),('compression',w.DWORD),('bytes',w.DWORD),
                ('xp',w.LONG),('yp',w.LONG),('used',w.DWORD),('important',w.DWORD)]

user.LoadCursorW.argtypes=[w.HINSTANCE,c.c_void_p]; user.LoadCursorW.restype=w.HANDLE
user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,c.c_int,c.c_int,w.UINT]; user.LoadImageW.restype=w.HANDLE
user.GetIconInfo.argtypes=[w.HANDLE,c.POINTER(ICONINFO)]; user.GetIconInfo.restype=w.BOOL
user.DrawIconEx.argtypes=[w.HDC,c.c_int,c.c_int,w.HANDLE,c.c_int,c.c_int,w.UINT,w.HBRUSH,w.UINT]; user.DrawIconEx.restype=w.BOOL
user.DestroyCursor.argtypes=[w.HANDLE]; user.DestroyCursor.restype=w.BOOL
gdi.GetObjectW.argtypes=[w.HANDLE,c.c_int,c.c_void_p]; gdi.GetObjectW.restype=c.c_int
gdi.DeleteObject.argtypes=[w.HANDLE]; gdi.DeleteObject.restype=w.BOOL
gdi.CreateCompatibleDC.argtypes=[w.HDC]; gdi.CreateCompatibleDC.restype=w.HDC
gdi.CreateDIBSection.argtypes=[w.HDC,c.c_void_p,w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD]; gdi.CreateDIBSection.restype=w.HBITMAP
gdi.SelectObject.argtypes=[w.HDC,w.HANDLE]; gdi.SelectObject.restype=w.HANDLE
gdi.DeleteDC.argtypes=[w.HDC]; gdi.DeleteDC.restype=w.BOOL

def signature(handle):
    if not handle:
        raise c.WinError(c.get_last_error())
    info=ICONINFO()
    if not user.GetIconInfo(handle,c.byref(info)):
        raise c.WinError(c.get_last_error())
    try:
        bitmap=BITMAP()
        if not gdi.GetObjectW(info.hbmColor or info.hbmMask,c.sizeof(bitmap),c.byref(bitmap)):
            raise c.WinError(c.get_last_error())
        width,height=bitmap.bmWidth,bitmap.bmHeight
        if not info.hbmColor:
            height //= 2
        bits=c.c_void_p(); dc=gdi.CreateCompatibleDC(None)
        header=HEADER(40,width,-height,1,32,0,width*height*4,0,0,0,0)
        dib=gdi.CreateDIBSection(dc,c.byref(header),0,c.byref(bits),None,0)
        if not dib or not bits.value:
            gdi.DeleteDC(dc)
            raise c.WinError(c.get_last_error())
        old=gdi.SelectObject(dc,dib)
        try:
            c.memset(bits,0,width*height*4)
            if not user.DrawIconEx(dc,0,0,handle,width,height,0,None,3):
                raise c.WinError(c.get_last_error())
            gdi.GdiFlush()
            pixels=c.string_at(bits,width*height*4)
            return {'size':[width,height],'hotspot':[info.xHotspot,info.yHotspot],
                    'pixels':hashlib.sha256(pixels).hexdigest()}
        finally:
            gdi.SelectObject(dc,old); gdi.DeleteObject(dib); gdi.DeleteDC(dc)
    finally:
        if info.hbmColor: gdi.DeleteObject(info.hbmColor)
        if info.hbmMask: gdi.DeleteObject(info.hbmMask)

def inspect():
    records=[]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Control Panel\Cursors') as key:
        scheme=winreg.QueryValueEx(key,'')[0]
        for role,resource in ROLES.items():
            path=winreg.QueryValueEx(key,role)[0]
            active=signature(user.LoadCursorW(None,resource))
            reference=user.LoadImageW(None,path,2,*active['size'],0x10)
            try:
                expected=signature(reference)
            finally:
                if reference: user.DestroyCursor(reference)
            records.append({'role':role,'matches':active==expected,'active':active,'expected':expected})
    return {'scheme':scheme,'all_match':all(r['matches'] for r in records),'roles':records}

if __name__=='__main__':
    if '--snapshot' in sys.argv:
        print(json.dumps({role:signature(user.LoadCursorW(None,resource)) for role,resource in ROLES.items()},sort_keys=True))
        raise SystemExit(0)
    report=inspect()
    print(json.dumps(report,ensure_ascii=True,indent=2))
    raise SystemExit(0 if report['all_match'] else 1)
