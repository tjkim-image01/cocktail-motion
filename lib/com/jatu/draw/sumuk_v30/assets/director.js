import {createCalligraphy} from './calligraphy-raster-v30.js?revision=30';
import {RasterPainting} from './raster-paint.js?revision=24';
import {VectorPainting} from './vector-paint.js?revision=17';
import {paintSignature,WRITE_END} from './calligraphy-portrait.js?revision=14';
import {LiveBrush} from './live-brush.js?revision=12';
import {smoothMotion,poseFromMotion} from './brush-motion.js?revision=12';
import {InkPaperMaterial} from './ink-paper.js?revision=6';
// Deterministic Canvas direction; no movie rendering or hidden completed underlay.
const ease=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x)},mix=(a,b,u)=>a.map((x,i)=>x+(b[i]-x)*u);
const FULL=[0,0,1000,652],PAPER='#f8f5ea',VW=1080,VH=1440,BOTTOM=1440;
const canvas=(w,h)=>Object.assign(document.createElement('canvas'),{width:w,height:h});
const fibers=canvas(128,128),fiberContext=fibers.getContext('2d'),fiberData=fiberContext.createImageData(128,128);let fiberSeed=37;
for(let i=0;i<fiberData.data.length;i+=4){fiberSeed=(1664525*fiberSeed+1013904223)>>>0;fiberData.data[i]=fiberData.data[i+1]=fiberData.data[i+2]=255;fiberData.data[i+3]=170+(fiberSeed>>>25)*.66}fiberContext.putImageData(fiberData,0,0);
function frame(box){let [l,t,r,b]=box;const original=(r-l)>990;if(!original){const cy=(t+b)/2,h=Math.max(b-t,(r-l)*4/3);t=cy-h/2;b=cy+h/2}const s=Math.min(VW/(r-l),VH/(b-t)),w=(r-l)*s,h=(b-t)*s;return {l,t,r,b,s,w,h,x:(1080-w)/2,y:(1440-h)/2}}

function halo(image,w,h){const c=canvas(w+8,h+8),x=c.getContext('2d');x.filter='blur(1.2px)';x.drawImage(image,4,4);x.filter='none';x.globalCompositeOperation='destination-out';x.drawImage(image,4,4);x.globalCompositeOperation='destination-in';x.fillStyle=x.createPattern(fibers,'repeat');x.fillRect(0,0,c.width,c.height);return c}
function lineMask(ctx,pts,width){if(!pts.length)return;ctx.beginPath();ctx.moveTo(...pts[0]);for(let i=1;i<pts.length;i++)ctx.lineTo(...pts[i]);ctx.strokeStyle='#fff';ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke()}
export class DrawingDirector{
 constructor(data,layers,atlases,spec){this.marks=data.strokes;this.layers=layers;this.atlases=atlases;this.spec=spec;this.surface=canvas(1000,652);this.stable=canvas(1000,652);this.sc=this.surface.getContext('2d');this.bc=this.stable.getContext('2d');this.count=0;this.vector=data.vectorPaint?new VectorPainting(this.marks,data.vectorPaint):null;this.raster=data.raster_paint?new RasterPainting(this.marks,layers,data.raster_paint):null;if(this.raster)this.surface=this.raster.surface;this.bleeds=this.raster?[]:layers.map(im=>im?halo(im,im.width,im.height):null);this.partial=canvas(1,1);this.introArt=canvas(1620,2880);this.birthArt=canvas(1080,1920);this.material=new InkPaperMaterial();this.material.canvas.width=1080;this.material.canvas.height=1920;try{this.liveBrush=new LiveBrush()}catch{this.liveBrush=null}this.paths=this.marks.map(m=>{let c=[0];for(let i=1;i<m.points.length;i++)c.push(c.at(-1)+Math.hypot(m.points[i][0]-m.points[i-1][0],m.points[i][1]-m.points[i-1][1]));return c})}
 invalidate(){this.raster?.invalidate();this.count=0;this.bc.clearRect(0,0,1000,652)}
 visible(m,s){return m.element==='sketch'?s.showGuides:m.phase==='wash'?s.showWash:s.showInk}
 stamp(ctx,index,age,s){const m=this.marks[index];if(!this.visible(m,s))return;const [l,t]=m.bounds,wet=ease(age/.9);ctx.save();ctx.globalAlpha=s.inkBleed*(m.phase==='ink'?.25:.13)*(.25+.75*wet);ctx.drawImage(this.bleeds[index],l-4,t-4);ctx.globalAlpha=1-.05*s.inkBleed*(1-wet);ctx.drawImage(this.layers[index],l,t);ctx.restore()}
 artwork(at,s,original,blend){if(this.raster)return this.raster.artwork(at,s,original,blend);if(this.vector){this.vectorOriginal=original;this.vectorBlend=blend;return this.vector.stateAt(at);}let n=this.marks.findIndex(m=>m.end>at+1e-8);if(n<0)n=this.marks.length;let dry=0;while(dry<n&&this.marks[dry].end<at-.9)dry++;if(dry<this.count)this.invalidate();while(this.count<dry){this.stamp(this.bc,this.count,1,s);this.count++}this.sc.clearRect(0,0,1000,652);this.sc.drawImage(this.stable,0,0);for(let i=dry;i<n;i++)this.stamp(this.sc,i,at-this.marks[i].end,s);let tip=null,penup=false;
  if(n<this.marks.length){const m=this.marks[n],pts=m.points,c=this.paths[n];if(at>=m.start){const u=Math.max(0,Math.min(1,(at-m.start)/(m.end-m.start))),distance=c.at(-1)*u;let k=0;while(k<c.length-2&&c[k+1]<=distance)k++;const f=(distance-c[k])/Math.max(.00001,c[k+1]-c[k]);tip=[pts[k][0]+(pts[k+1][0]-pts[k][0])*f,pts[k][1]+(pts[k+1][1]-pts[k][1])*f];if(this.visible(m,s)){const [l,t,r,b]=m.bounds;this.partial.width=r-l;this.partial.height=b-t;const pc=this.partial.getContext('2d');lineMask(pc,[...pts.slice(0,k+1),tip].map(p=>[p[0]-l,p[1]-t]),m.width+1);pc.globalCompositeOperation='source-in';pc.drawImage(this.layers[n],0,0);this.sc.save();this.sc.globalAlpha=s.inkBleed*.18;this.sc.filter=`blur(${.45+.65*u}px)`;this.sc.drawImage(this.partial,l,t);this.sc.filter='none';this.sc.globalAlpha=1;this.sc.drawImage(this.partial,l,t);this.sc.restore()}}else{penup=true;if(n){const prev=this.marks[n-1],last=prev.points.at(-1),u=ease((at-prev.end)/Math.max(.01,m.start-prev.end));tip=m.points[0].map((x,i)=>last[i]+(x-last[i])*u)}else tip=m.points[0]}}
  if(original&&blend>0){this.sc.save();this.sc.globalAlpha=blend;this.sc.drawImage(original,0,0,1000,652);this.sc.restore()}return {tip,penup,index:n}}
 camera(at){const shots=this.spec.shots;let i=shots.findIndex(s=>at<s.end);if(i<0)return FULL;const shot=shots[i];if(i===0)return shot.box;return mix(shots[i-1].box,shot.box,ease((at-shot.start)/.8))}
 brush(ctx,kind,time,x,y,s,pose){
  if(this.liveBrush){const intro=this.paintingIntro,scale=s.brushSize,image=this.liveBrush.render(intro?'calligraphy':kind,pose);ctx.drawImage(image,x-240*scale,y-312*scale,480*scale,384*scale);return}
  // GPU fallback retains direction/speed-linked angles and a fixed tip anchor.
  const spec=this.spec.brush_types[kind],angle=Math.round((pose.roll+1.2)/2.4*95),scale=s.brushSize;
  ctx.save();ctx.translate(x,y);ctx.rotate(pose.roll+.28);ctx.drawImage(this.atlases[kind],(angle%12)*spec.width,Math.floor(angle/12)*spec.height,spec.width,spec.height,-spec.anchor[0]*scale,-spec.anchor[1]*scale,spec.width*scale,spec.height*scale);ctx.restore();
 }

 kind(m,s){if(s.brushType!=='auto')return s.brushType;if(!m)return 'large';if(m.brush_kind)return m.brush_kind;if(m.width<5)return 'fine';if(m.phase==='ink')return 'medium';return m.element.endsWith('_face')?'medium':(m.bounds[2]-m.bounds[0])*(m.bounds[3]-m.bounds[1])>18000?'large':'flat'}
 stage(ctx,box,tip,penup,at,time,s,source=this.surface,alpha=1,kind=null){
  const intro=source!==this.surface,height=intro?1920:1440;
  const f=intro?(()=>{const[l,t,r,b]=box,k=Math.min(1080/(r-l),1920/(b-t)),w=(r-l)*k,h=(b-t)*k;return{l,t,r,b,s:k,w,h,x:(1080-w)/2,y:(1920-h)/2}})():frame(box);
  ctx.save();ctx.beginPath();ctx.rect(0,0,1080,height);ctx.clip();ctx.globalAlpha=alpha;ctx.translate(540+s.panX,height/2+s.panY);ctx.scale(s.zoom,s.zoom);ctx.translate(-540,-height/2);ctx.fillStyle=PAPER;ctx.fillRect(0,0,1080,height);const ratio=source.width/(intro?1080:1000);if(this.vector&&!intro){ctx.save();ctx.translate(f.x-f.l*f.s,f.y-f.t*f.s);ctx.scale(f.s,f.s);this.vector.draw(ctx,at,s,f.s*s.zoom);if(this.vectorOriginal&&this.vectorBlend>0){ctx.save();ctx.globalAlpha*=this.vectorBlend;ctx.drawImage(this.vectorOriginal,0,0,1000,652);ctx.restore();}ctx.restore();}else ctx.drawImage(source,f.l*ratio,f.t*ratio,(f.r-f.l)*ratio,(f.b-f.t)*ratio,f.x,f.y,f.w,f.h);
  if(tip&&s.showBrush){const x=f.x+(tip[0]-f.l)*f.s,y=f.y+(tip[1]-f.t)*f.s-(penup?12:0),index=this.marks.findIndex(m=>m.end>at);this.paintingIntro=intro;const pose=intro?this.introPose:this.raster?poseFromMotion(this.raster.motionAt(at,49/Math.max(1,s.drawDuration-.8)*s.playbackRate)):smoothMotion(this.marks,this.paths,at,49/Math.max(1,s.drawDuration-.8)*s.playbackRate);if(penup){pose.penup=true;pose.pressure=0;}this.lastBrushPose=pose;this.brush(ctx,kind||this.kind(this.marks[index],s),time,x,y,{...s,brushSize:s.brushSize*(intro?(this.spec.intro_brush_scale||9.04):1.45)*f.s/(intro?3.6:5.14)},pose)}ctx.restore();
 }

 async prepareIntro(){this.calligraphy=await createCalligraphy();}
 intro(ctx,time,s){
  if((time<1&&this.spec.intro_brush_visible_from!==0)||!this.calligraphy)return;
  // Preserve the approved six-second player timeline and 3.5-second finish cue.
  // Only the new logo's internal stroke clock is remapped; body/audio stay fixed.
  const t=time<=3.5?.6+(this.spec.intro_brush_visible_from===0?time/3.5:(time-1)/2.5)*5.7:time<=4.15?6.3+(time-3.5)/.65:7.3+(time-4.15);
  this.calligraphy.frame(t,{camera:s.camera==='auto'?'closeup':'full',brush:s.showBrush});
  ctx.save();ctx.globalAlpha=1-ease((time-5.6)/.4);
  ctx.drawImage(this.calligraphy.canvas,0,0,1080,1920);ctx.restore();
 }
}
