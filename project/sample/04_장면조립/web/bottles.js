// V4 bottles, pour streams and splash drops from per-frame reference measurements
// (03_모션제작/bottles-v4.json, source 01_레퍼런스/analysis-v4/bottles/README.md).
// Pose: anchor = mouth tip, angle 0 = upright, + = clockwise; art y runs from the tip to the base.
import {sampleRows} from './world.js';
const lerp=(a,b,u)=>a+(b-a)*u;

// shared silhouette (all three overlap 0.93-0.95): lip ring 37×15, neck 33 wide to y 84,
// curved shoulder to the 90px body at y 121, base corners r 10, length 272
function silhouette(dx=0){const p=new Path2D();p.moveTo(-16.5+dx,15);p.lineTo(-16.5+dx,84);p.bezierCurveTo(-17+dx,102,-45+dx,100,-45+dx,121);p.lineTo(-45+dx,262);p.quadraticCurveTo(-45+dx,272,-35+dx,272);
 p.lineTo(35+dx,272);p.quadraticCurveTo(45+dx,272,45+dx,262);p.lineTo(45+dx,121);p.bezierCurveTo(45+dx,100,17+dx,102,16.5+dx,84);p.lineTo(16.5+dx,15);p.closePath();return p;}
const LIP=dx=>{const p=new Path2D();p.roundRect(-18.5+dx,0,37,15,3.5);return p;};
function drawBottle(ctx,B){
 // colour printed off-register: the fill sits a few px left of the ink line (paper gap inside the right edge)
 ctx.fillStyle=B.fill;ctx.fill(silhouette(B.fillDx));ctx.fill(LIP(B.fillDx));
 ctx.strokeStyle=B.highlight;ctx.lineWidth=6;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(-29.5+B.fillDx,127);ctx.lineTo(-29.5+B.fillDx,252);ctx.stroke();
 ctx.strokeStyle=B.ink;ctx.lineWidth=2;ctx.lineJoin='round';ctx.stroke(silhouette());ctx.stroke(LIP(0));
 const L=B.label;ctx.fillStyle=L.bg;ctx.beginPath();ctx.roundRect(-37,159,74,75,2);ctx.fill();ctx.strokeStyle=L.border;ctx.lineWidth=2;ctx.stroke();
 const [t1,t2,col]=L.text;ctx.fillStyle=col;ctx.textAlign='center';ctx.textBaseline='alphabetic';
 ctx.font=`${t1.length>5?15:17}px Lilita`;ctx.fillText(t1,0,195);ctx.font='15px Hand';ctx.fillText(t2,0,216);
}
function drawStream(ctx,S,fr){const p=fr.p;if(!p||p.length<2)return;
 const path=new Path2D();path.moveTo(...p[0]);for(let i=1;i<p.length-1;i++){const m=[(p[i][0]+p[i+1][0])/2,(p[i][1]+p[i+1][1])/2];path.quadraticCurveTo(...p[i],...m);}path.lineTo(...p.at(-1));
 ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=S.ink;ctx.lineWidth=S.outer;ctx.stroke(path);ctx.strokeStyle=S.fill;ctx.lineWidth=S.core;ctx.stroke(path);
 // thin highlight ~70% of the core width from the screen-right ink line (i.e. toward screen-left)
 const off=(S.hlPos-0.5)*S.core;ctx.save();ctx.strokeStyle=S.highlight;ctx.lineWidth=1.6;ctx.beginPath();
 p.forEach(([x,y],i)=>{const q=p[Math.min(p.length-1,i+1)],o=p[Math.max(0,i-1)],dx=q[0]-o[0],dy=q[1]-o[1],L=Math.hypot(dx,dy)||1,nx=dy/L,ny=-dx/L;   // normal pointing screen-left for a downward stream
  i?ctx.lineTo(x+nx*off,y+ny*off):ctx.moveTo(x+nx*off,y+ny*off);});ctx.stroke();ctx.restore();}
function drawDrops(ctx,list){for(const [x,y,r,h,kind] of list){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);if(kind==='bubble'){ctx.strokeStyle=h;ctx.lineWidth=1.5;ctx.stroke();}else{ctx.fillStyle=h;ctx.fill();}}}

export async function createBottles(root){
 const D=await fetch(root+'03_모션제작/bottles-v4.json').then(r=>r.json());
 return {data:D,draw(ctx,t){const u=t*30,f=Math.floor(u+1e-6);
  for(const [name,S] of Object.entries(D.streams)){const fr=S.frames[String(f)];if(!fr)continue;if(fr.p)drawStream(ctx,S,fr);if(fr.d)drawDrops(ctx,fr.d);}
  for(const B of Object.values(D.bottles)){const r=sampleRows(B.track,u);if(!r)continue;const [x,y,a]=r;
   ctx.save();ctx.translate(x,y);ctx.rotate(a*Math.PI/180);drawBottle(ctx,B);ctx.restore();}
 }};
}
