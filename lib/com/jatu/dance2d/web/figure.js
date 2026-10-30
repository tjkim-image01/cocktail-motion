// dance2d 런타임 ① 캐릭터: 부위로 나눈 회화풍 원화(parts.json, dance.py cut 결과)를 Three.js 메시로 올리고 포즈마다 정점을 놓는다.
// 팔·다리는 원화의 마디(어깨-팔꿈치-손목-손끝 / 골반-무릎-발목-바짓단)마다 새 자세로 옮기고, 관절 앞뒤에서만 두 마디를 섞어
// 텍스처째 부드럽게 휜다(Spine식 메시 가중치). 조각이 꺾이는 관절 인형도, 그림 전체 모핑도 아니다.
// 좌표는 원화 px(y 위쪽, 바닥 0, 가운데 0). group의 scale로 무대 단위에 맞춘다.
import * as THREE from 'three';
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x)),BLEND=.35;
const rot=(p,a,o=[0,0])=>{const c=Math.cos(a),s=Math.sin(a),x=p[0]-o[0],y=p[1]-o[1];return [o[0]+x*c-y*s,o[1]+x*s+y*c]};
const add=(a,b,k=1)=>[a[0]+b[0]*k,a[1]+b[1]*k],sub=(a,b)=>[a[0]-b[0],a[1]-b[1]],len=v=>Math.hypot(v[0],v[1]),dir=a=>[Math.cos(a),Math.sin(a)];
function curve(pts,u){
 const n=pts.length-1,i=Math.min(n-1,Math.max(0,Math.floor(u))),f=u-i;
 const p0=pts[Math.max(0,i-1)],p1=pts[i],p2=pts[i+1],p3=pts[Math.min(n,i+2)];
 const P=k=>.5*(2*p1[k]+(-p0[k]+p2[k])*f+(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*f*f+(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*f*f*f);
 const D=k=>.5*((-p0[k]+p2[k])+2*(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*f+3*(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*f*f);
 const t=[D(0),D(1)],m=len(t)||1;return {p:[P(0),P(1)],n:[-t[1]/m,t[0]/m]};
}

export async function createFigure(rig,base=''){
 const floor=rig.floor,CX=rig.centerX??rig.size[0]/2,toArt=([x,y])=>[x-CX,floor-y];
 const group=new THREE.Group(),loader=new THREE.TextureLoader(),parts={};
 const center=name=>rig.parts[name].center.map(toArt),piv=name=>toArt(rig.parts[name].pivot);
 const rest={arm:{L:center('arm.L'),R:center('arm.R')},leg:{L:center('leg.L'),R:center('leg.R')}};
 const seg=(pts,i)=>len(sub(pts[i+1],pts[i])),angle=(pts,i)=>{const d=sub(pts[i+1],pts[i]);return Math.atan2(d[1],d[0])};
 const L={upper:seg(rest.arm.L,1),fore:seg(rest.arm.L,2),hand:seg(rest.arm.L,3),thigh:seg(rest.leg.L,1),shin:seg(rest.leg.L,2),foot:seg(rest.leg.L,3)};
 const hipY=rest.leg.L[1][1],hipX=(rest.leg.R[1][0]-rest.leg.L[1][0])/2,ankleY=rest.leg.L[3][1];
 const torsoLen=(rest.arm.L[1][1]+rest.arm.R[1][1])/2-hipY,height=floor-rig.parts.head.box[1];
 const NECK=piv('head'),WAIST=piv('torso'),HIP=piv('pelvis');

 await Promise.all(rig.order.map(async(name,order)=>{
  const info=rig.parts[name],tex=await loader.loadAsync(base+info.file);
  tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;
  const [x0,y0,x1,y1]=info.box,uvOf=([x,y])=>{const ix=x+CX,iy=floor-y;return [(ix-x0)/(x1-x0),1-(iy-y0)/(y1-y0)]};
  const strip=!!info.center,NA=strip?56:14,NC=strip?16:14,pos=new Float32Array((NA+1)*(NC+1)*3),uv=new Float32Array((NA+1)*(NC+1)*2),src=[];
  const pts=strip?info.center.map(toArt):null,half=name.startsWith('arm')?L.upper*.75:L.thigh*1.05;
  for(let i=0;i<=NA;i++)for(let j=0;j<=NC;j++){
   let p,meta;
   if(strip){const u=i/NA*(pts.length-1),d=(j/NC*2-1)*half,c=curve(pts,u);p=add(c.p,c.n,d);meta={u,p}}
   else{p=toArt([x0+(x1-x0)*j/NC,y0+(y1-y0)*i/NA]);meta={p}}
   const k=i*(NC+1)+j,[a,b]=uvOf(p);uv[k*2]=a;uv[k*2+1]=b;pos[k*3]=p[0];pos[k*3+1]=p[1];src.push(meta);
  }
  const index=[];for(let i=0;i<NA;i++)for(let j=0;j<NC;j++){const a=i*(NC+1)+j,b=a+1,c=a+NC+1,d=c+1;index.push(a,c,b,b,c,d)}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('uv',new THREE.BufferAttribute(uv,2));g.setIndex(index);
  const mesh=new THREE.Mesh(g,new THREE.MeshBasicMaterial({map:tex,transparent:true,depthTest:false,depthWrite:false,side:THREE.DoubleSide}));
  mesh.frustumCulled=false;group.add(mesh);parts[name]={mesh,src,pts,order};
 }));
 const setOrder=base=>{for(const p of Object.values(parts))p.mesh.renderOrder=base+p.order};

 // 포즈(dance.py choreo 형식: 몸통 길이로 정규화한 이동 + 팔다리 각도) → 정점.
 function update(p){
  const sq=p.squash??1,lean=p.lean,shift=p.shift*torsoLen*.75,vel=(p.vel??0)*torsoLen;
  const legPts={};let low=Infinity;
  for(const [tag,s] of [['L',-1],['R',1]]){
   const [at,rt,as,rs]=p.legs[tag],hip=[shift+s*hipX,hipY],knee=add(hip,dir(at),L.thigh*rt),ankle=add(knee,dir(as),L.shin*rs);
   legPts[tag]={hip,knee,ankle,as};low=Math.min(low,ankle[1]);
  }
  // 가장 낮은 발목을 바닥(+점프 높이)에 둔다.
  const rootz=ankleY+(p.air??0)*torsoLen*.6+(p.hop??0)*torsoLen-low;
  const T=q=>{const x=q[0]*(1+(1-sq)*.7),y=hipY+(q[1]-hipY)*sq;const r=rot([x,y],lean,WAIST);return [r[0]+shift,r[1]+rootz]};
  const Pv=q=>{const r=rot(q,lean*.5,HIP);return [r[0]+shift,r[1]+rootz]};
  const headA=lean*.55+p.nod,neck=T(NECK),Hd=q=>add(neck,rot(sub(q,NECK),headA));
  const set=(name,fn)=>{const part=parts[name];if(!part)return;const a=part.mesh.geometry.attributes.position;part.src.forEach((m,k)=>{const q=fn(m);a.array[k*3]=q[0];a.array[k*3+1]=q[1]});a.needsUpdate=true};
  // 마디 i의 강체 변환(길이 방향으로만 늘고 줄어듦)을 관절 앞뒤 BLEND 구간에서 이웃 마디와 섞는다.
  const bend=(name,target)=>{
   const src=parts[name].pts,n=src.length-1,X=[];
   for(let i=0;i<n;i++){const s=sub(src[i+1],src[i]),t=sub(target[i+1],target[i]);X.push({s0:src[i],t0:target[i],as:Math.atan2(s[1],s[0]),at:Math.atan2(t[1],t[0]),k:len(t)/(len(s)||1)})}
   const apply=(i,q)=>{const x=X[i],l=rot(sub(q,x.s0),-x.as);return add(x.t0,rot([l[0]*x.k,l[1]],x.at))};
   set(name,m=>{const i=Math.min(n-1,Math.floor(m.u)),f=m.u-i,a=apply(i,m.p);let j=-1,w=0;
    if(f<BLEND&&i>0){j=i-1;w=.5*(1-f/BLEND)}else if(f>1-BLEND&&i<n-1){j=i+1;w=.5*(1-(1-f)/BLEND)}
    if(j<0)return a;const x=w*2;w=.5*x*x*(3-2*x);const b=apply(j,m.p);return [a[0]+(b[0]-a[0])*w,a[1]+(b[1]-a[1])*w]});
  };
  const flare=-vel*.04,joints={};
  for(const [tag,s] of [['L',-1],['R',1]]){
   const g=legPts[tag];for(const k of ['hip','knee','ankle'])g[k]=[g[k][0],g[k][1]+rootz];
   const r=rest.leg[tag],top=Pv(r[0]),toe=add(g.ankle,dir(g.as+(angle(r,3)-angle(r,2))),L.foot);
   bend('leg.'+tag,[top,g.hip,g.knee,add(g.ankle,[flare,0]),add(toe,[flare*1.4,0])]);
   const lift=g.ankle[1]-ankleY,toeDown=-s*clamp(lift/(torsoLen*.26))*.32,pivot=r[3];
   set('shoe.'+tag,m=>add(rot(sub(m.p,pivot),toeDown),g.ankle));joints['leg.'+tag]=g;
  }
  set('pelvis',m=>Pv(m.p));
  const hem=-vel*.03;set('torso',m=>{const k=clamp((WAIST[1]-40-m.p[1])/90);return add(T(m.p),[hem*k,0])});
  // 머리 윗부분(머리카락·모자·귀)은 몸보다 늦게 따라온다.
  const hairTop=NECK[1]+(height-NECK[1])*.45,hdx=-vel*.05,hdy=(1-sq)*-torsoLen*.3;
  set('head',m=>{const k=clamp((m.p[1]-hairTop)/(height-hairTop));return add(Hd(m.p),[hdx*k,hdy*k])});
  if(parts.tail){const tp=piv('tail'),wag=(rig.parts.tail.wag??.3)*Math.sin((p.beat??0)*Math.PI*2);set('tail',m=>Pv(add(tp,rot(sub(m.p,tp),wag))))}
  for(const [tag] of [['L'],['R']]){
   // 어깨 위 첫 마디는 위팔과 함께 어깨점을 중심으로 돈다.
   const r=rest.arm[tag],[au,ru,af,rf]=p.arms[tag],S=T(r[1]),E=add(S,dir(au),L.upper*ru),W=add(E,dir(af),L.fore*rf),S0=add(S,rot(sub(r[0],r[1]),au-angle(r,1)));
   const tip=add(W,dir(af+(angle(r,3)-angle(r,2))),L.hand);
   bend('arm.'+tag,[S0,S,E,W,tip]);joints['arm.'+tag]={S,E,W,tip};
  }
  return {rootz,joints};
 }
 return {group,update,parts,rest,lengths:L,torsoLen,height,setOrder};
}
