"""Register imagegen coat edits against reviewed sprite sheets.

This only measures/crops generated bitmap assets. It never recolors or draws pets.
One common scale is measured per state, while per-frame alpha matching recovers
translation. Source frame selection and reviewed timing remain unchanged.
"""
from pathlib import Path
from copy import deepcopy
from statistics import median
import argparse
import json
import math
from PIL import Image, ImageChops, ImageDraw, ImageFont
import build_complete_theme as compiler


def split_axis(mask,parts,horizontal):
    length=mask.width if horizontal else mask.height;cuts=[0]
    for index in range(1,parts):
        expected=round(index*length/parts);radius=round(length/parts*.16);scores=[]
        for p in range(max(cuts[-1]+1,expected-radius),min(length,expected+radius+1)):
            stripe=mask.crop((p,0,p+1,mask.height) if horizontal else (0,p,mask.width,p+1))
            scores.append((stripe.histogram()[255],abs(p-expected),p))
        cuts.append(min(scores)[2])
    return cuts+[length]


def rectangles(image, grid, threshold=128):
    mask=image.getchannel('A').point(lambda a:255 if a>=threshold else 0)
    cols,rows=grid;ys=split_axis(mask,rows,False);out=[]
    for row in range(rows):
        xs=split_axis(mask.crop((0,ys[row],image.width,ys[row+1])),cols,True)
        out += [[xs[c],ys[row],xs[c+1],ys[row+1]] for c in range(cols)]
    return out


def mask(image, threshold):
    return image.getchannel('A').point(lambda a:255 if a>=threshold else 0)


def intersection(template,target,dx,dy):
    x0,y0=max(0,dx),max(0,dy)
    x1,y1=min(target.width,dx+template.width),min(target.height,dy+template.height)
    if x1<=x0 or y1<=y0:return 0
    a=template.crop((x0-dx,y0-dy,x1-dx,y1-dy))
    b=target.crop((x0,y0,x1,y1))
    return ImageChops.multiply(a,b).histogram()[255]


def register(old,new,scale,point,threshold):
    template=mask(old,threshold).resize((max(1,round(old.width*scale)),max(1,round(old.height*scale))),Image.Resampling.NEAREST)
    target=mask(new,threshold);ob,nb=template.getbbox(),target.getbbox()
    dx=round((nb[0]+nb[2]-ob[0]-ob[2])/2)
    dy=round((nb[1]+nb[3]-ob[1]-ob[3])/2)
    step=4;radius=max(12,round(min(target.size)*.07))
    small_t=template.resize((max(1,round(template.width/step)),max(1,round(template.height/step))),Image.Resampling.NEAREST)
    small_n=target.resize((max(1,round(target.width/step)),max(1,round(target.height/step))),Image.Resampling.NEAREST)
    coarse=[]
    for oy in range(round(dy/step)-math.ceil(radius/step),round(dy/step)+math.ceil(radius/step)+1):
        for ox in range(round(dx/step)-math.ceil(radius/step),round(dx/step)+math.ceil(radius/step)+1):
            coarse.append((intersection(small_t,small_n,ox,oy),-((ox*step-dx)**2+(oy*step-dy)**2),ox,oy))
    best=max(coarse);cx,cy=best[2]*step,best[3]*step
    fine=[]
    for oy in range(cy-step,cy+step+1):
        for ox in range(cx-step,cx+step+1):
            fine.append((intersection(template,target,ox,oy),-((ox-dx)**2+(oy-dy)**2),ox,oy))
    hit,_,dx,dy=max(fine)
    total=template.histogram()[255]+target.histogram()[255]
    confidence=hit/(total-hit) if total>hit else 1
    px,py=round(point[0]*scale+dx),round(point[1]*scale+dy)
    predicted=[px,py];snap=0
    # Native hotspot verification needs opaque contact. Retain the measured point
    # unless transparent; at most 3 source pixels may be nudged into the mark.
    if not(0<=px<new.width and 0<=py<new.height and target.getpixel((px,py))):
        candidates=[]
        for yy in range(max(0,py-3),min(new.height,py+4)):
            for xx in range(max(0,px-3),min(new.width,px+4)):
                if target.getpixel((xx,yy)):candidates.append(((xx-px)**2+(yy-py)**2,xx,yy))
        if candidates:
            dist,px,py=min(candidates);snap=round(dist**.5,3)
    return [px,py],{'scale':round(scale,6),'translation':[dx,dy],
                    'iou':round(confidence,6),'predicted_landmark':predicted,
                    'landmark':[px,py],'opaque':bool(0<=px<new.width and 0<=py<new.height and target.getpixel((px,py))),
                    'snap_source_pixels':snap}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-config',type=Path,required=True)
    parser.add_argument('--assets-dir',type=Path,required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--version',default='1.0.0')
    parser.add_argument('--output-config',type=Path)
    parser.add_argument('--root',type=Path,default=Path.cwd(),help='Base directory for relative source paths (default: current directory)')
    parser.add_argument('--palette',type=int)
    args=parser.parse_args();root=args.root.resolve();assets=args.assets_dir.resolve()
    cfg=json.loads(args.base_config.read_text(encoding='utf-8-sig'))
    cfg['name']=args.name;cfg['version']=args.version
    if args.palette is not None:cfg['pixel_palette_colors']=args.palette
    calibration_file=assets/'calibration.json'
    overrides=json.loads(calibration_file.read_text(encoding='utf-8-sig')) if calibration_file.exists() else {}
    if not isinstance(overrides,dict):raise ValueError('calibration.json must map state IDs to reviewed overrides')
    threshold=cfg.get('pixel_alpha_threshold',128)
    states=[];review={'method':'state_shared_scale_per_frame_binary_alpha_translation','states':{},'missing':[]}
    compiler.ROOT=root
    for oldspec in cfg['states']:
        state_id=oldspec['id'];source=assets/(state_id+'.png')
        if not source.exists():review['missing'].append(state_id);continue
        old=Image.open(root/oldspec['source']).convert('RGBA');new=Image.open(source).convert('RGBA')
        newrects=rectangles(new,oldspec['grid'],threshold)
        selected=oldspec.get('source_frames',list(range(len(newrects))))
        # Existing rects/points have ALREADY been selected. Only use selection
        # indices for the new full sheet; never select the old lists twice.
        oldrects=oldspec.get('source_rects')
        if oldrects is None:oldrects=[rectangles(old,oldspec['grid'],threshold)[i] for i in selected]
        if len(oldrects)!=len(selected) or len(oldspec['landmarks'])!=len(selected):
            raise ValueError('Base selected rectangle/landmark mismatch: '+state_id)
        cells=[];scales=[]
        for k,index in enumerate(selected):
            oc,nc=old.crop(oldrects[k]),new.crop(newrects[index])
            ob,nb=mask(oc,threshold).getbbox(),mask(nc,threshold).getbbox()
            if not ob or not nb:raise ValueError('Empty cell: '+state_id+'/'+str(index))
            scales.append(((nb[2]-nb[0])/(ob[2]-ob[0])+(nb[3]-nb[1])/(ob[3]-ob[1]))/2)
            cells.append((oc,nc))
        scale=median(scales)
        spec=deepcopy(oldspec);spec['source']=source.relative_to(root).as_posix()
        spec['source_rects']=[newrects[i] for i in selected];spec['landmarks']=[];spec['landmark_units']='pixels'
        diagnostics=[]
        for k,(oc,nc) in enumerate(cells):
            point=oldspec['landmarks'][k]
            if oldspec.get('landmark_units','normalized')=='normalized':point=[point[0]*oc.width,point[1]*oc.height]
            mapped,info=register(oc,nc,scale,point,threshold)
            info['source_frame']=selected[k];info['old_rect']=oldrects[k];info['new_rect']=spec['source_rects'][k]
            info['base_landmark']=point
            spec['landmarks'].append(mapped);diagnostics.append(info)
        state_overrides=overrides.get(state_id,{})
        if not isinstance(state_overrides,dict):raise ValueError('State calibration must be an object: '+state_id)
        if set(state_overrides)&{'id','role','source'}:raise ValueError('Calibration must not replace state identity or source')
        spec.update(deepcopy(state_overrides))
        states.append(spec)
        review['states'][state_id]={'shared_scale':scale,'frame_count':len(cells),
                    'minimum_iou':min(x['iou'] for x in diagnostics),'frames':diagnostics}
    cfg['states']=states
    dest=args.output_config or assets/('partial-config.json' if review['missing'] else 'theme-config.json')
    dest.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    (assets/'registration-diagnostics.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
    font_path=next((p for p in ('C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if Path(p).exists()),None)
    font=ImageFont.truetype(font_path,16) if font_path else ImageFont.load_default(size=16)
    board=Image.new('RGB',(1280,max(1,math.ceil(len(states)/4))*320),'#f4efe6');draw=ImageDraw.Draw(board)
    for i,spec in enumerate(states):
        frames,anchor,side=compiler.prepare(spec,cfg);x,y=i%4*320,i//4*320
        art=frames[0].resize((240,240),Image.Resampling.NEAREST);board.paste(art,(x+40,y),art)
        hx,hy=x+40+anchor[0]*5,y+anchor[1]*5
        draw.line((hx-5,hy,hx+5,hy),fill='#00a0ab');draw.line((hx,hy-5,hx,hy+5),fill='#00a0ab')
        draw.text((x+10,y+244),spec['id']+' '+spec['label'],font=font,fill='#493829')
        for j,bg in enumerate(('#fffaf2','#25282d')):
            draw.rectangle((x+10+j*158,y+266,x+154+j*158,y+317),fill=bg)
            board.paste(frames[0],(x+15+j*158,y+268),frames[0])
    board.save(assets/'calibration-review.png')
    print(json.dumps({'ready':len(states),'missing':review['missing'],'config':str(dest),
                     'min_iou':min((v['minimum_iou'] for v in review['states'].values()),default=None)},ensure_ascii=False))


if __name__=='__main__':main()
