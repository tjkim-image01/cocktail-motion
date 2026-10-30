// V4 UI layer drawn from per-frame reference measurements (03_모션제작/ui-v4.json,
// source 01_레퍼런스/analysis-v4/ui/README.md).  Frame-held values use f = floor(t*30).
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const lerp=(a,b,u)=>a+(b-a)*u;
const INK='#2c2a29',BODY='#fdfcf9',SHADOW='#f3d3d4',HEAD='#e8737c',HEAD_LINE='#4b2a2b',HEAD_EXTRUDE='#8a4e56';
function run(runs,f){let v=runs[0][1];for(const [s,x] of runs){if(s>f)break;v=x;}return v;}
function easeOutBack(u,c1){u=clamp(u);return 1+(c1+1)*(u-1)**3+c1*(u-1)**2;}

// Font sizes chosen so measured cap heights come out (headline 49 + 3.5 extrusion = 52, label 30, small 15).
const fit={};
function fontFor(ctx,family,cap,sample='H'){const key=family+cap;if(fit[key])return fit[key];ctx.font=`100px ${family}`;const a=ctx.measureText(sample).actualBoundingBoxAscent;return fit[key]=100*cap/a;}

export function drawUI(ctx,t,ui,glassScale=1){
 const f=Math.floor(t*30+1e-6),u=t*30;
 // the oz scale grows with the glass in the finale (pivot 352.5, 617.5)
 ctx.save();ctx.translate(352.5,617.5);ctx.scale(glassScale,glassScale);ctx.translate(-352.5,-617.5);drawOz(ctx,f,ui);ctx.restore();
 drawCard(ctx,u,f,ui);
 drawTimeline(ctx,u,f,ui);
}

function cardState(u,ui){const N=ui.card.entries.filter(n=>n<=Math.floor(u+1e-6)).at(-1);if(N===undefined)return null;
 const k=u-N,F=ui.card.fit,e=easeOutBack((k-F.t0_frames)/F.D_frames,F.c1);
 return {N,k,scale:F.s0+(1-F.s0)*e,rot:F.r0_deg*(1-e),alpha:k<1?0:ui.card.alpha[Math.min(3,Math.floor(k))]};}

function drawCard(ctx,u,f,ui){
 const s=cardState(u,ui);if(!s)return;const R=ui.card.rest,[small,head,label,detail]=ui.texts[String(s.N)],final=s.N===810;
 ctx.save();ctx.translate(R.cx,R.cy);ctx.rotate((R.angle_deg+s.rot)*Math.PI/180);ctx.scale(s.scale,s.scale);
 const w=R.w-2.5,h=R.h-2.5;
 if(s.alpha>0){
  // the pink shadow is drawn fully opaque under the fading body (card reads pink at N+1)
  ctx.fillStyle=SHADOW;ctx.beginPath();ctx.roundRect(-w/2+8,-h/2+8,w,h,14);ctx.fill();
  ctx.globalAlpha=s.alpha;ctx.fillStyle=BODY;ctx.beginPath();ctx.roundRect(-w/2,-h/2,w,h,14);ctx.fill();ctx.strokeStyle=INK;ctx.lineWidth=2.5;ctx.stroke();
  // rows: screen positions measured at rest; card-local = screen - centre (rest tilt is applied by the transform)
  const X=x=>x-R.cx,Y=y=>y-R.cy;
  ctx.textBaseline='alphabetic';ctx.textAlign='left';
  ctx.fillStyle='#b5485a';ctx.font=`${fontFor(ctx,'Hand',15)}px Hand`;ctx.fillText(small,X(676),Y(559));
  ctx.fillStyle='#2a262c';ctx.font=`${fontFor(ctx,'Lucky',30)}px Lucky`;ctx.fillText(label.toUpperCase(),X(678),Y(final?687:681));
  ctx.fillStyle='#6f6b6b';ctx.font=`${fontFor(ctx,'Hand',17,'d')}px Hand`;ctx.fillText(detail,X(679),Y(final?723:711));
  if(!final){const P=ui.progress.track,fw=run(ui.progress.fillW,f),cnt=run(ui.progress.counter,f);
   ctx.fillStyle=BODY;ctx.beginPath();ctx.roundRect(X(P.x0),Y(P.y_top_outer),P.x1-P.x0,P.y_bot_outer-P.y_top_outer,8);ctx.fill();
   if(fw>0){ctx.fillStyle='#ea747f';ctx.beginPath();ctx.roundRect(X(P.fill_x0),Y(728),Math.min(fw,234),12,6);ctx.fill();}
   ctx.strokeStyle=INK;ctx.lineWidth=2;ctx.beginPath();ctx.roundRect(X(P.x0)+1,Y(P.y_top_outer)+1,P.x1-P.x0-2,P.y_bot_outer-P.y_top_outer-2,8);ctx.stroke();
   if(cnt){ctx.fillStyle='#302d2b';ctx.font=`${fontFor(ctx,'Hand',13,'1')}px Hand`;ctx.fillText(cnt,X(928),Y(741));}}
  ctx.globalAlpha=1;
 }
 drawHeadline(ctx,head,X0(R),Y0(R),final);
 ctx.restore();
}
const X0=R=>672.5-R.cx,Y0=R=>636.5-R.cy;
function drawHeadline(ctx,word,x,y,final){
 const size=fontFor(ctx,'Lucky',final?53:49);ctx.font=`${size}px Lucky`;ctx.lineJoin='round';ctx.textAlign='left';ctx.textBaseline='alphabetic';
 const text=word.toUpperCase(),bx=x+3.5,by=y-(final?0:3.5);
 // dark red extrusion down-left, then the face; both with a maroon outline
 ctx.lineWidth=4.2;ctx.strokeStyle=HEAD_LINE;ctx.strokeText(text,bx-3.5,by+3.5);ctx.fillStyle=HEAD_EXTRUDE;ctx.fillText(text,bx-3.5,by+3.5);
 ctx.strokeText(text,bx,by);ctx.fillStyle=HEAD;ctx.fillText(text,bx,by);
}

function drawTimeline(ctx,u,f,ui){
 const T=ui.timeline,[a0,a1]=T.fadeIn;if(f<a0)return;const alpha=clamp((u-a0)/(a1-a0));
 const labels=['ICE','GIN','CAMPARI','VERMOUTH','STIR','PEEL'];
 ctx.save();ctx.globalAlpha=alpha;ctx.lineCap='round';
 for(let i=0;i<5;i++){const x0=T.x[i],x1=T.x[i+1];ctx.strokeStyle='#d1d0cc';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x0+24,T.y);ctx.lineTo(x1-24,T.y);ctx.stroke();
  const D=T.done[i];if(f>=D){const front=segFront(T.segFront,u-D);ctx.strokeStyle='#e76f7c';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(x0,T.y);ctx.lineTo(x0+front,T.y);ctx.stroke();}}
 const pulse=23.64+1.41*Math.sin(2*Math.PI*u/T.pulse.P_frames+T.pulse.phase_rad);
 for(let i=0;i<6;i++){const st=run(T.state[i],f),x=T.x[i];if(st===0)continue;
  let r=lerp(22,23,alpha);if(st===2)r=pulse;if(st===3){const k=f-T.done[i];r=k<T.pop.length?T.pop[k]:23.5;}
  ctx.beginPath();ctx.arc(x,T.y,r-1.5,0,Math.PI*2);ctx.fillStyle='#fdfcf9';ctx.fill();ctx.lineWidth=3;ctx.strokeStyle=st===1?'#b4b1ad':'#2e2c2c';ctx.stroke();
  const sc=r/23.5;
  if(st===3){ctx.beginPath();ctx.arc(x,T.y,(r-1.5)*0.84,0,Math.PI*2);ctx.fillStyle='#e4757f';ctx.fill();
   const k=f-T.done[i];ctx.strokeStyle='#fff9ed';ctx.lineWidth=3.5*sc;ctx.lineJoin='round';ctx.beginPath();ctx.moveTo(x-9*sc,T.y+1*sc);ctx.lineTo(x-3*sc,T.y+7*sc);if(k>=T.checkFull)ctx.lineTo(x+10*sc,T.y-8*sc);ctx.stroke();}
  else{ctx.fillStyle=st===1?'#96908d':'#b5485a';ctx.font=`${26*sc}px Lilita`;ctx.textAlign='center';ctx.textBaseline='alphabetic';ctx.fillText(String(i+1),x,T.y+9*sc);}
  ctx.fillStyle=st===1?'#938f8c':st===2?'#ab4a5a':'#2e2926';ctx.font=`${fontFor(ctx,'Hand',17)}px Hand`;ctx.textAlign='center';ctx.fillText(labels[i],x,987);   // ×1.2 after full-res finale compare
 }
 ctx.restore();
}
function segFront(table,k){const ks=Object.keys(table).map(Number).sort((a,b)=>a-b);if(k<=0)return 0;
 if(k<ks[0])return table[ks[0]]*k/ks[0];for(let i=0;i<ks.length-1;i++)if(k<=ks[i+1])return lerp(table[ks[i]],table[ks[i+1]],(k-ks[i])/(ks[i+1]-ks[i]));return 156;}

function drawOz(ctx,f,ui){
 for(const [n,L] of Object.entries(ui.oz)){const y=L.y,xt=[486,489,492][n-1];
  if(f>=L.greyFrom&&f<=L.greyTo){const a=L.grey[f-L.greyFrom]||0;ctx.save();ctx.globalAlpha=a;ctx.strokeStyle='#66655f';ctx.fillStyle='#66655f';ctx.lineWidth=3;
   ctx.setLineDash([11,9]);ctx.beginPath();ctx.moveTo(227,y);ctx.lineTo(xt,y);ctx.stroke();ctx.setLineDash([]);
   ozLabel(ctx,xt,y,n,'#66655f',1);ctx.restore();}
  if(f>=L.redFrom){const k=f-L.redFrom,w=k<L.redW.length?L.redW[k]:L.redW.at(-1),rest=L.redW.at(-1);
   if(w<=6){if(w>0){ctx.fillStyle='#b3505f';ctx.beginPath();ctx.arc(xt+2,y,2,0,Math.PI*2);ctx.fill();}}
   else ozLabel(ctx,xt,y,n,'#b3505f',w/rest);}
 }
}
function ozLabel(ctx,x,y,n,color,sx){ctx.save();ctx.translate(x,y);ctx.scale(sx,Math.min(1.08,0.6+0.4*sx));ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;ctx.lineCap='round';
 ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(28,0);ctx.stroke();ctx.font=`${fontFor(ctx,'Hand',16,'1')}px Hand`;ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillText(`${n} oz`,34,0);ctx.restore();}
