import * as THREE from '../vendor/three.module.js';
import {introTitle,introIce,iceMarks} from './intro.js';
const ROOT='../../';
const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
const mix=(a,b,u)=>a+(b-a)*u;
export async function createScene(canvas){
 await Promise.all([document.fonts.load('80px Lilita'),document.fonts.load('24px Barlow'),document.fonts.load('150px Lucky'),document.fonts.load('29px Hand')]);
 const [motion,bounds,intro]=await Promise.all([fetch(ROOT+'03_모션제작/motion.json').then(r=>r.json()),fetch(ROOT+'02_아이콘제작/asset-bounds.json').then(r=>r.json()),fetch(ROOT+'03_모션제작/intro-motion-v2.json').then(r=>r.json())]);
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
 renderer.setPixelRatio(1);renderer.setSize(1080,1080,false);renderer.outputColorSpace=THREE.SRGBColorSpace;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#fbf9f4');
 const camera=new THREE.OrthographicCamera(0,1080,0,1080,-100,100);camera.position.z=50;
 function plane(texture,w,h,z){const geo=new THREE.PlaneGeometry(w,h);geo.scale(1,-1,1);const m=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide}));m.renderOrder=z;m.position.z=z;scene.add(m);return m;}
 const loader=new THREE.TextureLoader();const objects={};
 const names=['glass','ice','gin','campari','vermouth','spoon','peel','liquid-clear','liquid-red'];
 const textures={};
 await Promise.all(names.map(async name=>{
  const file=['glass','ice'].includes(name)?name+'-v2':name;
  const tx=await loader.loadAsync(ROOT+'02_아이콘제작/assets/'+file+'.png');tx.colorSpace=THREE.SRGBColorSpace;tx.minFilter=THREE.LinearMipmapLinearFilter;
  const b=bounds[file], [l,t,r,bt]=b.bounds;
  // Crop only UVs, preserving generated PNGs and their original alpha unchanged.
  tx.offset.set(l/b.width,1-bt/b.height);tx.repeat.set((r-l)/b.width,(bt-t)/b.height);textures[name]={tx,ratio:(r-l)/(bt-t)};
 }));
 for(const [name,track] of Object.entries(motion.tracks)){
  const asset=name.startsWith('ice')?'ice':name;
  let height=asset==='glass'?365:asset==='ice'?82:['gin','campari','vermouth'].includes(asset)?270:asset==='spoon'?340:asset==='peel'?53:210;
  const {tx,ratio}=textures[asset];let width=height*ratio;
  if(['gin','campari','vermouth'].includes(asset))width=90;
  if(asset==='glass')width=286;if(asset==='peel')width=172;
  if(asset.startsWith('liquid'))width=245;
  const order=asset==='glass'?6:asset.startsWith('liquid')?2:asset==='spoon'?3:asset==='ice'?4:7;
  const mesh=plane(tx,width,height,order);mesh.material.alphaTest=0.28;
  if(asset==='glass'){
   const geo=new THREE.PlaneGeometry(width,height,1,32);geo.scale(1,-1,1);const positions=geo.attributes.position;
   for(let i=0;i<positions.count;i++){const y=positions.getY(i);const weight=y<100?0:y<125?(y-100)/25:Math.max(0,(182.5-y)/57.5);positions.setY(i,y+14*weight);}positions.needsUpdate=true;mesh.geometry.dispose();mesh.geometry=geo;
  }
  if(['gin','campari','vermouth'].includes(asset)){
   const cutCap={value:0};mesh.userData.cutCap=cutCap;
   const cutoff=tx.offset.y+tx.repeat.y*.925;
   mesh.material.onBeforeCompile=shader=>{shader.uniforms.cutCap=cutCap;shader.fragmentShader='uniform float cutCap;\n'+shader.fragmentShader;shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>\nif (cutCap > 0.5 && vMapUv.y > ${cutoff.toFixed(6)}) discard;`);};
  }
  if(asset==='liquid-red'){
   const liquidColor={value:new THREE.Color('#d97684')};mesh.userData.liquidColor=liquidColor;
   mesh.material.onBeforeCompile=shader=>{shader.uniforms.liquidColor=liquidColor;shader.fragmentShader='uniform vec3 liquidColor;\n'+shader.fragmentShader;shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>\nfloat liquidLum=dot(diffuseColor.rgb,vec3(0.2126,0.7152,0.0722));\ndiffuseColor.rgb=mix(vec3(0.025),liquidColor*(0.85+liquidLum*0.6),smoothstep(0.004,0.025,liquidLum));`);};
  }
  objects[name]={mesh,width,height,track,asset};
 }
 // Separate pale glass transmission behind the imagegen rim, liquid and ice.
 const tintCanvas=document.createElement('canvas');tintCanvas.width=1080;tintCanvas.height=1080;
 const tc=tintCanvas.getContext('2d');tc.fillStyle='#dceff2';tc.beginPath();tc.moveTo(212,455);tc.bezierCurveTo(278,477,421,477,488,455);tc.lineTo(466,770);tc.quadraticCurveTo(350,806,234,770);tc.closePath();tc.fill();
 const tintTx=new THREE.CanvasTexture(tintCanvas);tintTx.colorSpace=THREE.SRGBColorSpace;const tint=plane(tintTx,1080,1080,1);tint.position.set(540,540,1);
 const hud=document.createElement('canvas');hud.width=hud.height=1080;const ctx=hud.getContext('2d');const hudTx=new THREE.CanvasTexture(hud);hudTx.colorSpace=THREE.SRGBColorSpace;const overlay=plane(hudTx,1080,1080,20);overlay.position.set(540,540,20);
 const ink='#302d31',red='#dc727b',muted='#9a9690';
 function text(str,x,y,size=24,color=ink,font='Barlow',align='left',outline=false){ctx.font=`${size}px ${font}`;ctx.textAlign=align;ctx.textBaseline='alphabetic';if(outline){ctx.lineJoin='round';ctx.strokeStyle=ink;ctx.lineWidth=size*0.055;ctx.strokeText(str,x,y+1.5);}ctx.fillStyle=color;ctx.fillText(str,x,y);}
 function line(x1,y1,x2,y2,color=ink,width=2){ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.lineWidth=width;ctx.strokeStyle=color;ctx.lineCap='round';ctx.stroke();}
 function rr(x,y,w,h,r=12){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
 function sample(track,t){for(let i=0;i<track.length-1;i++){const a=track[i],b=track[i+1];if(t>=a[0]&&t<=b[0]){let u=(t-a[0])/(b[0]-a[0]);return a.slice(1).map((v,j)=>mix(v,b[j+1],u));}}return track.at(-1).slice(1);}
 function stepAt(t){if(t<3.4)return -1;const i=motion.steps.findIndex(s=>t<s.end);return i<0?6:i;}
 function render(t){
  t=clamp(t,0,30);ctx.clearRect(0,0,1080,1080);const state={};
  for(const [name,obj] of Object.entries(objects)){
   let [x,y,rotation,opacity]=sample(obj.track,t);let sx=1,sy=1,extra={};
   if(name.startsWith('ice')){
    const descriptor=intro.ice.find(i=>i.id===name);
    if(t<=6){extra=introIce(t,descriptor);({x,y,rotation,opacity}=extra);sx=extra.scaleX;sy=extra.scaleY;}
    else {const later=sample(objects[name==='ice2'?'ice3':name==='ice3'?'ice2':name].track,t);const settled=introIce(6,descriptor),u=clamp((t-6)/.3);[x,y,rotation,opacity]=later.map((v,i)=>mix([settled.x,settled.y,settled.rotation,1][i],v,u));}
   }
   state[name]={x,y,rotation,opacity,...extra};obj.mesh.scale.set(sx,sy,1);
   obj.mesh.position.set(x,y,obj.mesh.renderOrder);obj.mesh.rotation.z=rotation*Math.PI/180;obj.mesh.visible=opacity>0.001;obj.mesh.material.opacity=opacity;
   if(name.startsWith('ice')){const redMix=clamp((t-11.8)/1.4);obj.mesh.material.color.set('#ffffff').lerp(new THREE.Color('#efb0ba'),redMix*.7);obj.mesh.material.opacity=opacity*(t<11.8?1:.79);}
   if(obj.mesh.userData.cutCap){const st=motion.steps[['gin','campari','vermouth'].indexOf(name)+1];obj.mesh.userData.cutCap.value=t>=st.pour[0]&&t<=st.pour[1]?1:0;}
   if(name==='liquid-red'){obj.mesh.material.color.set('#ffffff');obj.mesh.userData.liquidColor.value.set('#df8791').lerp(new THREE.Color('#b54d59'),clamp((t-16.5)/4));}
   if(name.startsWith('liquid')){
    // y is measured waterline. Grow volume from the glass base, maintaining its bottom contact.
    const bottom=755;const h=Math.max(2,bottom-y);const w=mix(226,257,clamp((bottom-y)/200));obj.mesh.scale.set(w/obj.width,h/obj.height,1);obj.mesh.position.y=y+h/2;
   }
  }
  tint.visible=t>=3.25;tint.material.opacity=clamp((t-3.25)/.3)*.7;
  const titleState=introTitle(ctx,t,intro);
  iceMarks(ctx,t,state,intro);
  const step=stepAt(t);
  if(step>=0){
   // Marked levels use the same source positions throughout.
   const level=state['liquid-red'].opacity>.1?state['liquid-red'].y:state['liquid-clear'].y;
   for(let i=1;i<=3;i++){const yy=749-i*62;const active=level<=yy+3;ctx.globalAlpha=t>6?1:0;line(489,yy,514,yy+1,active?'#ae4f64':'#dbd8d0',active?3:2);text(i+' oz',522,yy+6,22,active?'#a94c60':'#cecac3');}ctx.globalAlpha=1;
   const s=motion.steps[Math.min(step,5)];const landed=intro.ice.filter(i=>t>=i.settle).length;let p=step===6?1:clamp((t-s.start)/(s.end-s.start));if(s.pour)p=clamp((t-s.pour[0])/(s.pour[1]-s.pour[0]));if(step===0)p=landed/3;
   ctx.save();const settle=clamp((t-s.start)/.25);ctx.translate(0,(1-settle)*13);
   ctx.fillStyle='#edc6c8';rr(658,525,386,240,14);ctx.fill();ctx.fillStyle='#fffefb';rr(650,518,386,240,14);ctx.fill();ctx.strokeStyle=ink;ctx.lineWidth=2.7;ctx.stroke();
   text(step===6?"THAT'S A NEGRONI":`STEP ${step+1} OF 6`,674,563,22,'#a74b5c');
   text(step===6?'CIN CIN!':s.headline,674,636,66,red,'Lilita','left',true);
   text(step===6?'1 : 1 : 1':s.label,676,680,s.label.length>12?34:41,ink,'Lilita');
   text(step===6?'gin  ·  Campari  ·  sweet vermouth':s.detail,676,710,23,'#686360');
   if(step<6){ctx.fillStyle='#faf8f2';rr(679,727,238,14,7);ctx.fill();ctx.save();ctx.clip();ctx.fillStyle=red;ctx.fillRect(679,726,238*p,17);ctx.restore();ctx.strokeStyle=ink;ctx.lineWidth=2;ctx.stroke();let val=step===0?`${landed} / 3`:step===4?`${Math.min(20,Math.floor(p*20))} s`:step===5?'twist…':`${p.toFixed(1)} / 1 oz`;text(val,930,739,19);}
   ctx.restore();
   // Six linked timeline nodes, with completed checks.
   ctx.save();ctx.globalAlpha=clamp((t-3.85)/.45);
   const labels=['ICE','GIN','CAMPARI','VERMOUTH','STIR','PEEL'];
   for(let i=0;i<6;i++){const x=150+i*156,done=i<step;if(i<5)line(x+29,927,x+127,927,i<step?red:'#d8d4cb',3);ctx.beginPath();ctx.arc(x,927,23,0,Math.PI*2);ctx.fillStyle=done?red:'#fffdf8';ctx.fill();ctx.lineWidth=i===step?3.4:2;ctx.strokeStyle=i<=step?ink:'#bbb6ad';ctx.stroke();if(done){line(x-10,928,x-3,934,'#fff9ed',3.5);line(x-3,934,x+11,918,'#fff9ed',3.5);}else text(String(i+1),x,937,28,i===step?'#aa4b60':muted,'Lilita','center');text(labels[i],x,986,26,i<step?ink:i===step?'#a94c60':muted,'Hand','center');}ctx.restore();
  }
  // Pouring stream is geometry drawn from the current bottle-mouth transform to the waterline.
  for(const [i,name] of ['gin','campari','vermouth'].entries()){
   const s=motion.steps[i+1];if(t<s.pour[0]||t>s.pour[1])continue;
   const b=state[name],a=b.rotation*Math.PI/180;const mouth={x:b.x+Math.sin(a)*113,y:b.y-Math.cos(a)*113};
   const target={x:316+Math.sin(t*2)*1.5,y:Math.min(745,state[i===0?'liquid-clear':'liquid-red'].y+10)};
   ctx.beginPath();ctx.moveTo(mouth.x,mouth.y);ctx.bezierCurveTo(mouth.x+24,mouth.y+20,target.x-15,target.y-130,target.x,target.y);ctx.lineCap='round';ctx.strokeStyle=i===0?'#70858c':i===1?'#7b2535':'#5e2633';ctx.lineWidth=i===0?6:10;ctx.stroke();ctx.strokeStyle=i===0?'#e9f4f3':i===1?'#ee6d7d':'#af4f64';ctx.lineWidth=i===0?3:5;ctx.stroke();
   for(let j=0;j<3;j++){const ph=(t*4+j*.3)%1;ctx.globalAlpha=1-ph;ctx.strokeStyle=i===0?'#8dabb2':'#ce6676';ctx.lineWidth=1.4;ctx.beginPath();ctx.ellipse(target.x+Math.sin(j*7)*12,target.y+ph*12,7+ph*14,3+ph*3,0,0,Math.PI*2);ctx.stroke();}ctx.globalAlpha=1;
  }
  if(t>21&&t<24.5){for(let i=0;i<2;i++){ctx.strokeStyle='#dca0a8';ctx.lineWidth=1.5;ctx.beginPath();ctx.ellipse(350,565+i*12,75+Math.sin(t*7+i)*8,9,0,.2,Math.PI*1.6);ctx.stroke();}}
  if(t>24.9&&t<26.2){for(let j=0;j<7;j++){let ph=(t*1.6+j*.14)%1;ctx.globalAlpha=(1-ph)*.8;ctx.fillStyle='#e5b34d';ctx.beginPath();ctx.arc(350+Math.sin(j*3.1)*45,415+ph*70,2.3,0,Math.PI*2);ctx.fill();}ctx.globalAlpha=1;}
  if(t>=26.8){const p=clamp((t-26.8)/.6);for(let i=0;i<9;i++){let a=i/9*Math.PI*2;let x=350+Math.cos(a)*185,y=615+Math.sin(a)*211;line(x,y,x+Math.cos(a)*23*p,y+Math.sin(a)*23*p,i%2?red:'#e6b94c',3*p);}}
  hudTx.needsUpdate=true;renderer.render(scene,camera);return {time:t,step,objects:state,title:titleState};
 }
 render(0);return {render,renderer,objects,motion};
}
