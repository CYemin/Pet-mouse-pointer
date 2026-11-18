"""Compile an imagegen sprite sheet into native Windows cursor samples.

Pillow is used for sprite extraction, size conversion and preview encoding.
The illustration itself is generated, not redrawn by this compiler.
"""
from pathlib import Path
import io
import json
import struct
import zipfile
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'sable-dog-samples'
SOURCE = ROOT / 'assets/dog-sprites.png'
CANVAS = 464
ANCHOR = (64, 140)
SIZES = (32, 48, 64, 96, 128)
# Nose landmarks in each source cell. Register every frame on its nose tip.
LANDMARKS = [(54,127),(53,127),(54,127),(54,127),
             (54,127),(52,121),(53,123),(54,127)]
THEMES = {
    'normal-blink': {'frames': [0,1,2,1,3,0], 'ticks': [180,5,5,5,5,40]},
    'link-sniff': {'frames': [4,5,6,5,7], 'ticks': [65,9,10,9,35]},
}

def chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + b'\0' * (len(data) % 2)

def cur_file(images):
    entries, payloads = [], []
    offset = 6 + 16 * len(images)
    for image, hotspot in images:
        n = image.width
        # DIB with straight BGRA alpha, bottom-up pixels and 1-bit AND mask.
        pixels = b''.join(image.crop((0,y,n,y+1)).tobytes('raw','BGRA')
                          for y in range(n-1,-1,-1))
        stride = ((n + 31) // 32) * 4
        mask = bytearray(stride * n)
        for y in range(n):
            for x in range(n):
                if image.getpixel((x,n-1-y))[3] == 0:
                    mask[y*stride+x//8] |= 1 << (7-x%8)
        dib = struct.pack('<IiiHHIIiiII',40,n,n*2,1,32,0,len(pixels)+len(mask),0,0,0,0)
        data = dib + pixels + mask
        entries.append(struct.pack('<BBBBHHII',n,n,0,0,*hotspot,len(data),offset))
        payloads.append(data)
        offset += len(data)
    return struct.pack('<HHH',0,2,len(images)) + b''.join(entries) + b''.join(payloads)

def ani_file(cursors, sequence, rates):
    header = struct.pack('<9I',36,len(cursors),len(sequence),0,0,0,0,6,3)
    body = b'ACON' + chunk(b'anih',header)
    body += chunk(b'rate',struct.pack('<'+'I'*len(rates),*rates))
    body += chunk(b'seq ',struct.pack('<'+'I'*len(sequence),*sequence))
    body += chunk(b'LIST',b'fram'+b''.join(chunk(b'icon',c) for c in cursors))
    return b'RIFF' + struct.pack('<I',len(body)) + body

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    preview = OUT / 'frames'
    preview.mkdir(exist_ok=True)
    source = Image.open(SOURCE).convert('RGBA')
    w,h = source.size
    registered=[]
    for i, (nx,ny) in enumerate(LANDMARKS):
        col,row=i%4,i//4
        cell=source.crop((round(col*w/4),round(row*h/2),
                          round((col+1)*w/4),round((row+1)*h/2)))
        # Register on a fixed canvas without independently resizing frames.
        frame=Image.new('RGBA',(CANVAS,CANVAS))
        frame.alpha_composite(cell,(ANCHOR[0]-nx,ANCHOR[1]-ny))
        registered.append(frame)
    scaled={}
    for n in SIZES:
        scaled[n]=[f.resize((n,n),Image.Resampling.LANCZOS) for f in registered]
        for i,f in enumerate(scaled[n]):
            f.save(preview/f'{i}-{n}.png')
    hotspot=lambda n:tuple(round(a*n/CANVAS) for a in ANCHOR)
    for name,spec in THEMES.items():
        indices=list(dict.fromkeys(spec['frames']))
        seq=[indices.index(i) for i in spec['frames']]
        multi=[cur_file([(scaled[n][i],hotspot(n)) for n in SIZES]) for i in indices]
        # The native loader here rejects multi-resolution CURs inside ANI.
        # Export one tested ANI per size; default sample is the 48px version.
        for n in SIZES:
            cursors=[cur_file([(scaled[n][i],hotspot(n))]) for i in indices]
            data=ani_file(cursors,seq,spec['ticks'])
            (OUT/f'{name}-{n}.ani').write_bytes(data)
            if n==48:(OUT/f'{name}.ani').write_bytes(data)
        (OUT/f'{name}-static.cur').write_bytes(multi[0])
        frames=[]
        for i in spec['frames']:
            bg=Image.new('RGBA',(232,232),(239,233,222,255))
            bg.alpha_composite(registered[i].resize((224,224),Image.Resampling.LANCZOS),(4,4))
            frames.append(bg.convert('RGB'))
        frames[0].save(OUT/f'{name}.gif',save_all=True,append_images=frames[1:],
                       duration=[round(t*1000/60) for t in spec['ticks']],loop=0)
    # Side-by-side GIF, shared 60Hz timeline sampled at 10fps.
    gallery=[]
    def at_tick(spec,tick):
        t=tick%sum(spec['ticks'])
        for idx,duration in zip(spec['frames'],spec['ticks']):
            if t<duration:return idx
            t-=duration
    for tick in range(0,720,6):
        panel=Image.new('RGBA',(512,282),'#f1ece2')
        draw=ImageDraw.Draw(panel)
        draw.text((20,15),'NORMAL / BLINK',fill='#44382e')
        draw.text((276,15),'LINK / SNIFF',fill='#44382e')
        for x,spec in zip((8,264),THEMES.values()):
            art=registered[at_tick(spec,tick)].resize((232,232),Image.Resampling.LANCZOS)
            panel.alpha_composite(art,(x,42))
        gallery.append(panel.convert('RGB'))
    gallery[0].save(OUT/'preview.gif',save_all=True,append_images=gallery[1:],duration=100,loop=0)
    metadata={'source': str(SOURCE.relative_to(ROOT)),'sizes':SIZES,
              'hotspots':{str(n):hotspot(n) for n in SIZES},
              'source_landmarks':LANDMARKS,'animations':THEMES,
              'timing_unit':'1/60 second',
              'status':'prototype; Windows loader verification is separate from manual usability testing'}
    (OUT/'manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'sizes':SIZES,'hotspots':metadata['hotspots']},indent=2))

if __name__=='__main__':main()
