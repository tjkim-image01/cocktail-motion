"""Preserve original lash/iris pixels; vector outlines constrain V8-style eyelid deformation."""
import argparse
from pathlib import Path
import json,cv2,numpy as np

def _project_path():
 parser=argparse.ArgumentParser(description='M013 reference recipe; character-specific coordinates must be adapted for a new character')
 parser.add_argument('project',type=Path)
 return parser.parse_args().project

P=Path(_project_path()).resolve();D=json.loads((P/'face/rig.json').read_text());R=D['frames']
CW,CH,COLS=116,100,16;atlas=np.zeros((30*CH,COLS*CW,4),np.uint8);repair=atlas.copy();openmask=[];patches=[]
for i,r in enumerate(R):
 im=cv2.imread(str(P/f'frames/{i:04d}.jpg'));ee=[]
 ib,ig,ir=[a.astype(int) for a in cv2.split(im)]
 sk=(ir-ig>18)&(ig-ib>7)&(ig-ib<(ir-ig)*1.15)&(ir>185)&(ig>135)&(ib>110)
 sk[:210]=False;sk[500:]=False;sk[:,:165]=False;sk[:,550:]=False
 fn,fl,fs,fc=cv2.connectedComponentsWithStats(sk.astype(np.uint8));fj=1+np.argmax(fs[1:,4]);fy,fx=np.nonzero(fl==fj)
 owner=np.zeros(sk.shape,np.uint8);cv2.fillConvexPoly(owner,cv2.convexHull(np.c_[fx,fy].astype(np.int32)),255)

 for k,e in enumerate(r['eyes']):
  cx,cy=e['x'],e['y'];x,y=round(cx)-56,round(cy)-57;crop=im[y:y+CH,x:x+CW];b,g,red=[t.astype(int) for t in cv2.split(crop)];yy,xx=np.mgrid[0:CH,0:CW];dx=xx-(cx-x);dy=yy-(cy-y)
  domain=((dx+(8 if k==0 else -6))/53)**2+((dy+8)/47)**2<1
  hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV);blue=cv2.inRange(hsv,(75,60,70),(115,255,255))>0
  inside=domain&(((red-g<18)&(g-b<20)&(g>125))|blue)
  n,l,s,c=cv2.connectedComponentsWithStats(inside.astype(np.uint8));ids=[j for j in range(1,n) if s[j,4]>40]
  by=np.nonzero(blue)[0]
  valid=blue.sum()>450 and len(by)>0 and by.max()-by.min()>29
  alpha=np.zeros((CH,CW),np.uint8)
  if valid and ids:
   # Internal eye whites and iris usually form two components split by the dark pupil.
   chosen=[j for j in ids if np.any(blue&(l==j)) or (s[j,4]>100 and abs(c[j,0]-(cx-x))<35 and -25<c[j,1]-(cy-y)<20)]
   inside=np.isin(l,chosen);near=cv2.dilate(inside.astype(np.uint8),np.ones((9,9),np.uint8))>0
   black=(red<145)&(g<145)&(b<145)&domain
   bn,bl,bs,bc=cv2.connectedComponentsWithStats(black.astype(np.uint8))
   bids=[j for j in range(1,bn) if np.any((bl==j)&near)]
   joined=inside|np.isin(bl,bids)
   joined=cv2.morphologyEx(joined.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
   contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
   if contours:cv2.drawContours(alpha,contours,-1,255,-1)
  else:
   # Original blink: remove only its lashes and the small lid crease, preserving the eyebrow above.
   alpha[((red<180)&(g<165)&(b<155))&domain&(dy>-22)&(dy<26)]=255
   alpha=cv2.dilate(alpha,np.ones((5,5),np.uint8))
  # Include isolated decorative lower lash dots only if below iris, safely away from blush.
  dots=(red<100)&(g<100)&(b<100)&domain&(dy>13)&(dy<31)
  alpha[dots]=255
  protect=(dy<-44)|((red-g<20)&(g-b>18)&(red>160))|((np.abs(dx)>45)&((dy<-20)|(dy>10)))
  brow=(red>95)&(red<225)&(red-g>20)&(g-b>6)&(g<180)&(dy<-26)
  protect|=cv2.dilate(brow.astype(np.uint8),np.ones((3,3),np.uint8))>0
  protect|=owner[y:y+CH,x:x+CW]==0
  # The screen-left upper lash touches the front hair. Own the lash side of that seam,
  # rather than rejecting the whole connected component with the face-skin hull.
  if k==0 and valid:
   lash_poly=np.zeros((CH,CW),np.uint8)
   rel=np.array([[-52,-10],[-46,-31],[-25,-43],[7,-39],[28,-17],[14,-12],[-20,-5],[-43,11],[-51,11]],float)
   cv2.fillPoly(lash_poly,[np.rint(rel+[cx-x,cy-y]).astype(np.int32)],1)
   mascara=cv2.dilate(lash_poly,np.ones((3,3),np.uint8))>0
   upper_black=(red<145)&(g<145)&(b<145)&(dx>-53)&(dx<37)&(dy>-65)&(dy<10)&((dx>-45)|(dy>-24))
   un,ul,us,uc=cv2.connectedComponentsWithStats(upper_black.astype(np.uint8))
   lids=[j for j in range(1,un) if us[j,4]>12 and np.any((ul==j)&(lash_poly>0))]
   mascara|=cv2.dilate(np.isin(ul,lids).astype(np.uint8),np.ones((3,3),np.uint8))>0
   fringe_near=cv2.dilate(mascara.astype(np.uint8),np.ones((7,7),np.uint8))>0
   white_fringe=fringe_near&(red>210)&(g>210)&(b>200)&(np.abs(red-g)<18)&(np.abs(g-b)<18)
   mascara|=white_fringe
   alpha[mascara]=255
   protect[mascara]=False
  alpha[protect]=0
  erase=cv2.GaussianBlur(cv2.dilate(alpha,np.ones((5,5),np.uint8)),(0,0),.7)
  erase[protect]=0
  nslot=i*2+k;ax=nslot%COLS*CW;ay=nslot//COLS*CH
  skin=np.full_like(crop,e['skin'][::-1]);repair[ay:ay+CH,ax:ax+CW,:3]=skin;repair[ay:ay+CH,ax:ax+CW,3]=erase
  ee.append({'crop':crop,'alpha':alpha,'valid':valid,'x':x,'y':y,'ax':ax,'ay':ay})
 patches.append(ee)
for i,r in enumerate(R):
 for k,e in enumerate(r['eyes']):
  a=patches[i][k];src=i
  if not a['valid']:src=min((j for j in range(240) if patches[j][k]['valid']),key=lambda j:abs(j-i))
  o=patches[src][k];rgba=np.dstack([o['crop'],o['alpha']]);atlas[a['ay']:a['ay']+CH,a['ax']:a['ax']+CW]=rgba
  # 64 corresponding samples on the extracted silhouette; the same points move during every blink.
  contours,_=cv2.findContours(o['alpha'],cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);co=max(contours,key=cv2.contourArea)[:,0,:].astype(float) if contours else np.array([[0,0],[1,0],[1,1]])
  delta=np.roll(co,-1,axis=0)-co;length=np.r_[0,np.cumsum(np.linalg.norm(delta,axis=1))];q=np.linspace(0,length[-1],64,endpoint=False);closed=np.vstack([co,co[0]])
  points=np.c_[np.interp(q,length,closed[:,0]),np.interp(q,length,closed[:,1])]
  e.update({'atlas':[a['ax'],a['ay'],CW,CH],'origin':[a['x'],a['y']],'spriteCenter':[R[src]['eyes'][k]['x']-o['x'],R[src]['eyes'][k]['y']-o['y']],'outline':np.round(points-[R[src]['eyes'][k]['x']-o['x'],R[src]['eyes'][k]['y']-o['y']],2).tolist(),'originalOpen':bool(a['valid']),'spriteSource':src})
cv2.imwrite(str(P/'face/eyes-atlas.png'),atlas);cv2.imwrite(str(P/'face/eye-repair-atlas.png'),repair)
(P/'face/rig.json').write_text(json.dumps(D,separators=(',',':')))
print('Extracted original eye pixels + local repair masks + 64-point contours for 480 eyes')
