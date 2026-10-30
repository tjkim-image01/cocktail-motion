// Local cubic-Bezier feature morphs. Body frames are never warped.
const mix=(a,b,t)=>a+(b-a)*t,clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
export class FaceRig {
  constructor(data,iris,atlas,repair,mouthOpen,mouthClosed){this.data=data;this.iris=iris;this.atlas=atlas;this.repair=repair;this.mouthOpen=mouthOpen;this.mouthClosed=mouthClosed;this.state={enabled:true,mouth:0,width:1,round:0,eyeL:1,eyeR:1,gaze:0,blinkAt:-1,talking:false,autoBlink:false};this.lastBlink=0;}
  static async load(base='face/'){const url=new URL(base.endsWith('/')?base:base+'/',document.baseURI);const d=await fetch(new URL('rig.json',url)).then(r=>r.json());const files=['face/iris-0.png','face/iris-1.png','face/eyes-atlas.png','face/eye-repair-atlas.png','face/mouth-open.png','face/mouth-closed.png'];const ims=await Promise.all(files.map(src=>new Promise((yes,no)=>{const im=new Image();im.onload=()=>yes(im);im.onerror=no;im.src=new URL(src.replace('face/',''),url).href})));return new FaceRig(d,ims.slice(0,2),ims[2],ims[3],ims[4],ims[5]);}
  blink(now=performance.now()){this.state.blinkAt=now;}
  blinkValue(now){const t=(now-this.state.blinkAt)/340;if(this.state.blinkAt<0||t>1)return 0;return t<.32?Math.sin(t/.32*Math.PI/2):Math.cos((t-.32)/.68*Math.PI/2);}
  render(ctx,i,now,viseme=null){if(!this.state.enabled)return;const f=this.data.frames[i],s=this.state;
    if(s.autoBlink&&now-this.lastBlink>3800){this.blink(now);this.lastBlink=now;}
    const blink=this.blinkValue(now);f.eyes.forEach((e,k)=>this.eye(ctx,e,k,clamp((k?s.eyeR:s.eyeL)*(1-blink))));
    this.mouth(ctx,f.mouth,viseme||{open:s.mouth,width:s.width,round:s.round});
  }
  skin(ctx,e,eye=false){ctx.save();ctx.translate(e.x,e.y);ctx.rotate(e.angle||0);ctx.fillStyle=`rgb(${e.skin.join(' ')})`;
    if(eye){ctx.beginPath();ctx.moveTo(-51,-9);ctx.bezierCurveTo(-52,-31,-28,-52,5,-48);ctx.bezierCurveTo(30,-45,43,-16,46,9);ctx.bezierCurveTo(39,28,4,34,-23,26);ctx.bezierCurveTo(-44,22,-49,9,-51,-9);ctx.fill();}
    else{const w=Math.max(e.w,72)+12,h=Math.max(e.h,4)+15;ctx.beginPath();ctx.roundRect(-w/2,-h/2,w,h,8);ctx.fill();}ctx.restore();
  }
  eye(ctx,e,k,op){
    if(e.originalOpen&&op>.999&&Math.abs(this.state.gaze)<.001)return;
    const [ax,ay,w,h]=e.atlas,[ox,oy]=e.origin,[cx,cy]=e.spriteCenter;
    ctx.drawImage(this.repair,ax,ay,w,h,ox,oy,w,h);
    ctx.save();ctx.translate(e.x+this.state.gaze*3,e.y);
    if(op<.065){ctx.rotate(e.angle);ctx.beginPath();ctx.moveTo(-38,10);ctx.bezierCurveTo(-17,19,17,19,38,10);ctx.strokeStyle='#20191b';ctx.lineWidth=4.5;ctx.lineCap='round';ctx.stroke();for(const [x,sgn] of [[-36,-1],[36,1]]){ctx.beginPath();ctx.moveTo(x,11);ctx.lineTo(x+sgn*9,5);ctx.lineWidth=2.5;ctx.stroke();}ctx.restore();return;}
    const b=1-op,lash=-27,bottom=22;
    const warp=y=>y<lash?lash+(y-lash)*(1-.35*b)+(bottom-lash)*b:bottom+(y-bottom)*op;
    // The silhouette consists of 64 corresponding points fitted as cubic Bezier segments.
    const points=e.outline.map(([x,y])=>[x,warp(y)]);const path=new Path2D();
    if(op>.025){
      path.moveTo(points[0][0],points[0][1]);
      for(let j=0;j<points.length;j++){const n=points.length,p0=points[(j-1+n)%n],p1=points[j],p2=points[(j+1)%n],p3=points[(j+2)%n];path.bezierCurveTo(p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6,p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6,p2[0],p2[1]);}path.closePath();ctx.clip(path);
    }
    for(let y=0;y<h;y++){const y0=warp(y-cy),y1=warp(y+1-cy);if(y1-y0<.04)continue;ctx.drawImage(this.atlas,ax,ay+y,w,1,-cx,y0,w,Math.max(.05,y1-y0)+.15);}
    ctx.restore();
  }
  mouth(ctx,e,v){
    this.skin(ctx,e);ctx.save();ctx.translate(e.x,e.y);ctx.rotate(e.angle);
    const ref=this.data.mouthReference.open,closed=this.data.mouthReference.closed;
    const open=clamp(v.open),round=clamp(v.round||0),wide=(v.width||1)*mix(1,.57,round);
    const sx=e.w/ref.rawWidth*wide,sy=(1+round*.18)*open,base=e.h>15?ref.baseline:0;
    if(open<.045){ctx.scale(e.w/closed.rawWidth,1);ctx.drawImage(this.mouthClosed,-64,base-48);ctx.restore();return;}
    const warp=y=>base+(y-ref.baseline)*sy;
    // Same 64 source contour correspondences fitted to cubic Bezier segments for every viseme.
    const points=ref.outline.map(([x,y])=>[x*sx,warp(y)]),p=new Path2D();p.moveTo(...points[0]);
    for(let j=0;j<points.length;j++){const n=points.length,a=points[(j-1+n)%n],b=points[j],c=points[(j+1)%n],d=points[(j+2)%n];p.bezierCurveTo(b[0]+(c[0]-a[0])/6,b[1]+(c[1]-a[1])/6,c[0]-(d[0]-b[0])/6,c[1]-(d[1]-b[1])/6,c[0],c[1]);}p.closePath();
    // Interior pixels are the original artwork: original top teeth, tongue, cavity, and ink.
    ctx.save();ctx.clip(p);ctx.drawImage(this.mouthOpen,-64*sx,warp(-48),128*sx,96*sy);ctx.restore();if(open<.85){ctx.strokeStyle='#3c2826';ctx.lineWidth=Math.min(1.1,.5+open);ctx.stroke(p);}ctx.restore();
  }
}
