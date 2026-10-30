"""Visually registered 1-second anchors from the local 1080px reference stills."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
# Screen coordinates in the 1080 x 1080 reference; rotation is clockwise degrees.
# Each named object remains a separate sprite; liquid height is a separate track.
anchors={
'glass':[(0,350,618,0,0),(2.93,350,618,0,0),(3.42,350,618,0,1),(30,350,618,0,1)],
'gin':[(0,-55,300,0,0),(6.2,-55,300,0,0),(6.3,-25,300,0,1),(6.4,40,300,0,1),(6.5,70,300,0,1),(6.8,70,300,0,1),(6.9,90,300,20,1),(7.2,149,329,116,1),(8,149,329,116,1),(9,149,329,116,1),(10,149,329,116,1),(11,70,300,0,1),(11.3,70,300,0,0),(30,70,300,0,0)],
'campari':[(0,70,300,0,0),(11,70,300,0,0),(11.4,70,300,0,1),(12,149,329,116,1),(13,149,329,116,1),(14,149,329,116,1),(15,149,329,116,1),(16,70,300,0,1),(16.25,70,300,0,0),(30,70,300,0,0)],
'vermouth':[(0,70,300,0,0),(16,70,300,0,0),(16.4,70,300,0,1),(17,149,329,116,1),(18,149,329,116,1),(19,149,329,116,1),(20,149,329,116,1),(21,70,300,0,1),(21.2,70,300,0,0),(30,70,300,0,0)],
'ice1':[(0,320,270,0,0),(3.5,320,400,-5,0),(4,310,550,-8,1),(4.5,290,714,7,1),(6,290,714,7,1),(10,290,714,7,1),(11,290,714,7,1),(15,290,700,6,1),(20,290,680,5,1),(21,290,680,5,1),(22,302,676,-8,1),(23,288,681,9,1),(24,300,676,-4,1),(25,290,680,5,1),(30,290,680,5,1)],
'ice2':[(0,355,270,0,0),(4,355,400,9,0),(4.5,355,555,-10,1),(5,350,648,20,1),(11,350,648,20,1),(15,350,630,20,1),(20,350,610,20,1),(21,350,610,20,1),(22,365,618,12,1),(23,340,610,-12,1),(24,359,615,7,1),(25,350,610,20,1),(30,350,610,20,1)],
'ice3':[(0,400,270,0,0),(4.5,400,400,-4,0),(5,400,650,3,1),(5.5,405,706,-18,1),(11,405,706,-18,1),(15,405,692,-18,1),(20,405,672,-18,1),(21,405,672,-18,1),(22,390,670,2,1),(23,407,675,-18,1),(24,392,670,-3,1),(25,405,672,-18,1),(30,405,672,-18,1)],
'spoon':[(0,360,520,7,0),(20.8,360,520,7,0),(21,366,515,7,1),(22,344,515,-3,1),(23,371,515,8,1),(24,341,515,-4,1),(24.4,360,300,0,0),(30,360,300,0,0)],
'peel':[(0,380,300,0,0),(24.8,350,320,0,0),(25,350,380,-4,1),(26,410,428,7,1),(27,430,436,0,1),(30,430,436,0,1)],
'liquid-clear':[(0,350,750,0,0),(6.8,350,750,0,0),(7,350,749,0,1),(8,350,733,0,1),(9,350,713,0,1),(10,350,693,0,1),(11,350,690,0,1),(12,350,690,0,1),(30,350,690,0,1)],
'liquid-red':[(0,350,690,0,0),(12,350,690,0,0),(12.1,350,690,0,1),(13,350,670,0,1),(14,350,638,0,1),(15,350,627,0,1),(16,350,625,0,1),(17,350,625,0,1),(18,350,602,0,1),(19,350,580,0,1),(20,350,562,0,1),(21,350,560,0,1),(30,350,560,0,1)]
}
# Insert exact integer-second samples while retaining necessary sub-second event anchors.
def sample(track,t):
 for a,b in zip(track,track[1:]):
  if a[0]<=t<=b[0]:
   u=(t-a[0])/(b[0]-a[0]); return [t]+[round(x+(y-x)*u,3) for x,y in zip(a[1:],b[1:])]
 return track[-1][:]
tracks={}
for name,track in anchors.items():
 times=sorted(set([float(i) for i in range(31)]+[k[0] for k in track]))
 tracks[name]=[sample(track,t) for t in times]
steps=[{'start':3.6,'end':6.0,'name':'ICE','headline':'FILL','label':'ICE','detail':'big cubes · rocks glass'}, {'start':6.0,'end':11.2,'name':'GIN','headline':'1 oz','label':'GIN','detail':'London dry · 30 mL','pour':[7.2,10.1]}, {'start':11.2,'end':16.2,'name':'CAMPARI','headline':'1 oz','label':'CAMPARI','detail':'the bitter one · 30 mL','pour':[11.8,15.1]}, {'start':16.2,'end':21,'name':'VERMOUTH','headline':'1 oz','label':'SWEET VERMOUTH','detail':'vermouth rosso · 30 mL','pour':[16.8,20.1]}, {'start':21,'end':24.6,'name':'STIR','headline':'20 sec','label':'STIR','detail':'until nice and cold'}, {'start':24.6,'end':26.8,'name':'PEEL','headline':'1','label':'ORANGE PEEL','detail':'express the oils, drop it in'}]
data={'duration':30,'fps':30,'coordinates':'1080px square, origin upper left, rotation clockwise degrees','method':'manual visual registration against 30 exact second stills; integer anchors plus sub-second drop/pour transitions; piecewise interpolation','reference':'../01_레퍼런스/sec-{second:02d}.png','fields':['time','x','y','rotation','opacity'],'tracks':tracks,'steps':steps}
(root/'03_모션제작/motion.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
