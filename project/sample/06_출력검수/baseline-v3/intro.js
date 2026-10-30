const clamp=v=>Math.max(0,Math.min(1,v));
const lerp=(a,b,p)=>a+(b-a)*p;
export function linearSample(keys,t){if(t<=keys[0][0])return keys[0].slice(1);for(let i=0;i<keys.length-1;i++){let a=keys[i],b=keys[i+1];if(t<=b[0]){const p=(t-a[0])/(b[0]-a[0]);return a.slice(1).map((v,j)=>lerp(v,b[j+1],p));}}return keys.at(-1).slice(1);}
export function introTitle(ctx,t,data){
 const title=data.title,[cy,groupScale]=linearSample(title.headerKeys,t);const letterStates=[];
 ctx.save();ctx.translate(540,cy);ctx.scale(groupScale,groupScale);ctx.translate(-540,-490);
 for(let i=0;i<title.text.length;i++){
  const age=t-title.starts[i];const scale=age<0?0:linearSample(title.popKeys,age)[0];
  const wobble=age<0.4?Math.sin(age*27)*Math.exp(-age*9)*7:0;
  const x=title.centers[i],bottom=title.bottom-(age>0?Math.sin(Math.min(age/.4,1)*Math.PI)*3:0);
  const state={letter:title.text[i],age,scale,x,bottom,rotation:title.angles[i]+wobble};letterStates.push(state);if(scale<=0)continue;
  ctx.save();ctx.translate(x,bottom);ctx.rotate(state.rotation*Math.PI/180);ctx.scale(scale,scale);
  ctx.font='150px Lucky';ctx.textAlign='left';ctx.textBaseline='alphabetic';const m=ctx.measureText(state.letter);
  const w=m.actualBoundingBoxLeft+m.actualBoundingBoxRight,h=m.actualBoundingBoxAscent+m.actualBoundingBoxDescent;
  ctx.scale(title.widths[i]/w,title.height/h);ctx.translate((m.actualBoundingBoxLeft-m.actualBoundingBoxRight)/2,-m.actualBoundingBoxDescent);
  ctx.lineJoin='round';ctx.strokeStyle='#302d31';ctx.lineWidth=5.6;ctx.strokeText(state.letter,0,2.2);ctx.strokeText(state.letter,0,0);ctx.fillStyle='#e4797e';ctx.fillText(state.letter,0,0);ctx.restore();
 }
 ctx.restore();
 function sub(str,y,opacity,size){if(opacity<=0)return;ctx.save();ctx.globalAlpha=opacity;ctx.font=`${size}px Hand`;ctx.textAlign='center';ctx.fillStyle='#6d6765';ctx.fillText(str,540,y);ctx.restore();}
 sub('a 30 second recipe',616,clamp((t-1.4)/.4)*(1-clamp((t-2.5)/.2)),32);
 sub('equal parts  ·  stirred  ·  on the rocks',204,clamp((t-3.2)/.4),29);
 return {letters:letterStates,centerY:cy,groupScale};
}
// v3: one measured sample per reference frame (30fps), linear in between.
const FPS=30;
function framePose(ice,t){const f=ice.frames,u=t*FPS;if(u<=f[0][0])return f[0].slice(1);if(u>=f.at(-1)[0])return f.at(-1).slice(1);
 let i=0;while(f[i+1][0]<u)i++;const a=f[i],b=f[i+1],p=(u-a[0])/(b[0]-a[0]);return a.slice(1).map((v,j)=>lerp(v,b[j+1],p));}
export function introIce(t,ice){const [x,y,rotation]=framePose(ice,t);return {x,y,rotation,opacity:t*FPS>=ice.startFrame-1e-6?1:0,scaleX:ice.scale,scaleY:ice.scale};}
export function iceLanded(t,data){return data.ice.filter(i=>t*FPS>=i.settleFrame-1e-6).length;}
// Impact marks are held per reference frame and ride with their cube without rotating.
export function iceMarks(ctx,t,states,data){
 const marks=data.iceMarks[String(Math.floor(t*FPS+1e-6))];if(!marks)return;
 ctx.save();ctx.strokeStyle='#302d31';ctx.lineCap='round';
 for(const [id,x1,y1,x2,y2,w] of marks){const s=states[id];if(!s)continue;ctx.lineWidth=w+0.6;ctx.beginPath();ctx.moveTo(s.x+x1,s.y+y1);ctx.lineTo(s.x+x2,s.y+y2);ctx.stroke();}
 ctx.restore();
}
// Cube art measured from an axis-aligned reference crop: 71px rounded square, ink outline,
// pale fill lighter at the top-left, grey front-corner highlight (top line, right line, corner curve).
export function drawIceTexture(size=256){
 const c=document.createElement('canvas');c.width=c.height=size;const g=c.getContext('2d');g.scale(size/100,size/100);g.translate(50,50);
 const L=-35.8,T=-37,W=71.5,H=71,R=13;
 const path=new Path2D();
 // hand-drawn outline: rounded square sampled as a polyline with a small, fixed wobble
 const pts=[];const per=[[L+R,T,L+W-R,T],[L+W,T+R,L+W,T+H-R],[L+W-R,T+H,L+R,T+H],[L,T+H-R,L,T+R]];const corners=[[L+W-R,T+R,-90],[L+W-R,T+H-R,0],[L+R,T+H-R,90],[L+R,T+R,180]];
 for(let k=0;k<4;k++){const [x1,y1,x2,y2]=per[k];for(let i=0;i<=12;i++){const u=i/12;pts.push([lerp(x1,x2,u),lerp(y1,y2,u)]);}const [cx,cy,a0]=corners[k];for(let i=1;i<10;i++){const a=(a0+i*9)*Math.PI/180;pts.push([cx+Math.cos(a)*R,cy+Math.sin(a)*R]);}}
 pts.forEach(([x,y],i)=>{const n=Math.sin(i*1.7)*0.35+Math.sin(i*0.43)*0.45;const a=Math.atan2(y,x);const px=x+Math.cos(a)*n,py=y+Math.sin(a)*n;i?path.lineTo(px,py):path.moveTo(px,py);});path.closePath();
 const fill=g.createLinearGradient(L,T,L+W,T+H);fill.addColorStop(0,'#f9fdff');fill.addColorStop(.45,'#eff9fc');fill.addColorStop(1,'#eef8fb');
 g.fillStyle=fill;g.fill(path);
 g.strokeStyle='#9aa5a9';g.lineWidth=1.5;g.lineCap='round';
 g.beginPath();g.moveTo(-24,-18.5);g.quadraticCurveTo(-3,-18,12,-19.2);g.quadraticCurveTo(19,-20,26,-29);g.stroke();
 g.beginPath();g.moveTo(16.8,-17.5);g.lineTo(17.4,24);g.stroke();
 g.strokeStyle='#29292b';g.lineWidth=3.1;g.lineJoin='round';g.stroke(path);
 return c;
}
