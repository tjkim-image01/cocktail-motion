// V4 glass world drawn from per-frame reference measurements (03_모션제작/glass-v4.json,
// source 01_레퍼런스/analysis-v4/glass/README.md).  Geometry is the frame-119 glass in screen px.
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const lerp=(a,b,u)=>a+(b-a)*u;
const INK='#2f292c';
export function keyed(keys,u){if(u<=keys[0][0])return keys[0][1];for(let i=0;i<keys.length-1;i++){const [a,va]=keys[i],[b,vb]=keys[i+1];if(u<=b)return lerp(va,vb,(u-a)/(b-a));}return keys.at(-1)[1];}
// rows [[frame, ...values]] sorted: linear between neighbouring frames, null outside
export function sampleRows(rows,u){if(!rows.length||u<rows[0][0]||u>rows.at(-1)[0])return null;let lo=0,hi=rows.length-1;
 while(hi-lo>1){const m=(lo+hi)>>1;if(rows[m][0]<=u)lo=m;else hi=m;}const a=rows[lo],b=rows[hi];if(a===b||b[0]===a[0])return a.slice(1);
 const p=(u-a[0])/(b[0]-a[0]);return a.slice(1).map((v,j)=>typeof v==='number'&&typeof b[j+1]==='number'?lerp(v,b[j+1],p):(p<.5?v:b[j+1]));}
const hex=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
const css=c=>`rgb(${c.map(v=>Math.round(clamp(v,0,255))).join(',')})`;
const mixc=(a,b,m)=>a.map((v,i)=>lerp(v,b[i],m));

// --- glass geometry (frame 119) as polylines, so every stroke can be drawn partially ---
const CX=353.3,CY=457.0,RX=142.95,RY=22.25;
const pl={line:(a,b,n=40)=>Array.from({length:n+1},(_,i)=>[lerp(a[0],b[0],i/n),lerp(a[1],b[1],i/n)]),
 quad:(a,c,b,n=60)=>Array.from({length:n+1},(_,i)=>{const u=i/n;return [(1-u)**2*a[0]+2*(1-u)*u*c[0]+u*u*b[0],(1-u)**2*a[1]+2*(1-u)*u*c[1]+u*u*b[1]];}),
 arc:(a0,a1,n=80)=>Array.from({length:n+1},(_,i)=>{const a=lerp(a0,a1,i/n);return [CX+RX*Math.cos(a),CY+RY*Math.sin(a)];})};
const STROKES={left:pl.line([210.4,457],[233.5,782]),right:pl.line([496.2,457],[470,782]),
 rimBack:pl.arc(Math.PI,2*Math.PI),rimFrontL:pl.arc(Math.PI,Math.PI/2),rimFrontR:pl.arc(0,Math.PI/2),
 bottom:pl.quad([233.5,782],[353,814],[470,782]),innerBottom:pl.quad([240,746.8],[352,765.2],[463,747.3])};
function strokePart(ctx,pts,frac,fromEnd){if(frac<=0)return;const n=pts.length-1,k=frac*n,P=fromEnd?[...pts].reverse():pts;ctx.beginPath();ctx.moveTo(...P[0]);
 for(let i=1;i<=Math.floor(k);i++)ctx.lineTo(...P[i]);const r=k-Math.floor(k);if(r>0&&Math.floor(k)<n){const a=P[Math.floor(k)],b=P[Math.floor(k)+1];ctx.lineTo(lerp(a[0],b[0],r),lerp(a[1],b[1],r));}ctx.stroke();}
function silhouette(ctx){ctx.beginPath();ctx.ellipse(CX,CY,RX,RY,0,Math.PI,2*Math.PI);ctx.lineTo(470,782);ctx.quadraticCurveTo(353,814,233.5,782);ctx.closePath();}
function interior(ctx){ctx.beginPath();ctx.moveTo(212,457);ctx.lineTo(234.5,781);ctx.quadraticCurveTo(353,812,469,781);ctx.lineTo(494.6,457);ctx.closePath();}

function glassBack(ctx,G,u){const E=G.entrance,fa=u>=114?1:keyed(E.fill,u),ba=u>=114?1:keyed(E.base,u);
 if(fa>0){ctx.save();ctx.globalAlpha=fa;ctx.fillStyle='#ddeff2';silhouette(ctx);ctx.fill();ctx.restore();}
 if(ba>0){ctx.save();ctx.globalAlpha=ba;ctx.fillStyle='#c3dfeb';ctx.beginPath();ctx.moveTo(240,746.8);ctx.quadraticCurveTo(352,765.2,463,747.3);ctx.lineTo(470,782);ctx.quadraticCurveTo(353,814,233.5,782);ctx.closePath();ctx.fill();ctx.restore();}}
function glassLines(ctx,G,u){const E=G.entrance.strokes;ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
 for(const [name,pts] of Object.entries(STROKES)){const s=E[name],frac=u>=120?1:keyed(s.keys,u);ctx.strokeStyle=name==='innerBottom'?'#8c9fa5':INK;ctx.lineWidth=name==='innerBottom'?2:2.4;strokePart(ctx,pts,frac,s.from==='end');}
 ctx.restore();}
function highlights(ctx,G,u){const a=u>=114?1:keyed(G.entrance.highlight,u);if(a<=0)return;ctx.save();ctx.globalAlpha=a;ctx.lineCap='round';
 for(const [x1,y1,x2,y2,w,c] of [[489.2,480,483.8,562,2.3,'#f0f6f6'],[234.7,506.9,257.3,692.8,6.6,'#f0f9fe'],[253.3,524.2,272.1,600,2.7,'#e8f9fb'],[483.2,563.9,467.3,777.9,2.8,'#f4f6f9']]){ctx.strokeStyle=c;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
 ctx.restore();}

// --- liquid: ellipse surface (lighter band between its arcs) over a body that fills the glass ---
const halfW=y=>122.5-0.075*(y-580);
function liquidAt(G,u){const r=sampleRows(G.liquid,u);if(!r)return null;const [yc,b,body,band]=r;return {yc,b,body:hex(body),band:hex(band)};}
function drawLiquid(ctx,L){const a=halfW(L.yc),ab=halfW(745);
 ctx.save();interior(ctx);ctx.clip();
 const xl=349-halfW(740),xr=349+halfW(740);
 ctx.fillStyle=css(L.body);ctx.beginPath();ctx.moveTo(349-a,L.yc);ctx.lineTo(xl,740);ctx.quadraticCurveTo(xl+1,757,xl+24,757);ctx.lineTo(xr-24,757);ctx.quadraticCurveTo(xr-1,757,xr,740);ctx.lineTo(349+a,L.yc);ctx.ellipse(349,L.yc,a,L.b,0,0,Math.PI);ctx.closePath();ctx.fill();
 // dark contour along the liquid bottom: it separates the liquid from the thick glass base
 ctx.strokeStyle=css(mixc(L.body,[47,41,44],0.5));ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(xl+2,748);ctx.quadraticCurveTo(xl+3,756.5,xl+24,756.5);ctx.lineTo(xr-24,756.5);ctx.quadraticCurveTo(xr-3,756.5,xr-2,748);ctx.stroke();
 ctx.fillStyle=css(L.band);ctx.beginPath();ctx.ellipse(349,L.yc,a,L.b,0,0,Math.PI*2);ctx.fill();
 ctx.strokeStyle=css(mixc(L.body,[47,41,44],0.45));ctx.lineWidth=1.8;ctx.stroke();
 ctx.restore();}

// the reference tints everything below the back arc of the surface ellipse (the band counts as liquid)
function underSurface(ctx,L){ctx.beginPath();ctx.ellipse(349,L.yc,halfW(L.yc),L.b,0,0,Math.PI*2);ctx.rect(0,L.yc,1080,1080-L.yc);}
function ripples(ctx,L,u){const a=halfW(L.yc);ctx.save();ctx.strokeStyle=css(mixc(L.band,L.body,0.7));ctx.lineWidth=1.5;
 for(let k=0;k<2;k++){const ph=((u/24)+k*0.5)%1,s=0.25+0.6*ph;ctx.globalAlpha=0.7*(1-ph);ctx.beginPath();ctx.ellipse(349,L.yc,a*s,L.b*s,0,0,Math.PI*2);ctx.stroke();}ctx.restore();}
// --- ice cube (same art as V3), optionally tinted below the waterline ---
const ICE={fill:[[249,253,255],[239,249,252],[238,248,251]],line:[154,165,169],ink:[41,41,43]};
let cubePath=null;
function cube(){if(cubePath)return cubePath;const L=-35.8,T=-37,W=71.5,H=71,R=13,pts=[];
 const per=[[L+R,T,L+W-R,T],[L+W,T+R,L+W,T+H-R],[L+W-R,T+H,L+R,T+H],[L,T+H-R,L,T+R]],cs=[[L+W-R,T+R,-90],[L+W-R,T+H-R,0],[L+R,T+H-R,90],[L+R,T+R,180]];
 for(let k=0;k<4;k++){const [x1,y1,x2,y2]=per[k];for(let i=0;i<=12;i++)pts.push([lerp(x1,x2,i/12),lerp(y1,y2,i/12)]);const [cx,cy,a0]=cs[k];for(let i=1;i<10;i++){const a=(a0+i*9)*Math.PI/180;pts.push([cx+Math.cos(a)*R,cy+Math.sin(a)*R]);}}
 const p=new Path2D();pts.forEach(([x,y],i)=>{const n=Math.sin(i*1.7)*0.35+Math.sin(i*0.43)*0.45,a=Math.atan2(y,x);i?p.lineTo(x+Math.cos(a)*n,y+Math.sin(a)*n):p.moveTo(x+Math.cos(a)*n,y+Math.sin(a)*n);});p.closePath();return cubePath=p;}
function drawCube(ctx,tint){const c=k=>tint?css(mixc(ICE.fill[k],tint.col,tint.m)):css(ICE.fill[k]);
 const g=ctx.createLinearGradient(-36,-37,36,34);g.addColorStop(0,c(0));g.addColorStop(.45,c(1));g.addColorStop(1,c(2));ctx.fillStyle=g;ctx.fill(cube());
 ctx.strokeStyle=tint?css(mixc(ICE.line,tint.col,tint.m)):css(ICE.line);ctx.lineWidth=1.5;ctx.lineCap='round';
 ctx.beginPath();ctx.moveTo(-24,-18.5);ctx.quadraticCurveTo(-3,-18,12,-19.2);ctx.quadraticCurveTo(19,-20,26,-29);ctx.stroke();ctx.beginPath();ctx.moveTo(16.8,-17.5);ctx.lineTo(17.4,24);ctx.stroke();
 if(tint){ctx.save();ctx.translate(-1.6,1.6);ctx.strokeStyle=`rgba(255,255,255,${tint.stir?0.35:0.85})`;ctx.lineWidth=2;ctx.stroke(cube());ctx.restore();}   // light rim on the lower-left edge in liquid
 ctx.strokeStyle=tint?css(mixc(ICE.ink,tint.col.map(v=>v*(tint.stir?1:0.6)),tint.m)):css(ICE.ink);ctx.lineWidth=3.1;ctx.lineJoin='round';ctx.stroke(cube());}
export function drawIce(ctx,x,y,angle,scale,L,m,stir=false){
 ctx.save();ctx.translate(x,y);ctx.rotate(angle*Math.PI/180);ctx.scale(scale,scale);drawCube(ctx,null);ctx.restore();
 if(!L)return;ctx.save();underSurface(ctx,L);ctx.clip();ctx.translate(x,y);ctx.rotate(angle*Math.PI/180);ctx.scale(scale,scale);drawCube(ctx,{col:L.body,m,stir});ctx.restore();}

// --- bar spoon: ball, twisted shaft, bowl; tinted where it is under the surface ---
function spoonShape(ctx,bx,by,a,Lb,tint){const sx=-Math.sin(a*Math.PI/180),sy=Math.cos(a*Math.PI/180),ex=bx+sx*Lb,ey=by+sy*Lb;
 const metal=tint?css(mixc([188,189,195],tint.col,tint.m)):'#bcbdc3',ink=tint?css(mixc([37,35,34],tint.col.map(v=>v*0.3),tint.m)):'#252322';
 ctx.lineCap='round';ctx.strokeStyle=ink;ctx.lineWidth=7;ctx.beginPath();ctx.moveTo(bx,by);ctx.lineTo(ex,ey);ctx.stroke();ctx.strokeStyle=metal;ctx.lineWidth=3.2;ctx.stroke();
 ctx.strokeStyle=ink;ctx.lineWidth=1.1;for(let d=24;d<Lb-22;d+=9){const px=bx+sx*d,py=by+sy*d;ctx.beginPath();ctx.moveTo(px-sy*3-sx*2,py+sx*3-sy*2);ctx.lineTo(px+sy*3+sx*2,py-sx*3+sy*2);ctx.stroke();}
 ctx.save();ctx.translate(ex,ey);ctx.rotate(Math.atan2(sy,sx)-Math.PI/2);ctx.beginPath();ctx.ellipse(0,0,8.5,14,0,0,Math.PI*2);ctx.fillStyle=metal;ctx.fill();ctx.lineWidth=2.2;ctx.strokeStyle=ink;ctx.stroke();ctx.restore();
 ctx.beginPath();ctx.arc(bx,by,11,0,Math.PI*2);ctx.fillStyle=metal;ctx.fill();ctx.lineWidth=2.2;ctx.strokeStyle=ink;ctx.stroke();}
function drawSpoon(ctx,G,u,L,m){const r=sampleRows(G.spoon.rows,u);if(!r)return;const [bx,by,a]=r;
 ctx.save();spoonShape(ctx,bx,by,a,G.spoon.L,null);ctx.restore();
 if(L){ctx.save();underSurface(ctx,L);ctx.clip();spoonShape(ctx,bx,by,a,G.spoon.L,{col:L.body,m});ctx.restore();}}

// --- orange peel: tube along a hand-traced centreline of the frame-830 rest shape ---
// traced on peel_rest_x3.png (crop origin 354,365, ×3); loops cross like a cursive "ll"
const PEEL=[[105,158],[150,205],[210,240],[265,238],[300,220],[330,190],[345,150],[335,112],[315,98],[293,112],[283,150],[290,200],[312,228],[350,248],[420,250],[458,228],[490,195],[518,152],[512,118],[490,108],[466,122],[458,160],[466,210],[490,236],[530,258],[565,268],[600,272]].map(([x,y])=>[354+x/2.8455,365+y/2.8455]);
function drawPeel(ctx,G,u){const r=sampleRows(G.peel.rows,u);if(!r)return;const [x,y,a,sx,sy]=r,[cx,cy]=G.peel.centroid;
 ctx.save();ctx.translate(x,y);ctx.rotate(a*Math.PI/180);ctx.scale(sx,sy);ctx.translate(-cx,-cy);
 const path=new Path2D();path.moveTo(...PEEL[0]);for(let i=1;i<PEEL.length-1;i++){const [x0,y0]=PEEL[i],[x1,y1]=PEEL[i+1];path.quadraticCurveTo(x0,y0,(x0+x1)/2,(y0+y1)/2);}path.lineTo(...PEEL.at(-1));
 ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#422818';ctx.lineWidth=16;ctx.stroke(path);ctx.strokeStyle='#fbb754';ctx.lineWidth=11;ctx.stroke(path);   // tube ≈14px incl. outline (full-res compare at frame 830)
 ctx.fillStyle='#c27c1e';PEEL.forEach(([px,py],i)=>{ctx.beginPath();ctx.arc(px+((i*7)%3-1)*2,py+((i*5)%3-1)*2,1.1,0,Math.PI*2);ctx.fill();});
 ctx.restore();}

function dots(ctx,list,ring){for(const [x,y,r,kind,h] of list){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);if(kind==='gin-bubble-ring'){ctx.strokeStyle=h;ctx.lineWidth=1.6;ctx.stroke();}else{ctx.fillStyle=h;ctx.fill();}}}
function drawRays(ctx,G,f){for(const ray of G.rays){const fr=ray.frames.find(r=>r[0]===f)||(f>ray.frames.at(-1)[0]?ray.frames.at(-1):null);if(!fr)continue;
 const satMax=Math.max(...ray.frames.map(r=>r[6]));ctx.save();ctx.globalAlpha=clamp(fr[6]/(satMax*0.85));ctx.strokeStyle=ray.hex;ctx.lineCap='round';ctx.lineWidth=ray.hex==='#eba231'?6.5:5.5;ctx.beginPath();ctx.moveTo(fr[1],fr[2]);ctx.lineTo(fr[3],fr[4]);ctx.stroke();ctx.restore();}}

export function glassScaleAt(G,u){const r=sampleRows(G.glassScale,u);return r?r[0]:1;}
// state: ice poses for this time (used by intro impact marks and sound)
export function drawWorld(ctx,t,G,intro){
 const u=t*30,f=Math.floor(u+1e-6);if(f<85)return {ice:{}};
 const s=glassScaleAt(G,u),[px,py]=G.glassPivot,L=liquidAt(G,u),stir=f>=G.stir[0]&&f<=G.stir[1],m=stir?G.iceMixStir:G.iceMix;
 ctx.save();ctx.translate(px,py);ctx.scale(s,s);ctx.translate(-px,-py);
 glassBack(ctx,G,u);if(L){drawLiquid(ctx,L);if(stir)ripples(ctx,L,u);}
 ctx.restore();
 const ice={},intoFront=f<180;
 if(!intoFront)drawCubes();
 // gin bubble rings come from the glass measurement; Campari/vermouth drops are drawn with the stream (bottles.js)
 const bub=(G.bubbles[String(f)]||[]).filter(b=>b[3]==='gin-bubble-ring');dots(ctx,bub);
 ctx.save();ctx.translate(px,py);ctx.scale(s,s);ctx.translate(-px,-py);glassLines(ctx,G,u);highlights(ctx,G,u);ctx.restore();
 drawSpoon(ctx,G,u,L,m);   // the spoon passes in front of the rim and the title
 if(intoFront)drawCubes();
 drawRays(ctx,G,f);drawPeel(ctx,G,u);// spritz radii above ~4px are merged clusters in the detector; the reference shows small mist dots
 dots(ctx,(G.peel.spritz[String(f)]||[]).map(([x,y,r,h])=>[x,y,Math.min(r,4)*0.75,'drop',h]));
 return {ice,liquid:L,stir};
 function drawCubes(){const off=intro.iceArtOffset;for(const [id,rows] of Object.entries(G.ice)){const r=sampleRows(rows,u);if(!r)continue;const [x,y,a]=r,sc=intro.ice.find(i=>i.id===id).scale*s;ice[id]={x,y,rotation:a};drawIce(ctx,x+off[0],y+off[1],a,sc,L,m,stir);}}
}
