import * as THREE from './tool-render/vendor/three.module.js';
import {createDrawingTool} from './tool-render/models.js';
// Real-time 3D bristle deformation. The paper contact is always local (0,0,0).
// Shaft rotation and tuft compression therefore cannot detach the painted tip.
export class LiveBrush {
 constructor(){
  this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});this.renderer.setSize(800,640);this.renderer.setPixelRatio(1);this.renderer.setClearColor(0,0);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
  this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-200,200,160,-160,.1,1500);this.camera.position.set(0,0,650);this.camera.lookAt(0,0,0);
  this.scene.add(new THREE.AmbientLight(0xffffff,2.1));const key=new THREE.DirectionalLight(0xfff0d8,3.2);key.position.set(-170,240,400);this.scene.add(key);const rim=new THREE.DirectionalLight(0xdde9ff,1.1);rim.position.set(250,50,150);this.scene.add(rim);
  this.tools={};for(const kind of ['fine','medium','large','flat','calligraphy'])this.tools[kind]=this.create(kind);
 }
 create(kind){
  const g=createDrawingTool(kind==='fine'?'sagunja':kind==='flat'?'western':'korean'),br=g.userData.bristles,H=kind==='fine'?46:kind==='flat'?26:42,R=kind==='fine'?6.4:kind==='flat'?12:9.5;
  if(kind==='calligraphy')g.scale.set(2.08,1.17,1.85);else if(kind==='large')g.scale.set(1.36,1.13,1.36);else if(kind==='fine')g.scale.set(.85,1.11,.85);else g.scale.y=1.17;
  g.position.set(0,-100,0);g.visible=false;this.scene.add(g);
  const positions=br.geometry.attributes.position,base=positions.array.slice(),uv=br.geometry.attributes.uv,parts=[];
  for(const child of [...g.children]){
   if(child===br)continue;
   // Replace the old rigid decorative hair tubes with deforming fibres.
   if(child.geometry?.type==='TubeGeometry'){child.visible=false;continue}
   parts.push({mesh:child,y:child.position.y});
  }
  const hairGeometry=new THREE.BufferGeometry(),hair=new Float32Array(24*6*2*3);hairGeometry.setAttribute('position',new THREE.BufferAttribute(hair,3));const strands=new THREE.LineSegments(hairGeometry,new THREE.LineBasicMaterial({color:0x625d48,transparent:true,opacity:.35}));g.add(strands);
  const contact=new THREE.Mesh(new THREE.SphereGeometry(1,20,10),new THREE.MeshStandardMaterial({color:0x1b2117,roughness:.88}));g.add(contact);
  br.material=br.material.clone();br.material.color.setHex(0x292d23);br.material.roughness=.9;
  return {g,br,H,R,base,uv,parts,strands,contact,kind};
 }
 deform(t,x,y,z,angle,p,drag){
  const v=Math.max(0,Math.min(1,y/t.H)),r=Math.hypot(x,z),spread=t.R*.82*Math.pow(p,1.12)*Math.exp(-v*5.5),radius=r*(1+.24*p*(1-v))+spread;
  const theta=r>.001?Math.atan2(x,z):angle;
  return [Math.sin(theta)*radius+drag*p*t.H*.18*Math.sin(Math.PI*v),y*(1-.23*p),Math.cos(theta)*radius*(1-.14*p)];
 }
 render(kind,pose){
  const t=this.tools[kind]||this.tools.medium,p=pose.pressure;
  if(this.current!==t){if(this.current)this.current.g.visible=false;t.g.visible=true;this.current=t}
  t.g.rotation.set(pose.pitch,pose.yaw,pose.roll);
  const a=t.br.geometry.attributes.position;
  for(let i=0;i<a.count;i++){const k=i*3,point=this.deform(t,t.base[k],t.base[k+1],t.base[k+2],(t.uv?.getX(i)||0)*Math.PI*2,p,pose.dragX);a.setXYZ(i,...point)}
  a.needsUpdate=true;t.br.geometry.computeVertexNormals();
  for(const part of t.parts)part.mesh.position.y=part.y-(part.y>=t.H-1?t.H*.23*p:0);
  const spread=Math.max(.12,t.R*.82*Math.pow(p,1.12));t.contact.scale.set(spread,.38,spread*.86);t.contact.visible=!pose.penup;
  const v=t.strands.geometry.attributes.position;let k=0;
  for(let strand=0;strand<24;strand++){const theta=strand/24*Math.PI*2;for(let j=0;j<6;j++)for(const step of [j,j+1]){
   const h=step/6*t.H,profile=Math.sin(Math.PI*.8*step/6)*.9*t.R,point=this.deform(t,Math.sin(theta)*profile,h,Math.cos(theta)*profile,theta,p,pose.dragX);v.setXYZ(k++,...point)
  }}v.needsUpdate=true;
  this.renderer.render(this.scene,this.camera);return this.renderer.domElement;
 }
}
