"""Validate any prepared episode against the user-approved EP03 drawing method."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

def validate(episode):
 E=Path(episode);A=E/'art';data=json.loads((A/'painting.json').read_text());spec=data['raster_paint'];marks=data['strokes']
 assert not data.get('vector_paint') and spec['no_end_fill'] and spec['single_pigment_per_stroke']
 assert data['initial']=='blank paper'
 assert Image.open(A/spec['reference']).size==(4000,2608)
 people=spec['head_first_people'];last=0
 for p in people:
  rows=[m for m in marks if m['element']==p['key']]
  stages=[[m for m in rows if m['anatomical_stage']==stage] for stage in ['head','body','details']]
  assert all(stages),p['key']
  assert last<=min(m['start'] for m in rows)+1e-8
  for before,after in zip(stages,stages[1:]):assert max(m['end'] for m in before)<=min(m['start'] for m in after)+1e-8
  last=max(m['end'] for m in rows)
 assert last<=min(m['start'] for m in marks if m['element']=='objects')+1e-8
 assert max(m['end'] for m in marks if m['element']=='objects')<=min(m['start'] for m in marks if m['element']=='background')+1e-8
 changes=[]
 bg=np.asarray(Image.open(A/spec['background_exclusion_mask']).convert('L')) if spec.get('background_exclusion_mask') else None
 for i,m in enumerate(marks):
  assert m.get('single_pigment') and len(m['points'])>=2
  pixels=np.asarray(Image.open(A/m['file']).convert('RGBA'));visible=pixels[:,:,3]>0
  assert np.all(pixels[:,:,:3][visible]==m['pigment_rgb']),(i,'mixed RGB')
  if bg is not None and m['element']!='background':
   l,t,r,b=m['bounds'];assert not np.any(visible&(bg[t*4:b*4,l*4:r*4]>0)),(i,'background included in foreground')
  assert m['start']<m['end']<=m['move_end']+1e-8
  if i:
   prev=marks[i-1];gap=m['start']-prev['end'];assert gap>=-1e-8
   if prev['pigment_id']!=m['pigment_id']:
    assert gap>=.13-1e-8
    if prev['element']==m['element']=='background' and prev['phase']==m['phase']=='wash':assert gap>=.2-1e-8
    changes.append(gap)
 return dict(episode=E.name,strokes=len(marks),people=len(people),single_RGB_assets_checked=len(marks),minimum_reload_seconds=min(changes),semantic_exclusions_checked=bg is not None,passed=True)
