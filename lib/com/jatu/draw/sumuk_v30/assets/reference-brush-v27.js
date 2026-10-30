import * as THREE from './tool-render/vendor/three.module.js';

// Dedicated review brush. The production player's approved brushes stay intact.
export class ReferenceBrush{
 constructor(){
  this.size=900;this.anchor=[450,750];this.pixelsPerUnit=1.25;
  this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});
  this.renderer.setSize(this.size,this.size);this.renderer.setClearColor(0,0);this.renderer.outputColorSpace=THREE.SRGBColorSpace;
  this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-360,360,600,-120,.1,2000);this.camera.position.set(0,0,1000);this.camera.lookAt(0,0,0);
  this.scene.add(new THREE.AmbientLight(0xfff8eb,1.8));
  const key=new THREE.DirectionalLight(0xffffff,2.7);key.position.set(-220,350,500);this.scene.add(key);
  const fill=new THREE.DirectionalLight(0xe6ebff,.7);fill.position.set(280,100,180);this.scene.add(fill);
  this.group=new THREE.Group();this.scene.add(this.group);
  const woodCanvas=document.createElement('canvas');woodCanvas.width=128;woodCanvas.height=1024;
  const wc=woodCanvas.getContext('2d');wc.fillStyle='#b9953c';wc.fillRect(0,0,128,1024);
  for(let i=0;i<220;i++){const x=(i*37.789)%128;wc.strokeStyle=`rgba(${i%3?77:236},${i%3?61:209},${i%3?22:123},${.035+(i%7)*.009})`;wc.lineWidth=.3+(i%5)*.2;wc.beginPath();wc.moveTo(x,0);wc.bezierCurveTo(x+2,330,x-1,670,x+1,1024);wc.stroke();}
  const texture=new THREE.CanvasTexture(woodCanvas);texture.colorSpace=THREE.SRGBColorSpace;
  const wood=new THREE.MeshStandardMaterial({map:texture,color:0xf3d479,roughness:.49});
  const black=new THREE.MeshStandardMaterial({color:0x151914,roughness:.36});
  this.rigid=[];
  const cylinder=(rt,rb,h,y,mat)=>{const m=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,40),mat);m.position.y=y;this.group.add(m);this.rigid.push({mesh:m,y});return m;};
  // 55mm hair to 200mm bamboo shaft, matching the user's brush photograph.
  cylinder(10,10,22,111,black);cylinder(9,9.8,364,304,wood);cylinder(9.1,9.1,13,492.5,black);
  const loop=new THREE.Mesh(new THREE.TorusGeometry(5.5,1.2,10,32),black);loop.position.y=507;loop.scale.y=1.6;this.group.add(loop);this.rigid.push({mesh:loop,y:507});
  this.radius=v=>11*Math.pow(Math.sin(v*Math.PI*.53),1.45)*(1-.12*THREE.MathUtils.smoothstep(v,.88,1));
  const profile=Array.from({length:65},(_,i)=>new THREE.Vector2(this.radius(i/64),i/64*100));
  const geometry=new THREE.LatheGeometry(profile,72);this.base=geometry.attributes.position.array.slice();this.baseAngles=Array.from({length:geometry.attributes.position.count},(_,i)=>geometry.attributes.uv.getX(i)*Math.PI*2);
  const colors=new Float32Array(geometry.attributes.position.count*3);
  for(let i=0;i<geometry.attributes.position.count;i++){
   const v=geometry.attributes.position.getY(i)/100,theta=geometry.attributes.uv.getX(i)*Math.PI*2;
   const mix=THREE.MathUtils.smoothstep(v,.45,.92),grain=.025*Math.sin(theta*17+v*9);
   const c=new THREE.Color().setRGB(Math.max(.002,.004+mix*.77+grain*.22),Math.max(.002,.005+mix*.74+grain*.22),Math.max(.002,.003+mix*.63+grain*.22));c.toArray(colors,i*3);
  }
  geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));
  this.hair=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({vertexColors:true,roughness:.9}));this.group.add(this.hair);
  this.tipCap=new THREE.Mesh(new THREE.CircleGeometry(1,72),new THREE.MeshBasicMaterial({color:0x10110e,side:THREE.DoubleSide}));this.tipCap.rotation.x=Math.PI/2;this.tipCap.position.y=.02;this.group.add(this.tipCap);
  const fibres=new Float32Array(80*20*2*3),fibreColors=new Float32Array(fibres.length);this.fibreGeometry=new THREE.BufferGeometry();this.fibreGeometry.setAttribute('position',new THREE.BufferAttribute(fibres,3));
  let colorIndex=0;for(let i=0;i<80;i++)for(let j=0;j<20;j++)for(const step of[j,j+1]){const v=step/20,mix=THREE.MathUtils.smoothstep(v,.45,.92);fibreColors[colorIndex++]=.018+mix*.64;fibreColors[colorIndex++]=.018+mix*.60;fibreColors[colorIndex++]=.012+mix*.49;}
  this.fibreGeometry.setAttribute('color',new THREE.BufferAttribute(fibreColors,3));
  this.fibres=new THREE.LineSegments(this.fibreGeometry,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.3}));this.group.add(this.fibres);
 }
 bendAt(v,p,dx){
  // A cantilever rooted in the ferrule: a single curvature, zero root slope.
  // The contact stays at x=0; the handle follows the displaced root instead
  // of forcing both ends to x=0 and folding the tuft back on itself.
  return p*(9+4*dx)*(2*v-v*v);
 }
 contactAt(p){
  // Loaded long hairs flatten across the paper into a narrow ellipse, rather
  // than inflating radially into a round pad when pressed.
  const x=17*Math.pow(p,1.12);return{x,z:x*(1-.76*p)};
 }
 deform(x,y,z,p,dx,theta=0){
  const v=y/100,r=Math.hypot(x,z),angle=r>.0001?Math.atan2(x,z):theta,spread=this.contactAt(p).x*Math.pow(1-v,3),radius=r*(1+.2*p*(1-v))+spread;
  const flatten=1-.76*p*Math.pow(1-v,2);
  return [Math.sin(angle)*radius+this.bendAt(v,p,dx),y*(1-.34*p),Math.cos(angle)*radius*flatten];
 }
 render({pressure=0,dx=0,dy=1,penup=false,speed=0}){
  const p=penup?0:Math.max(0,Math.min(1,pressure));
  this.group.rotation.set(1.1+.04*speed-.04*p,.04*dx,-.6+.06*dx+.02*dy);
  const positions=this.hair.geometry.attributes.position;
  for(let i=0;i<positions.count;i++){const j=i*3;positions.setXYZ(i,...this.deform(this.base[j],this.base[j+1],this.base[j+2],p,dx,this.baseAngles[i]));}
  positions.needsUpdate=true;this.hair.geometry.computeVertexNormals();
  for(const part of this.rigid){part.mesh.position.y=part.y-34*p;part.mesh.position.x=this.bendAt(1,p,dx);}
  const contact=this.contactAt(p);this.tipCap.visible=p>0;this.tipCap.scale.set(contact.x,contact.z,1);
  const fibres=this.fibreGeometry.attributes.position;let k=0;
  for(let i=0;i<80;i++){const a=i/80*Math.PI*2;for(let j=0;j<20;j++)for(const step of[j,j+1]){
   const v=step/20,r=this.radius(v)*1.005;fibres.setXYZ(k++,...this.deform(Math.sin(a)*r,v*100,Math.cos(a)*r,p,dx,a));
  }}fibres.needsUpdate=true;
  this.renderer.render(this.scene,this.camera);return this.renderer.domElement;
 }
}
