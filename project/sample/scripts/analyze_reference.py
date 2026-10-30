"""Read exact 3-frame samples. Pixel observations are distinct from fitted motion."""
from pathlib import Path
import cv2,json,numpy as np
r=Path(__file__).resolve().parents[1]/'01_레퍼런스'
report=[]
for n in range(0,34):
 im=cv2.imread(str(r/f'deciseconds/frame-{n:03d}.jpg'));b,g,red=cv2.split(im)
 mask=((red.astype(float)>g.astype(float)*1.22)&(red>130)&(g<190)).astype('uint8')*255
 cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
 boxes=[list(map(int,cv2.boundingRect(c))) for c in cnts if cv2.contourArea(c)>12]
 boxes.sort(key=lambda b:b[0]);report.append({'time':n/10,'red_letters':boxes})
(r/'analysis-01/title-observations.json').write_text(json.dumps(report,indent=2))
for x in report: print(x)
base=cv2.imread(str(r/'deciseconds/frame-039.jpg'));ice=[]
for n in range(39,57):
 im=cv2.imread(str(r/f'deciseconds/frame-{n:03d}.jpg'));diff=np.max(cv2.absdiff(im,base),axis=2)
 mask=((diff>48)&(np.min(im,axis=2)<200)).astype('uint8')*255;mask[:,:210]=0;mask[:,490:]=0;mask[790:]=0
 cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
 boxes=[list(map(int,cv2.boundingRect(c))) for c in cnts if cv2.contourArea(c)>60]
 item={'time':n/10,'moving_contours':boxes};ice.append(item);print(item)
(r/'analysis-01/ice-observations.json').write_text(json.dumps(ice,indent=2))
