#!/usr/bin/env python3
"""Track small facial regions; extract palettes/iris images and fit Bezier-compatible eye/mouth rigs."""
import json, math
import argparse
from pathlib import Path
import cv2
import numpy as np

def _project_path():
 parser=argparse.ArgumentParser(description='M013 reference recipe; character-specific coordinates must be adapted for a new character')
 parser.add_argument('project',type=Path)
 return parser.parse_args().project

P=Path(_project_path()).resolve()
OUT=P/'face';OUT.mkdir(exist_ok=True)
imgs=[cv2.imread(str(P/f'frames/{i:04d}.jpg')) for i in range(240)]
centers=np.full((240,2,2),np.nan);radii=np.full((240,2,2),np.nan)
for i,im in enumerate(imgs):
 hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV);m=cv2.inRange(hsv,(75,60,70),(115,255,255));m[:210]=0;m[410:]=0;m[:,:180]=0;m[:,510:]=0
 n,l,s,c=cv2.connectedComponentsWithStats(m)
 ids=sorted([j for j in range(1,n) if s[j,4]>200 and 15<s[j,2]<60 and 8<s[j,3]<65],key=lambda j:c[j,0])
 if len(ids)==2:
  for eye,j in enumerate(ids):
   if s[j,3]<22:continue
   centers[i,eye]=c[j];radii[i,eye]=[s[j,2]/2+3,s[j,3]/2+3]
for e in range(2):
 for d in range(2):
  ok=np.isfinite(centers[:,e,d]);centers[:,e,d]=np.interp(np.arange(240),np.where(ok)[0],centers[ok,e,d]);radii[:,e,d]=np.interp(np.arange(240),np.where(ok)[0],radii[ok,e,d])
# Narrow inferred lids during original blinks are discarded; the user controls all blinking independently.
records=[]
for i,im in enumerate(imgs):
 eyes=centers[i];mid=eyes.mean(0);diff=eyes[1]-eyes[0];angle=math.atan2(diff[1],diff[0]);scale=np.linalg.norm(diff)/140
 gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);mask=np.zeros(gray.shape,np.uint8)
 x0,x1=round(mid[0]-66*scale),round(mid[0]+62*scale);y0,y1=round(mid[1]+60*scale),round(mid[1]+127*scale)
 mask[y0:y1,x0:x1]=(gray[y0:y1,x0:x1]<105).astype(np.uint8)
 n,l,s,c=cv2.connectedComponentsWithStats(mask)
 ids=[j for j in range(1,n) if s[j,4]>8 and s[j,2]>6 and s[j,2]<100 and s[j,3]<60 and s[j,0]>x0+1 and s[j,0]+s[j,2]<x1-1 and s[j,1]>y0 and s[j,1]+s[j,3]<y1-1]
 if ids:
  ids=sorted(ids,key=lambda j:s[j,4],reverse=True)
  if s[ids[0],3]>15:ids=ids[:1]
  else:ids=[j for j in ids if s[j,3]<18]
  xx0=min(s[j,0] for j in ids);xx1=max(s[j,0]+s[j,2] for j in ids);yy0=min(s[j,1] for j in ids);yy1=max(s[j,1]+s[j,3] for j in ids)
 else:xx0,xx1,yy0,yy1=mid[0]-35,mid[0]+35,mid[1]+80,mid[1]+88
 mouth={'x':float((xx0+xx1)/2),'y':float((yy0+yy1)/2),'w':float(max(50*scale,xx1-xx0)),'h':float(max(3,yy1-yy0)),'angle':angle}
 entries=[]
 for e,(cx,cy) in enumerate(eyes):
  # Clip masks remain inside the face and below eyebrows. Blue iris sampling selects open examples.
  entries.append({'x':float(cx),'y':float(cy),'rx':float(radii[i,e,0]),'ry':float(radii[i,e,1]),'angle':angle,'side':e})
 records.append({'eyes':entries,'mouth':mouth,'scale':float(scale)})
# Fill only local eye/mouth patches; retain the exact original full frame around them.
# A low-frequency skin plane excludes lashes, eyebrows, whites, iris, blush and hair from the colour samples.
for i,(im,r) in enumerate(zip(imgs,records)):
 patches=[]
 for k,e in enumerate(r['eyes']):
  cx,cy=e['x'],e['y'];rx,ry=e['rx'],e['ry'];
  x0,x1=int(cx-50),int(cx+51);y0,y1=int(cy-51),int(cy+35)
  patches.append((f'eye{k}',x0,y0,x1,y1,cx,cy))
 mo=r['mouth'];cx,cy=mo['x'],mo['y'];w=max(mo['w'],70)
 patches.append(('mouth',int(cx-w/2-9),int(cy-mo['h']/2-9),int(cx+w/2+10),int(cy+mo['h']/2+10),cx,cy))
 for name,x0,y0,x1,y1,cx,cy in patches:
  crop=im[y0:y1,x0:x1];rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB).astype(float);yy,xx=np.mgrid[y0:y1,x0:x1];b,g,red=cv2.split(crop)
  skin=(red.astype(int)-g.astype(int)>12)&(g.astype(int)-b.astype(int)>7)&(red>210)&(g>160)&(b>130)
  # Skin sampling at the sides and below feature; exclude blush and interior eye.
  if name.startswith('eye'):skin&=((xx<cx-36)|(xx>cx+32)|(yy>cy+27))
  else:skin&=((yy<cy-mo['h']/2-4)|(yy>cy+mo['h']/2+4))
  if skin.sum()<10:color=np.median(rgb.reshape(-1,3),axis=0)
  else:color=np.median(rgb[skin],axis=0)
  target=r['eyes'][int(name[-1])] if name.startswith('eye') else mo
  target['skin']=[round(float(v)) for v in color]
  target['patch']=[x0,y0,x1-x0,y1-y0]
 # Eye repair backgrounds generated as local patches with feature-adaptive alpha.
# Representative extracted original iris textures, one for each eye, with an alpha ellipse.
ref=0
for k,e in enumerate(records[ref]['eyes']):
 cx,cy=round(e['x']),round(e['y']);rx,ry=round(e['rx']),round(e['ry']);crop=imgs[ref][cy-ry:cy+ry+1,cx-rx:cx+rx+1].copy()
 alpha=np.zeros(crop.shape[:2],np.uint8);cv2.ellipse(alpha,(rx,ry),(rx-1,ry-1),0,0,360,255,-1)
 cv2.imwrite(str(OUT/f'iris-{k}.png'),np.dstack([crop,alpha]))
# Export source feature crops for provenance and inspection (not runtime full-frame substitutes).
for k,e in enumerate(records[0]['eyes']):
 x,y,w,h=e['patch'];cv2.imwrite(str(OUT/f'extracted-eye-{k}.png'),imgs[0][y:y+h,x:x+w])
mo=records[150]['mouth'];x,y,w,h=mo['patch'];cv2.imwrite(str(OUT/'extracted-mouth.png'),imgs[150][y:y+h,x:x+w])
(OUT/'rig.json').write_text(json.dumps({'method':'Local feature tracking + extracted iris texture + same-topology cubic Bezier lids and viseme contours. V8 lash-ownership and local skin-fill principles.','referenceFrame':0,'mouthReferenceFrame':150,'frames':records},separators=(',',':')))
# Tracking contact sheet
sheet=np.full((3*260,8*255,3),245,np.uint8)
for k,i in enumerate(range(0,240,10)):
 im=imgs[i].copy();r=records[i]
 for e in r['eyes']:cv2.ellipse(im,(round(e['x']),round(e['y'])),(42,45),0,0,360,(0,220,0),2)
 mo=r['mouth'];cv2.rectangle(im,(int(mo['x']-mo['w']/2-8),int(mo['y']-mo['h']/2-8)),(int(mo['x']+mo['w']/2+8),int(mo['y']+mo['h']/2+8)),(0,0,255),2)
 crop=im[210:480,180:470];crop=cv2.resize(crop,(250,233));x=k%8*255;y=k//8*260;sheet[y:y+233,x:x+250]=crop;cv2.putText(sheet,str(i),(x+5,y+252),0,.5,(0,0,0),1)
cv2.imwrite(str(P/'qa/feature-tracking.jpg'),sheet)
print('Saved local rigs for',len(records),'frames')
