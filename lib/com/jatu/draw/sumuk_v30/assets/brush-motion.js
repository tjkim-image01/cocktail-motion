const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x)};
// Pose is derived from the path, not a wall-clock animation. Rewinding produces
// the same pressure, speed, and angle at the same point on a stroke.
export function poseFromMotion({dx=0,dy=0,speed=0,pressure=0,penup=false}){
 const length=Math.hypot(dx,dy);if(length){dx/=length;dy/=length}else{dx=0;dy=1}
 const rush=clamp(Math.log1p(Math.max(0,speed)/70)/Math.log1p(1800/70),0,1),p=penup?0:clamp(pressure,0,1);
 return {pressure:p,speed:rush,direction:[dx,dy],pitch:clamp(1.08-.53*rush-.15*p,.32,1.15),roll:clamp(-.28+.83*dx*rush+.17*dy*rush,-1.15,.85),yaw:.28*dx*rush,dragX:-dx*rush,dragY:dy*rush,penup};
}
function pointAt(m,c,d){const pts=m.points;if(c.at(-1)<.001)return pts[0];d=clamp(d,0,c.at(-1));let k=0;while(k<c.length-2&&c[k+1]<d)k++;const u=(d-c[k])/Math.max(.00001,c[k+1]-c[k]);return pts[k].map((x,i)=>x+(pts[k+1][i]-x)*u)}
export function motionAt(marks,paths,at,rate=1){
 let index=marks.findIndex(m=>m.end>at);if(index<0)index=marks.length-1;const m=marks[index],c=paths[index],length=c.at(-1),u=clamp((at-m.start)/Math.max(.001,m.end-m.start),0,1),penup=at<m.start||at>=m.end;
 const distance=length*u,window=Math.max(1,Math.min(length*.12,12)),a=pointAt(m,c,distance-window),b=pointAt(m,c,distance+window);
 const entry=smooth(u/.12),release=smooth((1-u)/.18),pressure=(m.phase==='wash'?.86:clamp(.18+m.width/26,.20,.65))*Math.sqrt(entry*release);
 return poseFromMotion({dx:b[0]-a[0],dy:b[1]-a[1],speed:length/Math.max(.02,m.end-m.start)*rate,pressure,penup});
}
export function smoothMotion(marks,paths,at,rate=1){
 const current=motionAt(marks,paths,at,rate);let pitch=0,roll=0,yaw=0,weight=0;
 // Short deterministic hand inertia rounds corners without making the brush
 // lag behind the ink tip. Pressure releases immediately during pen lifts.
 for(let i=0;i<6;i++){const w=6-i,p=motionAt(marks,paths,Math.max(0,at-i*.012),rate);pitch+=p.pitch*w;roll+=p.roll*w;yaw+=p.yaw*w;weight+=w}
 return {...current,pitch:pitch/weight,roll:roll/weight,yaw:yaw/weight};
}
