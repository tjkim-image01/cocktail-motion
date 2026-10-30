"""Rebuild the nine remaining review players using the approved EP06 method.

Existing cleaned paintings remain the source. Heads precede bodies, each brush
loads one constant RGB pigment, all figure colors precede its fine contours,
and objects/background follow the people. No SVG, final-area fill or MP4.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, gaussian_filter1d

from .build_person_review_v21 import clip_paths, curve, polygon, support
from .build_pigment_review_v22 import density
from .reorder_head_first_v24 import schedule
from .trace_art import trace_paths

ROOT=Path(__file__).resolve().parents[1]
PAPER=np.array([248,245,234],np.float32)
PALETTE={
 'ivory':('미색',[181,165,131]),'skin':('살구색',[224,156,122]),
 'pink':('분홍색',[205,100,116]),'orange':('주홍색',[227,83,16]),
 'yellow':('연한 노랑',[232,199,116]),'ochre':('황토색',[207,145,40]),
 'wood':('나무빛 갈색',[151,108,63]),'earth':('짙은 갈색',[115,81,46]),
 'green':('풀빛 연두',[130,153,58]),'deep_green':('짙은 녹색',[74,117,76]),
 'blue':('청록색',[83,137,147]),'sky':('하늘색',[88,140,172]),
 'purple':('보라색',[127,99,146]),'gray':('회색',[105,112,107]),
 'ink':('먹색',[43,42,36]),'umber_ink':('갈색 먹',[74,57,36]),
}
IDS=list(PALETTE)
CENTERS=None


def prepare_palette(wash):
    global PALETTE,IDS,CENTERS
    # Sample each painting's real colors instead of tinting every scene with
    # EP06's clothing palette. Stronger loaded pigments dilute back to these
    # observed colors through alpha, including pale wood and cool stone.
    small=cv2.resize(wash,(500,326),interpolation=cv2.INTER_AREA)
    lab=cv2.cvtColor(small,cv2.COLOR_RGB2LAB)
    cv2.setRNGSeed(2401)
    _,_,centers=cv2.kmeans(lab.reshape(-1,3).astype(np.float32)[::3],18,None,
                          (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,.3),2,cv2.KMEANS_PP_CENTERS)
    centers=centers[np.argsort(-centers[:,0])]
    rgb=cv2.cvtColor(np.uint8(centers)[None,:,:],cv2.COLOR_LAB2RGB)[0]
    palette={}
    for i,color in enumerate(rgb):
        delta=PAPER-color.astype(float)
        positive=delta>0
        depth=min(1.7,float(np.min((PAPER[positive]-8)/delta[positive]))) if np.any(positive) else 1
        pigment=np.clip(np.rint(PAPER-delta*depth),0,255).astype(int).tolist()
        h,s,v=cv2.cvtColor(np.uint8(pigment)[None,None,:],cv2.COLOR_RGB2HSV)[0,0]
        name=('미색' if v>210 else '회색') if s<28 else '분홍빛' if h<9 or h>164 else '주홍빛' if h<18 and s>135 else '살구빛' if h<18 else '나무빛' if h<32 else '풀빛' if h<80 else '청록빛' if h<105 else '푸른빛' if h<132 else '보랏빛'
        palette[f'paint_{i:02d}']=(name+f' {i+1}',pigment)
    palette.update(ink=('먹색',[43,42,36]),umber_ink=('갈색 먹',[74,57,36]))
    PALETTE=palette;IDS=list(palette);CENTERS=centers


def first_spec():
    # Read only literal geometry, never execute the old destructive builder.
    tree=ast.parse((ROOT/'scripts/reorder_first.py').read_text())
    values={}
    for node in tree.body:
        if not isinstance(node,ast.Assign) or not isinstance(node.targets[0],ast.Name):continue
        name=node.targets[0].id
        if name in ['polys','names','people']:
            values[name]=ast.literal_eval(node.value)
        elif name=='heads':
            values[name]={ast.literal_eval(k):ast.literal_eval(v.args[0]) for k,v in zip(node.value.keys,node.value.values)}
    return dict(people=[dict(key=k,poly=values['polys'][k],head=values['heads'][k],secondary=False) for k in values['people']],
                objects=[[(359,381),(487,337),(621,379),(614,410),(582,440),(566,465),(567,509),(535,519),(526,478),(500,465),(474,454),(433,435),(411,417),(368,417)]])


def classify(wash):
    if CENTERS is not None:
        lab=cv2.cvtColor(cv2.bilateralFilter(wash,7,20,7),cv2.COLOR_RGB2LAB).astype(np.float32)
        best=np.full(wash.shape[:2],np.inf,np.float32);labels=np.zeros(wash.shape[:2],np.uint8)
        for i,center in enumerate(CENTERS):
            distance=np.sum((lab-center)**2,axis=2);closer=distance<best
            best[closer]=distance[closer];labels[closer]=i
        return cv2.medianBlur(labels,7)
    smooth=cv2.bilateralFilter(wash,7,18,7)
    h,s,v=cv2.split(cv2.cvtColor(smooth,cv2.COLOR_RGB2HSV))
    result=np.full(h.shape,IDS.index('ivory'),np.uint8)
    result[(s<36)&(v<223)]=IDS.index('gray')
    result[(h>=19)&(h<34)&(s>=55)]=IDS.index('yellow')
    result[(h>=9)&(h<34)&(s>=115)]=IDS.index('ochre')
    result[(h>=7)&(h<34)&(s>=55)&(v<185)]=IDS.index('wood')
    result[(h>=7)&(h<34)&(s>=55)&(v<125)]=IDS.index('earth')
    result[(h>=30)&(h<80)&(s>=40)]=IDS.index('green')
    result[(h>=30)&(h<80)&(s>=40)&(v<155)]=IDS.index('deep_green')
    result[(h>=80)&(h<105)&(s>=25)]=IDS.index('blue')
    result[(h>=105)&(h<132)&(s>=25)]=IDS.index('sky')
    result[(h>=132)&(h<165)&(s>=25)]=IDS.index('purple')
    result[((h<9)|(h>=165))&(s>=40)]=IDS.index('pink')
    result[(h<18)&(s>120)&(v>150)]=IDS.index('orange')
    result[(h<25)&(s>=20)&(s<115)&(v>175)]=IDS.index('skin')
    return cv2.medianBlur(result,5)


def pigment_masks(labels,area,limit):
    counts=np.bincount(labels[area>0],minlength=len(IDS))
    selected=[int(i) for i in np.argsort(-counts) if counts[i]>=24][:limit]
    if not selected:return []
    # Minor shades use the nearest of the actual loaded colors; this avoids
    # dozens of imperceptible reloads on small distant figures.
    selected.sort()
    adjusted=labels.copy()
    colors=np.array([PALETTE[IDS[i]][1] for i in selected],float)
    for i,count in enumerate(counts):
        if count and i not in selected:
            delta=colors-np.array(PALETTE[IDS[i]][1])
            replacement=selected[int(np.argmin(np.sum(delta*delta,axis=1)))]
            adjusted[(labels==i)&(area>0)]=replacement
    return [(IDS[i],np.where((adjusted==i)&(area>0),255,0).astype(np.uint8)) for i in selected]


def pigment_routes(area,width):
    """Follow each color region's long axis, including curved garment sweeps.

    Components stay separate and get explicit pen lifts. A red sleeve never
    uses the same brush as a face or a blue garment next to it.
    """
    count,cc,stats,_=cv2.connectedComponentsWithStats((area>0).astype(np.uint8))
    routes=[]
    for ident in range(1,count):
        if stats[ident,cv2.CC_STAT_AREA]<24:continue
        l,t,w,h=stats[ident,:4]
        ys,xs=np.nonzero(cc[t:t+h,l:l+w]==ident)
        coords=np.column_stack((xs+l,ys+t)).astype(float)/2
        center=coords.mean(axis=0)
        _,vectors=np.linalg.eigh(np.cov(coords.T))
        direction=vectors[:,-1]
        if direction[1]<0 or (abs(direction[1])<.2 and direction[0]<0):direction=-direction
        normal=np.array([-direction[1],direction[0]])
        uv=(coords-center)@np.column_stack([direction,normal])
        local_width=max(1.8,min(width,max(3,min(w,h)/2*.65)))
        local=np.zeros_like(area);local[t:t+h,l:l+w]=np.where(cc[t:t+h,l:l+w]==ident,255,0)
        radius=max(1,math.ceil(local_width))
        guide=cv2.dilate(local,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))
        lo,hi=uv.min(axis=0),uv.max(axis=0)
        cross=np.arange(lo[1],hi[1]+local_width*.25,max(1,local_width*.72))
        if len(cross)==0:cross=np.array([(lo[1]+hi[1])/2])
        for offset in cross:
            bend=local_width*.055*math.sin(offset*.17)
            nodes=[center+direction*lo[0]+normal*offset,
                   center+direction*((lo[0]+hi[0])/2)+normal*(offset+bend),
                   center+direction*hi[0]+normal*offset]
            paths=clip_paths([curve(nodes)],guide)
            if paths:routes.append(dict(paths=paths,width=local_width))
    return routes


def camera_box(area,padding=24):
    ys,xs=np.nonzero(area)
    if not len(xs):return [0,0,1000,652]
    l,t,r,b=xs.min()/2-padding,ys.min()/2-padding,xs.max()/2+padding,ys.max()/2+padding
    w=max(160,r-l);h=max(130,b-t);cx=(l+r)/2;cy=(t+b)/2
    return [max(0,cx-w/2),max(0,cy-h/2),min(1000,cx+w/2),min(652,cy+h/2)]


def build(ep, *, project, source_path, scene):
    global ROOT
    ROOT=Path(project).resolve()
    E=ROOT/'episodes'/ep;A=E/'art';O=A/'raster-v24'
    O.mkdir(exist_ok=True);(O/'strokes').mkdir(exist_ok=True)
    backup=E/'versions/before-sumuk-lib-v30';backup.mkdir(exist_ok=True)
    for source in [A/'painting.json',E/'episode.json',E/'config/player-settings.json']:
        if not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
    old=json.loads((backup/'painting.json').read_text());info=json.loads((backup/'episode.json').read_text())
    spec=scene
    source=Image.open(source_path).convert('RGB')
    logical=source.copy();logical.thumbnail((928,604),Image.Resampling.LANCZOS)
    offset=((1000-logical.width)//2,(652-logical.height)//2)
    plate=Image.new('RGB',(4000,2608),tuple(PAPER.astype(int)))
    plate.paste(source.resize((logical.width*4,logical.height*4),Image.Resampling.LANCZOS),(offset[0]*4,offset[1]*4))
    plate.save(O/'working-reference-4000.png')
    rgb4=np.array(plate);rgb=cv2.resize(rgb4,(2000,1304),interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    smooth=cv2.bilateralFilter(gray,7,22,6)
    closed=cv2.morphologyEx(smooth,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(13,13)))
    ink=(((closed.astype(float)-smooth)>13)|(smooth<112)).astype(np.uint8)*255
    ink=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    remove=cv2.dilate(ink,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    wash=cv2.bilateralFilter(cv2.inpaint(rgb,remove,5,cv2.INPAINT_TELEA),5,10,8)
    wash4=cv2.resize(wash,(4000,2608),interpolation=cv2.INTER_CUBIC)
    Image.fromarray(wash4).save(O/'wash-working-4000.png')
    prepare_palette(wash);families=classify(wash)
    owner=np.zeros((1304,2000),np.int16)
    ownership_order=spec.get('ownership_order',list(reversed(range(len(spec['people'])))))
    for i in ownership_order:owner[polygon(spec['people'][i]['poly'])>0]=i+1
    # White pixels/explicit polygons are semantically background, including
    # spaces beside sleeves and between limbs. They override broad silhouettes.
    exclusions=np.zeros(owner.shape,np.uint8)
    for poly in spec.get('background_exclusions',[]):exclusions|=polygon(poly)
    if spec.get('background_exclusion_mask'):
        path=Path(spec['background_exclusion_mask'])
        if not path.is_absolute():path=ROOT/path
        exclusions=cv2.max(exclusions,np.array(Image.open(path).convert('L').resize((2000,1304),Image.Resampling.NEAREST)))
    owner[exclusions>0]=0
    exclusions4=cv2.resize(exclusions,(4000,2608),interpolation=cv2.INTER_NEAREST)
    if np.any(exclusions4):Image.fromarray(exclusions4).save(O/'background-exclusion-mask.png')
    objects=np.zeros(owner.shape,np.uint8)
    for poly in spec['objects']:objects|=polygon(poly)
    objects[(owner>0)|(exclusions>0)]=0
    background=np.where((owner==0)&(objects==0),255,0).astype(np.uint8)
    content=np.zeros_like(background);content[offset[1]*2:(offset[1]+logical.height)*2,offset[0]*2:(offset[0]+logical.width)*2]=255
    background=cv2.min(background,content)
    marks=[];groups=[];shots=[];people=[];coverage=[]
    def emit(area,paths,width,pid,phase,group,stage,painted=None):
        if not paths:return None
        swept=cv2.min(area,support(paths,width))
        ys,xs=np.nonzero(swept>1)
        if len(xs)<8:return None
        l,t=int(xs.min())//2,int(ys.min())//2;r,b=math.ceil((xs.max()+1)/2),math.ceil((ys.max()+1)/2)
        alpha=cv2.resize(swept[t*2:b*2,l*2:r*2],((r-l)*4,(b-t)*4),interpolation=cv2.INTER_LINEAR).astype(float)/255
        color=PALETTE[pid][1]
        if phase=='wash':strength=density(rgb4[t*4:b*4,l*4:r*4] if stage=='hair' else wash4[t*4:b*4,l*4:r*4],color)
        else:
            base=cv2.cvtColor(wash4[t*4:b*4,l*4:r*4],cv2.COLOR_RGB2GRAY).astype(float)
            desired=cv2.cvtColor(rgb4[t*4:b*4,l*4:r*4],cv2.COLOR_RGB2GRAY).astype(float)
            lum=float(np.array(color)@np.array([.299,.587,.114]))
            strength=np.clip((base-desired)/np.maximum(20,base-lum),0,1)
            strength=np.maximum(strength,np.where(desired<112,np.clip((245-desired)/(245-lum),0,1),0))
        alpha*=strength
        if group!='background':alpha[exclusions4[t*4:b*4,l*4:r*4]>0]=0
        if painted is not None:
            previous=painted[t*4:b*4,l*4:r*4]
            goal=np.maximum(previous,alpha)
            alpha=(goal-previous)/np.maximum(.00001,1-previous)
            previous[:]=goal
        alpha=np.rint(alpha*255).astype(np.uint8)
        if np.count_nonzero(alpha>1)<8:return None
        ys,xs=np.nonzero(alpha>0);x0,y0=int(xs.min())//4*4,int(ys.min())//4*4
        x1,y1=math.ceil((xs.max()+1)/4)*4,math.ceil((ys.max()+1)/4)*4
        a=alpha[y0:y1,x0:x1];rgba=np.zeros((*a.shape,4),np.uint8);rgba[:,:,:3]=color;rgba[:,:,3]=a
        filename=f'raster-v24/strokes/{len(marks):04d}.png';Image.fromarray(rgba).save(A/filename)
        m=dict(id=len(marks),file=filename,bounds=[l+x0//4,t+y0//4,l+x1//4,t+y1//4],
               points=[p for path in paths for p in path],brush_paths=paths,width=width,reveal_width=width,pixel_scale=4,
               pigment_id=pid,pigment_name=PALETTE[pid][0],pigment_rgb=color,single_pigment=True,
               phase=phase,element=group,anatomical_stage='head' if stage=='hair' else stage,
               head_hair_base=stage=='hair',brush_kind='fine' if stage=='hair' or phase=='ink' else 'flat' if width>20 else 'medium',
               label=PALETTE[pid][0]+' · '+{'head':'머리·얼굴 채색','hair':'머릿결 방향 채색','body':'몸 채색','details':'세선 정리','objects':'물건 채색','background':'배경 채색'}[stage])
        marks.append(m);return m
    def washes(area,group,stage,limit,width):
        before=len(marks)
        for pid,color_area in pigment_masks(families,area,limit):
            painted=np.zeros((2608,4000),np.float32)
            covered=np.zeros_like(area)
            routes=pigment_routes(color_area,width)
            # Batch local same-color strokes into assets while preserving their
            # separate paths and pen lifts; tiny texture islands do not each
            # require a separate image request or animation stage.
            for start in range(0,len(routes),12):
                batch=routes[start:start+12];paths=[path for route in batch for path in route['paths']]
                actual_width=max(route['width'] for route in batch)
                emit(color_area,paths,actual_width,pid,'wash',group,stage,painted)
                covered|=cv2.min(color_area,support(paths,actual_width))
            missing=np.where((color_area>0)&(covered<64),255,0).astype(np.uint8)
            corrections=pigment_routes(missing,max(4,min(12,width)))
            for start in range(0,len(corrections),16):
                batch=corrections[start:start+16];paths=[path for route in batch for path in route['paths']]
                actual_width=max(route['width'] for route in batch)
                emit(color_area,paths,actual_width,pid,'wash',group,stage,painted)
                covered|=cv2.min(color_area,support(paths,actual_width))
            target=np.count_nonzero(color_area)
            coverage.append(dict(group=group,stage=stage,pigment=pid,coverage=round(np.count_nonzero(covered>16)/max(1,target),5)))
        return marks[before:]
    def contours(area,group):
        before=len(marks);target=cv2.min(ink,area)
        # Separate real ink centerlines; unrelated contours remain pen-up travel.
        segments=[]
        dist=cv2.distanceTransform(target,cv2.DIST_L2,5)
        for length,pts in trace_paths(target):
            if length<3:continue
            pts=np.asarray(pts,float)/2
            if len(pts)>3:pts=gaussian_filter1d(pts,.35,axis=0)
            xy=np.rint(pts*2).astype(int);xy[:,0]=np.clip(xy[:,0],0,1999);xy[:,1]=np.clip(xy[:,1],0,1303)
            width=max(2.2,min(7,float(np.percentile(dist[xy[:,1],xy[:,0]],90))+1.2))
            segments.append((float(pts[:,1].mean()),pts.tolist(),width))
        segments.sort(key=lambda x:x[0])
        # Local batches reduce texture count while retaining explicit pen lifts.
        for start in range(0,len(segments),8):
            batch=segments[start:start+8];paths=[v[1] for v in batch];width=max(v[2] for v in batch)
            emit(target,paths,width,'ink' if group not in ['objects','background'] else 'umber_ink','ink',group,'details')
        return marks[before:]
    areas=[np.where(owner==i+1,255,0).astype(np.uint8) for i in range(len(spec['people']))]
    weights=[math.sqrt(np.count_nonzero(area)) for area in areas]
    n=len(areas);minimum=min(2.4,35/max(1,n));remaining=36.0-n*minimum;cursor=.8
    for i,(person,area) in enumerate(zip(spec['people'],areas)):
        key=person['key'];start=cursor;end=start+minimum+remaining*weights[i]/sum(weights)
        covered_head=not bool(person.get('head'))
        if covered_head:
            # A hooded rear figure has no visible face polygon in the original
            # plan. Paint the hood's upper quarter first instead of inventing
            # a face or omitting the head stage.
            ys,_=np.nonzero(area);cut=float(ys.min())+(float(ys.max())-ys.min())*.27
            head=np.where(np.indices(area.shape)[0]<=cut,area,0).astype(np.uint8)
        else:head=cv2.min(area,polygon(person['head']))
        body=cv2.subtract(area,head)
        dark=np.where((gray<125)&(head>0),255,0).astype(np.uint8)
        dark=cv2.morphologyEx(dark,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        # Dark hair and hats use narrow directional passes before the body.
        thick=cv2.morphologyEx(dark,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        hair=cv2.min(head,binary_fill_holes(thick>0).astype(np.uint8)*255)
        head_color=cv2.subtract(head,hair)
        first=len(marks);headmarks=washes(head_color,key,'head',4,8)
        painted=np.zeros((2608,4000),np.float32)
        for route in pigment_routes(hair,3.2):
            emit(hair,route['paths'],route['width'],'ink','wash',key,'hair',painted)
        headmarks=marks[first:]
        bodymarks=washes(body,key,'body',8,20)
        details=contours(area,key)
        local=headmarks+bodymarks+details
        schedule(local,start,end,marks[first-1] if first else None)
        if not headmarks or not bodymarks or not details:raise ValueError(f'{ep} {key}: missing anatomical stage {len(headmarks)}/{len(bodymarks)}/{len(details)}')
        people.append(dict(key=key,name=f'인물 {i+1}',head_start=headmarks[0]['start'],body_start=bodymarks[0]['start'],details_start=details[0]['start'],end=end,covered_head=covered_head))
        shots.extend([dict(element=key,start=start,end=bodymarks[0]['start'],box=camera_box(area)),dict(element=key,start=bodymarks[0]['start'],end=end,box=camera_box(area))])
        groups.append(key);cursor=end
        print(ep,key,len(local),'head → body → details',flush=True)
    for key,area,end,limit,width in [('objects',objects,42.8,14,18),('background',background,49.8,18,32)]:
        start=cursor;first=len(marks);washmarks=washes(area,key,key,limit,width);details=contours(area,key)
        local=washmarks+details
        schedule(local,start,end,marks[first-1] if first else None,lift=.2 if key=='background' else .13)
        if not local:raise ValueError(f'{ep}: missing {key}')
        groups.append(key);shots.append(dict(element=key,start=start,end=end,box=[0,0,1000,652] if key=='background' else camera_box(area)));cursor=end
    passes=[]
    for pid in dict.fromkeys(m['pigment_id'] for m in marks if m['element']=='background' and m['phase']=='wash'):
        ms=[m for m in marks if m['element']=='background' and m['phase']=='wash' and m['pigment_id']==pid]
        passes.append(dict(pigment_id=pid,name=PALETTE[pid][0],rgb=PALETTE[pid][1],start=ms[0]['start'],end=ms[-1]['move_end'],strokes=len(ms)))
    data={k:v for k,v in old.items() if k not in ['vector_paint','strokes','raster_paint']}
    labels={p['key']:p['name']+' · 머리부터 몸까지' for p in people}
    labels.update(objects='물건 · 생활의 도구',background='배경 · 색별 채색')
    data.update(strokes=marks,pixel_scale=4,original='raster-v24/working-reference-4000.png',group_order=groups,group_labels=labels,
                initial='blank paper',method='Head colors then body colors then fine ink per person; constant RGB per loaded pigment; source density in alpha only',
                raster_paint=dict(version=24,pixel_scale=4,working_size=[4000,2608],reference='raster-v24/working-reference-4000.png',native_ai_size=list(source.size),
                                  no_end_fill=True,single_pigment_per_stroke=True,color_change_lift_seconds=.13,continuous_mask_paths='all',
                                  head_before_body=True,head_first_people=people,background_color_passes=passes,
                                  pigments={k:dict(name=name,rgb=rgb) for k,(name,rgb) in PALETTE.items()},choreography_source='scripts/build_series_raster_v24.py'))
    if np.any(exclusions4):data['raster_paint'].update(background_exclusion_mask='raster-v24/background-exclusion-mask.png',semantic_background_deferred=True)
    info.update(player_revision='raster-v24-review',player_only=True,review_status='awaiting-user',drawing_order='각 인물 머리·얼굴 채색 → 몸 채색 → 세선 정리 → 다음 인물 → 물건 → 색별 배경')
    info['player_director']['shots']=shots
    # Commit the new review index only after every image has been written.
    (A/'painting.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (E/'episode.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    report=dict(episode=ep,strokes=len(marks),people=people,coverage=coverage,background_color_passes=passes,
                source_sha256=hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),settings_sha256=hashlib.sha256((E/'config/player-settings.json').read_bytes()).hexdigest(),
                settings_unchanged=(E/'config/player-settings.json').read_bytes()==(backup/'player-settings.json').read_bytes(),MP4_created=False)
    (O/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('READY',ep,len(marks),flush=True)
    return report


