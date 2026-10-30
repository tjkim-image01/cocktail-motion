import {ReferenceBrush} from './reference-brush-v27.js?revision=29';

export async function createCalligraphy(){
const BASE=new URL('../episodes/ep02/review/tj-v27/',import.meta.url);
const canvas=Object.assign(document.createElement('canvas'),{width:940,height:1672}),ctx=canvas.getContext('2d');
const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*(3-2*x)};
let plan,image,birth,art,brush,lastView=null,loaded=false,time=0,playing=false,anchor=0,anchorTime=0,raf=0;
const loadImage=url=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error('이미지를 읽지 못했습니다.'));i.src=url;});

class BitmapInk{
 constructor(source,map){
  this.canvas=document.createElement('canvas');this.canvas.width=source.width;this.canvas.height=source.height;
  const gl=this.gl=this.canvas.getContext('webgl',{alpha:false,antialias:false,preserveDrawingBuffer:true});
  if(!gl)throw Error('이 브라우저에서 WebGL을 사용할 수 없습니다.');
  const compile=(type,code)=>{const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,'attribute vec2 p;varying vec2 uv;void main(){uv=p*.5+.5;gl_Position=vec4(p,0.,1.);}'));
  gl.attachShader(program,compile(gl.FRAGMENT_SHADER,`precision highp float;
   varying vec2 uv;uniform sampler2D approved;uniform sampler2D born;uniform sampler2D paper;uniform float clock;
   void main(){vec2 p=vec2(uv.x,1.-uv.y);vec4 b=texture2D(born,p);float birth=(floor(b.r*255.+.5)+floor(b.g*255.+.5)*256.)/1000.;
    float reveal=smoothstep(birth,birth+.035,clock);vec3 blank=texture2D(paper,p*vec2(1.8359375,26.125)).rgb;
    gl_FragColor=vec4(mix(blank,texture2D(approved,p).rgb,reveal),1.);}`));
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  const loc=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  const paper=this.paper=document.createElement('canvas');paper.width=512;paper.height=64;paper.getContext('2d').drawImage(source,0,0,source.width,85,0,0,512,64);
  for(const [unit,name,img,repeat]of[[0,'approved',source,false],[1,'born',map,false],[2,'paper',paper,true]]){
   gl.activeTexture(gl.TEXTURE0+unit);const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,name==='born'?gl.NEAREST:gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,name==='born'?gl.NEAREST:gl.LINEAR);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,repeat?gl.REPEAT:gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,repeat?gl.REPEAT:gl.CLAMP_TO_EDGE);
   gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);gl.uniform1i(gl.getUniformLocation(program,name),unit);
  }
  this.clock=gl.getUniformLocation(program,'clock');gl.viewport(0,0,this.canvas.width,this.canvas.height);
 }
 render(t){this.gl.uniform1f(this.clock,t);this.gl.drawArrays(this.gl.TRIANGLE_STRIP,0,4);return this.canvas;}
}

function sample(stroke,u){
 const ps=stroke.points;u=clamp(u);let lo=0,hi=ps.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(ps[mid].u<u)lo=mid;else hi=mid;}
 const a=ps[lo],b=ps[hi],f=clamp((u-a.u)/Math.max(.000001,b.u-a.u));
 const len=Math.max(.001,Math.hypot(b.x-a.x,b.y-a.y));
 return{x:a.x+(b.x-a.x)*f,y:a.y+(b.y-a.y)*f,width:a.width+(b.width-a.width)*f,dx:(b.x-a.x)/len,dy:(b.y-a.y)/len};
}

function poseAt(t){
 const strokes=plan.strokes;let index=strokes.findIndex(s=>t<=s.end);if(index<0)index=strokes.length-1;
 const stroke=strokes[index];
 if(t<stroke.start){
  const from=index?sample(strokes[index-1],1):{...sample(stroke,0),x:sample(stroke,0).x+90,y:sample(stroke,0).y-95};
  const to=sample(stroke,0),u=ease((t-(index?strokes[index-1].end:0))/(stroke.start-(index?strokes[index-1].end:0)));
  return{...to,x:from.x+(to.x-from.x)*u,y:from.y+(to.y-from.y)*u-28*Math.sin(Math.PI*u),pressure:0,penup:true,index};
 }
 if(t>stroke.end){const q=sample(stroke,1),u=ease((t-stroke.end)/.7);return{...q,x:q.x+60*u,y:q.y-80*u,pressure:0,penup:true,index};}
 const u=clamp((t-stroke.start)/(stroke.end-stroke.start)),q=sample(stroke,u);
 return{...q,pressure:Math.max(.015,Math.min(1,q.width/190)),penup:false,index,speed:1};
}

function brushMotionAt(t){
 const pose=poseAt(t);let dx=0,dy=0,pressure=0,weight=0;
 // Short deterministic hand inertia stabilizes the first hooked stroke.
 // Only orientation/pressure are smoothed; the contact point follows the ink.
 for(let i=0;i<5;i++){
  const q=poseAt(Math.max(0,t-i*.014)),w=5-i;
  dx+=q.dx*w;dy+=q.dy*w;pressure+=(q.penup?0:q.pressure)*w;weight+=w;
 }
 const length=Math.max(.0001,Math.hypot(dx,dy));
 return{...pose,dx:dx/length,dy:dy/length,pressure:pose.penup?0:pressure/weight};
}

function cameraAt(t,mode){
 if(mode==='full')return{zoom:1,x:0,y:0,mode:'full'};
 const followTime=Math.min(t,plan.write_end);let x=0,y=0,weight=0;
 for(let i=0;i<5;i++){const q=poseAt(Math.max(0,followTime-i*.018)),w=5-i;x+=q.x*w;y+=q.y*w;weight+=w;}
 x/=weight;y/=weight;
 const wide=ease((t-plan.write_end-.12)/.88),close=2.1;
 return{zoom:1+(close-1)*(1-wide),x:(canvas.width*.38-x*close)*(1-wide),y:(canvas.height*.66-y*close)*(1-wide),mode:wide===1?'full':'closeup'};
}

function frame(t,options={}){
 if(!loaded)return;time=Math.min(plan.duration,Math.max(0,t));ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,canvas.width,canvas.height);
 const view=lastView=cameraAt(time,options.camera??'closeup'),pose=brushMotionAt(time),alpha=1-ease((time-plan.write_end-.17)/.55);
 ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.zoom,view.zoom);
 // Extend the same blank paper outside the artwork while the close-up follows
 // the top or side edge; zoom never exposes a rectangular canvas boundary.
 ctx.fillStyle=ctx.createPattern(art.paper,'repeat');ctx.fillRect(-2500,-2500,6000,7000);ctx.drawImage(art.render(time),0,0);
 if((options.brush??true)&&alpha>0){
  ctx.save();ctx.globalAlpha=alpha;
  if(!pose.penup){ctx.fillStyle='rgba(18,16,9,.075)';ctx.beginPath();ctx.ellipse(pose.x+5,pose.y+6,8+16*pose.pressure,4+6*pose.pressure,-.4,0,Math.PI*2);ctx.fill();}
  const tool=brush.render(pose),scale=3.3;
  ctx.drawImage(tool,pose.x-brush.anchor[0]*scale,pose.y-brush.anchor[1]*scale,tool.width*scale,tool.height*scale);ctx.restore();
 }
 ctx.restore();
 return{...pose,view};
}

[plan,image,birth]=await Promise.all([fetch(new URL('plan.json',BASE)).then(r=>r.json()),loadImage(new URL('approved.png',BASE)),loadImage(new URL('birth.png',BASE))]);
art=new BitmapInk(image,birth);brush=new ReferenceBrush();loaded=true;
return {canvas,plan,frame,get view(){return lastView;}};
}
