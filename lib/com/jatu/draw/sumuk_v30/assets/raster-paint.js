// Routes reveal pigment density through a soft brush mask. EP06 v22 assets
// contain one constant RGB pigment per stroke, with texture only in alpha.
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*(3-2*x)};
const canvas=(w,h)=>Object.assign(document.createElement('canvas'),{width:w,height:h});
export class RasterPainting {
 constructor(marks,layers,spec){
  this.marks=marks;this.layers=layers;this.scale=spec.pixel_scale||4;this.continuousMasks=spec.continuous_mask_paths;
  this.surface=canvas(1000*this.scale,652*this.scale);this.stable=canvas(this.surface.width,this.surface.height);
  this.sc=this.surface.getContext('2d');this.bc=this.stable.getContext('2d');this.partial=canvas(1,1);this.count=0;this.cache=new Map();
  this.paths=marks.map(m=>{const c=[0];for(let i=1;i<m.points.length;i++)c.push(c.at(-1)+Math.hypot(m.points[i][0]-m.points[i-1][0],m.points[i][1]-m.points[i-1][1]));return c;});
  this.routes=marks.map(m=>{const spans=[];let total=0,previous=null;for(const points of m.brush_paths||[m.points]){if(points.length<2)continue;if(previous){const gap=Math.hypot(points[0][0]-previous[0],points[0][1]-previous[1]);if(gap>.01){spans.push({kind:'travel',start:total,end:total+gap*.32,a:previous,b:points[0]});total+=gap*.32;}}const c=[0];for(let i=1;i<points.length;i++)c.push(c.at(-1)+Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]));spans.push({kind:'ink',start:total,end:total+c.at(-1),points,c});total+=c.at(-1);previous=points.at(-1);}return{spans,total};});
 }
 invalidate(){this.count=0;this.cache.clear();this.bc.clearRect(0,0,this.stable.width,this.stable.height);}
 visible(m,s){return m.phase==='wash'?s.showWash:s.showInk;}
 sample(index,u){
  const route=this.routes[index],distance=route.total*clamp(u),drawPaths=[];
  for(let j=0;j<route.spans.length;j++){
   const span=route.spans[j],last=j===route.spans.length-1;
   if(distance>=span.end&&!last){if(span.kind==='ink')drawPaths.push(span.points);continue;}
   const part=clamp((distance-span.start)/Math.max(.00001,span.end-span.start));
   if(span.kind==='travel')return{tip:span.a.map((v,i)=>v+(span.b[i]-v)*part),drawPaths,penup:true,direction:span.b.map((v,i)=>v-span.a[i]),part};
   const c=span.c,pts=span.points,d=c.at(-1)*part;let k=0;while(k<c.length-2&&c[k+1]<d)k++;
   const f=(d-c[k])/Math.max(.00001,c[k+1]-c[k]),tip=pts[k].map((v,i)=>v+(pts[k+1][i]-v)*f);
   drawPaths.push([...pts.slice(0,k+1),tip]);return{tip,drawPaths,penup:false,direction:pts[k+1].map((v,i)=>v-pts[k][i]),part};
  }
 }
 motionAt(at,rate){let index=this.marks.findIndex(m=>m.end>at);if(index<0)index=this.marks.length-1;const m=this.marks[index],u=clamp((at-m.start)/Math.max(.0001,m.end-m.start)),q=this.sample(index,u),penup=at<m.start||at>=m.end||q.penup,entry=ease(q.part/.1)*ease((1-q.part)/.14);return{dx:q.direction[0],dy:q.direction[1],speed:this.routes[index].total/Math.max(.02,m.end-m.start)*rate,pressure:penup?0:(m.phase==='wash'?.86:Math.max(.2,Math.min(.65,.18+m.width/26)))*Math.sqrt(entry),penup};}
 layer(index,u){
  if(u===1&&this.cache.has(index))return this.cache.get(index);
  const m=this.marks[index];
  const [l,t,r,b]=m.bounds,p=this.scale,q=this.sample(index,u);
  this.partial.width=(r-l)*p;this.partial.height=(b-t)*p;
  const pc=this.partial.getContext('2d');pc.lineCap='round';pc.lineJoin='round';pc.strokeStyle='#fff';
  pc.filter=`blur(${p*.16}px)`;
  // A continuous wet edge, with slight pressure variation rather than dot stamps.
  if(this.continuousMasks&&(this.continuousMasks==='all'||m.element==='background')){
   pc.lineWidth=(m.reveal_width||m.width)*p*.99;pc.beginPath();
   for(const pts of q.drawPaths){if(pts.length<2)continue;pc.moveTo((pts[0][0]-l)*p,(pts[0][1]-t)*p);for(let j=1;j<pts.length;j++)pc.lineTo((pts[j][0]-l)*p,(pts[j][1]-t)*p);}
   pc.stroke();
  }else for(const pts of q.drawPaths)for(let j=1;j<pts.length;j++){
   const a=pts[j-1],b=pts[j];pc.lineWidth=(m.reveal_width||m.width)*p*(.97+.03*Math.sin((j/Math.max(1,pts.length-1))*Math.PI));
   pc.beginPath();pc.moveTo((a[0]-l)*p,(a[1]-t)*p);pc.lineTo((b[0]-l)*p,(b[1]-t)*p);pc.stroke();
  }
  pc.filter='none';pc.globalCompositeOperation='source-in';pc.drawImage(this.layers[index],0,0,this.partial.width,this.partial.height);
  const result={core:this.partial,halo:null};
  if(u===1){
   result.core=canvas(this.partial.width,this.partial.height);result.core.getContext('2d').drawImage(this.partial,0,0);
   result.halo=canvas(this.partial.width,this.partial.height);const hc=result.halo.getContext('2d');hc.filter=`blur(${p*.52}px)`;hc.drawImage(result.core,0,0);
   this.cache.set(index,result);
  }
  return result;
 }
 paint(ctx,index,u,age,s){
  const m=this.marks[index];if(!this.visible(m,s)||u<=0)return;
  const [l,t]=m.bounds,p=this.scale,layer=this.layer(index,u);
  ctx.save();
  if(s.inkBleed>0){const wet=ease(Math.max(0,age+.04)/.8);ctx.globalAlpha=s.inkBleed*(m.phase==='ink'?.17:.07)*(.45+.55*wet);if(!layer.halo)ctx.filter=`blur(${p*(.16+.36*wet)}px)`;ctx.drawImage(layer.halo||layer.core,l*p,t*p);ctx.filter='none';}
  ctx.globalAlpha=1;ctx.drawImage(layer.core,l*p,t*p);ctx.restore();
 }
 artwork(at,s,original,blend){
  let index=this.marks.findIndex(m=>m.end>at+1e-8);if(index<0)index=this.marks.length;
  let dry=0;while(dry<index&&this.marks[dry].end<at-.85)dry++;
  if(dry<this.count)this.invalidate();
  while(this.count<dry){const i=this.count++;this.paint(this.bc,i,1,1,s);this.cache.delete(i);}
  // Export may crop composition to the sampled camera rectangle. Dried pigment
  // still commits to the full stable board, so camera moves and rewind match.
  this.sc.save();
  if(this.clipBox){const[l,t,r,b]=this.clipBox,p=this.scale;this.sc.beginPath();this.sc.rect(l*p,t*p,(r-l)*p,(b-t)*p);this.sc.clip();}
  this.sc.clearRect(0,0,this.surface.width,this.surface.height);this.sc.drawImage(this.stable,0,0);
  for(let i=dry;i<index;i++)this.paint(this.sc,i,1,at-this.marks[i].end,s);
  let tip=null,penup=false;
  if(index<this.marks.length){const m=this.marks[index];if(at>=m.start){const u=clamp((at-m.start)/Math.max(.0001,m.end-m.start)),q=this.sample(index,u);tip=q.tip;penup=q.penup;this.paint(this.sc,index,u,0,s);}else{penup=true;const first=m.points[0];if(index){const prev=this.marks[index-1],last=prev.points.at(-1),u=ease((at-prev.end)/Math.max(.001,m.start-prev.end));tip=last.map((v,i)=>v+(first[i]-v)*u);}else tip=first;}}
  if(original&&blend>0){this.sc.save();this.sc.globalAlpha=blend;this.sc.drawImage(original,0,0,this.surface.width,this.surface.height);this.sc.restore();}
  this.sc.restore();
  return{tip,penup,index};
 }
}
