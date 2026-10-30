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
// Cubic interpolation through observed 0.1s positions. Impact knots retain a sharp velocity change.
function trajectory(ice,t){const k=ice.keys;if(t<=k[0][0])return k[0].slice(1);for(let i=0;i<k.length-1;i++){const a=k[i],b=k[i+1];if(t>b[0])continue;const dt=b[0]-a[0],u=(t-a[0])/dt;const impact=x=>ice.impacts.some(v=>Math.abs(v-x)<.004);return a.slice(1).map((v,j)=>{
 const col=j+1,prev=k[Math.max(0,i-1)],next=k[Math.min(k.length-1,i+2)];
 const m0=impact(a[0])?(b[col]-a[col])/dt:(b[col]-prev[col])/(b[0]-prev[0]);
 const m1=impact(b[0])?(b[col]-a[col])/dt:(next[col]-a[col])/(next[0]-a[0]);
 const h=(2*u*u*u-3*u*u+1)*v+(u*u*u-2*u*u+u)*dt*m0+(-2*u*u*u+3*u*u)*b[col]+(u*u*u-u*u)*dt*m1;
 return j===1?Math.min(h,ice.keys.at(-1)[2]+4):h;
 });}return k.at(-1).slice(1);}
export function introIce(t,ice){const [x,y,rotation]=trajectory(ice,t);let squash=0;for(const hit of ice.impacts){const age=t-hit;if(age>=0&&age<.07)squash=Math.max(squash,Math.sin(age/.07*Math.PI)*.09);}
 const before=trajectory(ice,Math.max(ice.start,t-.01)),after=trajectory(ice,Math.min(6,t+.01));
 const speed=(after[1]-before[1])/.02;const stretch=t<ice.settle?Math.min(Math.abs(speed)/14000,.07):0;
 return {x,y,rotation,opacity:t<ice.start?0:1,scaleX:1+squash-stretch/2,scaleY:1-squash+stretch,speed,impact:Math.min(...ice.impacts.map(v=>Math.abs(t-v)))};
}
export function iceMarks(ctx,t,states,data){
 for(const ice of data.ice){if(t<ice.start||t>ice.settle)continue;const s=states[ice.id];if(!s||s.opacity<=0||s.y<20)continue;
  ctx.save();ctx.strokeStyle='#738c92';ctx.lineWidth=1.7;ctx.lineCap='round';
  // Short staggered movement lines travel with each cube; no frozen trails or fades.
  if(Math.abs(s.speed)>650){for(let j=0;j<3;j++){const x=s.x+(j-1)*25,dir=s.speed>0?-1:1;ctx.beginPath();ctx.moveTo(x,s.y+dir*51);ctx.lineTo(x+(j-1)*3,s.y+dir*(67+j%2*9));ctx.stroke();}}
  for(const hit of ice.impacts){const age=t-hit;if(age<0||age>.13)continue;const p=age/.13;ctx.globalAlpha=1-p;for(let j=0;j<4;j++){const a=Math.PI*1.08+j*Math.PI*.28;ctx.beginPath();const radius=48+p*15;ctx.moveTo(s.x+Math.cos(a)*radius,s.y+Math.sin(a)*radius);ctx.lineTo(s.x+Math.cos(a)*(radius+13),s.y+Math.sin(a)*(radius+13));ctx.stroke();}}
  ctx.restore();
 }
}
