"""Use the actual final Flow mouth (also checked against end art), never a newly invented mouth drawing."""
import argparse
from pathlib import Path
import json,cv2,numpy as np

def _project_path():
 parser=argparse.ArgumentParser(description='M013 reference recipe; character-specific coordinates must be adapted for a new character')
 parser.add_argument('project',type=Path)
 return parser.parse_args().project

P=Path(_project_path()).resolve();d=json.loads((P/'face/rig.json').read_text());refs={}
for name,fr in [('open',239),('closed',0)]:
 im=cv2.imread(str(P/f'frames/{fr:04d}.jpg'));m=d['frames'][fr]['mouth'];cx,cy=m['x'],m['y'];ang=m['angle'];gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);mask=np.zeros(gray.shape,np.uint8)
 x0=int(cx-m['w']/2-4);x1=int(cx+m['w']/2+5);y0=int(cy-m['h']/2-4);y1=int(cy+m['h']/2+5)
 tmp=(gray[y0:y1,x0:x1]<205).astype(np.uint8)*255
 contours,_=cv2.findContours(tmp,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
 if name=='open':contours=[max(contours,key=cv2.contourArea)]
 contours=[c for c in contours if cv2.contourArea(c)>1]
 for c in contours:cv2.drawContours(mask[y0:y1,x0:x1],[c],-1,255,-1)
 # Keep the original anti-aliased ink edge, including the dark upper cavity, thin top teeth and broad pink tongue.
 mask=cv2.GaussianBlur(cv2.dilate(mask,np.ones((3,3),np.uint8)),(0,0),.45)
 M=cv2.getRotationMatrix2D((cx,cy),ang*180/np.pi,1);M[:,2]+=[64-cx,48-cy]
 rgb=cv2.warpAffine(im,M,(128,96),flags=cv2.INTER_LINEAR);alpha=cv2.warpAffine(mask,M,(128,96),flags=cv2.INTER_LINEAR)
 cv2.imwrite(str(P/f'face/mouth-{name}.png'),np.dstack([rgb,alpha]))
 co,_=cv2.findContours((alpha>100).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);co=max(co,key=cv2.contourArea)[:,0,:].astype(float)
 ln=np.r_[0,np.cumsum(np.linalg.norm(np.roll(co,-1,axis=0)-co,axis=1))];q=np.linspace(0,ln[-1],64,endpoint=False);ring=np.vstack([co,co[0]])
 pts=np.c_[np.interp(q,ln,ring[:,0])-64,np.interp(q,ln,ring[:,1])-48]
 left=co[np.argmin(co[:,0])]-[64,48];right=co[np.argmax(co[:,0])]-[64,48];base=(left[1]+right[1])/2
 refs[name]={'frame':fr,'rawWidth':m['w'],'rawHeight':m['h'],'angle':ang,'center':[64,48],'baseline':float(base),'outline':np.round(pts,3).tolist()}
d['mouthReference']={'method':'Actual mouth pixel extraction + 64 corresponding Bezier contour points. Open reference is final Flow frame 239, visually compared with original end.jpg. Closed reference is frame 0.','open':refs['open'],'closed':refs['closed']}
(P/'face/rig.json').write_text(json.dumps(d,separators=(',',':')))
print('Open reference:',refs['open']['rawWidth'],refs['open']['rawHeight'],'baseline:',refs['open']['baseline'])
