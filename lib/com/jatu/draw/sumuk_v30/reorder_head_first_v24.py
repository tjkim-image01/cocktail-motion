"""EP06: paint each head before its body, preserving approved v23 artwork."""
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .build_person_review_v21 import HAIR, clip_paths, polygon
from .build_pigment_review_v22 import SKIN

ROOT = Path(__file__).resolve().parents[1]
EP = ROOT/'episodes/ep06'
ART = EP/'art'


def schedule(marks, start, end, previous=None, lift=.13):
    if not marks:
        return
    changes = sum(a['pigment_id'] != b['pigment_id'] for a,b in zip(marks,marks[1:]))
    initial = lift if previous and previous['pigment_id'] != marks[0]['pigment_id'] else 0
    budget = end-start-initial-changes*lift
    if budget <= 0:
        raise ValueError(f'Insufficient paint time: {start}–{end}, {changes} color changes')
    weights = [max(1, sum(sum(math.dist(a,b) for a,b in zip(path,path[1:])) for path in m['brush_paths']))**.65 for m in marks]
    cursor = start+initial
    for i,(m,weight) in enumerate(zip(marks,weights)):
        if i and m['pigment_id'] != marks[i-1]['pigment_id']:
            cursor += lift
        dt = budget*weight/sum(weights)
        m.update(start=cursor,end=cursor+dt*.95,move_end=cursor+dt)
        cursor += dt


def main():
    backup = EP/'versions/before-head-first-v24'
    backup.mkdir(exist_ok=True)
    for f in [ART/'painting.json', EP/'episode.json',EP/'config/player-settings.json']:
        if not (backup/f.name).exists():
            shutil.copy2(f,backup/f.name)
    data = json.loads((backup/'painting.json').read_text())
    info = json.loads((backup/'episode.json').read_text())
    out = ART/'raster-v24/strokes'
    out.mkdir(parents=True,exist_ok=True)
    marks, shots, people = [], [], []
    emitted = 0
    def split(m,mask,stage):
        nonlocal emitted
        paths = clip_paths(m.get('brush_paths',[m['points']]),mask)
        if not paths:
            return None
        l,t,r,b = m['bounds']
        rgba = np.array(Image.open(ART/m['file']).convert('RGBA'))
        allowed = cv2.resize(mask[t*2:b*2,l*2:r*2],(rgba.shape[1],rgba.shape[0]),interpolation=cv2.INTER_NEAREST)
        rgba[:,:,3] = np.where(allowed>0,rgba[:,:,3],0)
        ys,xs = np.nonzero(rgba[:,:,3]>0)
        if len(xs)<3:
            return None
        x0,y0 = int(xs.min())//4*4,int(ys.min())//4*4
        x1,y1 = math.ceil((xs.max()+1)/4)*4,math.ceil((ys.max()+1)/4)*4
        fn = f'raster-v24/strokes/{emitted:04d}.png'
        Image.fromarray(rgba[y0:y1,x0:x1]).save(ART/fn)
        emitted += 1
        new = copy.deepcopy(m)
        new.update(file=fn,bounds=[l+x0//4,t+y0//4,l+x1//4,t+y1//4],
                   points=[p for path in paths for p in path],brush_paths=paths,
                   anatomical_stage=stage,source_v23_id=m['id'])
        return new
    for i,who in enumerate(['left_woman','right_woman']):
        headmask = polygon(SKIN[0 if i==0 else 2])
        for poly in HAIR[who]:
            headmask |= polygon(poly)
        selected = [m for m in data['strokes'] if m['element']==who]
        head,body,detail = [],[],[]
        for m in selected:
            if m.get('hair_pass'):
                m=copy.deepcopy(m)
                m.update(phase='wash',anatomical_stage='head',head_hair_base=True)
                head.append(m)
            elif m['phase']=='wash':
                part=split(m,headmask,'head')
                if part:head.append(part)
                part=split(m,cv2.bitwise_not(headmask),'body')
                if part:body.append(part)
            else:
                m=copy.deepcopy(m);m['anatomical_stage']='details';detail.append(m)
        order=['ivory','skin','blush','ochre','blue','green','orange','pink','wood','earth','ink']
        head.sort(key=lambda m:(order.index(m['pigment_id']),m.get('source_v23_id',m['id'])))
        # Keep the approved color order throughout the body, with hands attached
        # to the already painted sleeves rather than a separate hand stage.
        body.sort(key=lambda m:m.get('source_v23_id',m['id']))
        start=.8+i*14.6
        schedule(head,start,start+4.2,marks[-1] if marks else None)
        schedule(body,start+4.2,start+10.4,head[-1])
        schedule(detail,start+10.4,start+14.6,body[-1])
        marks.extend(head+body+detail)
        box=[153,100,568,559] if i==0 else [488,175,925,545]
        headbox=[350,116,510,244] if i==0 else [610,185,765,310]
        hair=next((m for m in head if m.get('head_hair_base')),None)
        if hair:
            shots.extend([dict(element=who,start=start,end=hair['start'],box=box),
                          dict(element=who,start=hair['start'],end=start+4.2,box=headbox)])
        else:shots.append(dict(element=who,start=start,end=start+4.2,box=box))
        shots.append(dict(element=who,start=start+4.2,end=start+14.6,box=box))
        people.append(dict(key=who,name=f'인물 {i+1}',head_start=start,
                           body_start=start+4.2,details_start=start+10.4,end=start+14.6))
    marks.extend(copy.deepcopy(m) for m in data['strokes'] if m['element'] in ['objects','background'])
    shots.extend(s for s in info['player_director']['shots'] if s['element'] in ['objects','background'])
    for i,m in enumerate(marks):m['id']=i
    data.update(strokes=marks,method='Head and face colors first; body colors next; fine details; next person; one loaded pigment per stroke')
    data['raster_paint'].update(version=24,head_first_people=people,head_before_body=True,
                                choreography_source='scripts/reorder_head_first_v24.py')
    info.update(player_revision='raster-v24-review',player_only=True,review_status='awaiting-user',
                drawing_order='한 사람 머리·얼굴 채색 → 몸 채색 → 세선 정리 → 다음 사람 → 물건 → 색별 배경')
    info['player_director']['shots']=shots
    (ART/'painting.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (EP/'episode.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    report=dict(episode='ep06',people=people,strokes=len(marks),
                settings_unchanged=(EP/'config/player-settings.json').read_bytes()==(backup/'player-settings.json').read_bytes(),
                settings_sha256=hashlib.sha256((EP/'config/player-settings.json').read_bytes()).hexdigest(),
                background_and_objects_preserved=True,MP4_created=False)
    (ART/'raster-v24/build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
