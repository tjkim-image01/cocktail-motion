// dance2d 런타임 ② 안무: dance.py choreo가 만든 motion.json(1박 perBeat 샘플)을 곡 시간으로 읽는다.
// 플래시식 타이밍: twos 모드는 1박 6장으로 자세를 붙잡고(hold), 디딤 박자 스쿼시·구간 시작 홉을 얹는다.
export const DRAWINGS_PER_BEAT=6;
const lerp=(a,b,t)=>a+(b-a)*t,wrap=a=>((a+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;
const limb=(a,b,f)=>[a[0]+wrap(b[0]-a[0])*f,lerp(a[1],b[1],f),a[2]+wrap(b[2]-a[2])*f,lerp(a[3],b[3],f)];
function mix(a,b,f){
 return {shift:lerp(a.shift,b.shift,f),air:lerp(a.air,b.air,f),lean:lerp(a.lean,b.lean,f),nod:lerp(a.nod,b.nod,f),
  arms:{L:limb(a.arms.L,b.arms.L,f),R:limb(a.arms.R,b.arms.R,f)},legs:{L:limb(a.legs.L,b.legs.L,f),R:limb(a.legs.R,b.legs.R,f)},
  lift:{L:lerp(a.lift.L,b.lift.L,f),R:lerp(a.lift.R,b.lift.R,f)},hands:f<.5?a.hands:b.hands};
}

// options.hopEvery: n박마다 첫 박에 작은 점프(0이면 없음), options.squash: 디딤 눌림 세기.
export function createChoreo(motion,{hopEvery=0,hop=.1,squash=.03}={}){
 const P=motion.beatPeriod,per=motion.perBeat,F=motion.frames,n=F.length,first=motion.firstBeat??0;
 const beatOf=t=>(t-first)/P;
 const sample=t=>{const u=Math.max(0,Math.min(n-1.001,beatOf(t)*per)),i=Math.floor(u);return mix(F[i],F[i+1],u-i)};
 function drawingTime(t,mode='twos'){
  if(mode!=='twos')return t;
  const d=P/DRAWINGS_PER_BEAT;return first+Math.floor((t-first)/d+1e-6)*d;
 }
 function poseAt(t){
  const f=sample(t),past=sample(t-.1),beat=beatOf(t),phase=((beat%1)+1)%1;
  const h=hopEvery?Math.max(0,Math.sin(Math.PI*Math.min(1,(((beat%hopEvery)+hopEvery)%hopEvery)/.5))):0;
  return {...f,beat,vel:(f.shift-past.shift)/.1*.75,hop:hopEvery&&beat>=0?h*hop:0,
   squash:1-squash*Math.exp(-phase*9)+squash*.55*Math.exp(-((phase-.45)**2)/.02)};
 }
 return {poseAt,drawingTime,beatOf,duration:first+n/per*P,beatPeriod:P};
}
