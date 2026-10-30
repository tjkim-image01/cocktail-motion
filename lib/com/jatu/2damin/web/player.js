import {FaceRig} from './face.js';
const config=await fetch('2damin.json').then(r=>{if(!r.ok)throw new Error('2damin.json is missing');return r.json()});
const $=s=>document.querySelector(s),canvas=$('#canvas'),ctx=canvas.getContext('2d',{alpha:false});
const status=$('#status'),play=$('#play'),seek=$('#seek'),position=$('#position'),audio=$('#speech');
let m,face,speech,index=0,framePos=0,playing=false,rate=(config.baseSpeed??2),dir=(config.defaultMode==='reverse'?-1:1),mode=(config.defaultMode||'pingpong'),last=0,request=0,seeking=0;
const cache=new Map(),pending=new Map();
function load(i){if(cache.has(i))return Promise.resolve(cache.get(i));if(pending.has(i))return pending.get(i);const p=new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>{cache.set(i,im);pending.delete(i);resolve(im)};im.onerror=()=>{pending.delete(i);reject(new Error(`프레임 ${i+1} 불러오기 실패`))};im.src=m.frames[i]});pending.set(i,p);return p;}
function warm(i){for(let n=1;n<=18;n++){const j=((i+n*dir)%m.count+m.count)%m.count;load(j).catch(fail)}for(const k of cache.keys()){const d=((k-i)*dir+m.count)%m.count;if(cache.size>48&&d>22&&k!==i)cache.delete(k)}}
function setFrame(i,img){index=i;cache.set(i,img);seek.value=i;position.value=`${(i/m.fps).toFixed(2)} / ${m.duration.toFixed(2)}초 · ${i+1}/${m.count}`;canvas.dataset.frame=i;warm(i)}
function pause(){playing=false;request=0;play.textContent='재생'}
function resume(){if(dir>0&&framePos>=m.count-1)framePos=0;if(dir<0&&framePos<=0)framePos=m.count-1;playing=true;play.textContent='정지'}
function fail(e){pause();status.textContent=e.message;console.error(e)}
async function jump(i){pause();const t=++seeking;framePos=Math.max(0,Math.min(m.count-1,i));const f=Math.round(framePos);const im=await load(f);if(t===seeking)setFrame(f,im)}
function speak(){face.state.mouth=0;$('#mouth').value=0;audio.playbackRate=1;audio.currentTime=0;audio.play().then(()=>{$('#speechState').textContent=`${config.voice||'음성'} · 말하는 중`;}).catch(e=>{$('#speechState').textContent='음성 재생 버튼을 다시 눌러주세요';console.error(e)})}
function stopSpeech(){audio.pause();audio.currentTime=0;$('#speechState').textContent='대사 준비됨'}
function lip(){if(audio.paused||audio.ended||!speech?.samples?.length)return null;const t=audio.currentTime;const k=Math.min(speech.samples.length-1,Math.floor(t*speech.fps));const a=speech.samples[k];if(!a)return null;$('#syllable').textContent=a.syllable||'쉼';return a;}
function loop(now){const dt=last?Math.max(0,Math.min(.08,(now-last)/1000)):0;last=now;
  if(playing){let next=framePos+dt*m.fps*rate*dir;
    if(next>m.count-1||next<0){if(mode==='pingpong'){dir*=-1;next=next<0?-next:2*(m.count-1)-next;}else if($('#loop').checked)next=((next%m.count)+m.count)%m.count;else{next=dir>0?m.count-1:0;pause()}}
    const i=Math.max(0,Math.min(m.count-1,Math.floor(next)));if(cache.has(i)){framePos=next;if(i!==index)setFrame(i,cache.get(i))}else{if(request!==i+1){request=i+1;load(i).then(im=>{if(request===i+1){framePos=next;setFrame(i,im);request=0}}).catch(fail)}}
  }
  const im=cache.get(index);if(im){ctx.drawImage(im,0,0,canvas.width,canvas.height);const v=lip();face.render(ctx,index,now,v);if(!v)$('#syllable').textContent='수동';}
  requestAnimationFrame(loop);
}
play.onclick=()=>playing?pause():resume();$('#prev').onclick=()=>jump(index-1).catch(fail);$('#next').onclick=()=>jump(index+1).catch(fail);seek.oninput=()=>jump(Number(seek.value)).catch(fail);
// Displayed 1x is the user's preferred pace: twice the original Flow frame rate.
$('#speed').onchange=e=>rate=Number(e.target.value)*(config.baseSpeed??2);
$('#direction').onchange=e=>{mode=e.target.value;request=0;dir=mode==='reverse'?-1:1;warm(index);};
$('#blink').onclick=()=>face.blink();
$('#eyeL').oninput=e=>face.state.eyeL=Number(e.target.value);$('#eyeR').oninput=e=>face.state.eyeR=Number(e.target.value);
$('#gaze').oninput=e=>face.state.gaze=Number(e.target.value);
$('#mouth').oninput=e=>{stopSpeech();face.state.mouth=Number(e.target.value)};$('#mouthWidth').oninput=e=>face.state.width=Number(e.target.value);$('#round').oninput=e=>face.state.round=Number(e.target.value);
$('#autoBlink').onchange=e=>face.state.autoBlink=e.target.checked;
$('#faceOn').onchange=e=>face.state.enabled=e.target.checked;
$('#speak').onclick=speak;$('#stopSpeech').onclick=stopSpeech;
$('#speakMove').onclick=()=>{jump(dir<0?m.count-1:0).then(()=>{resume();speak()}).catch(fail)};
$('#faceReset').onclick=()=>{stopSpeech();Object.assign(face.state,{mouth:0,width:1,round:0,eyeL:1,eyeR:1,gaze:0,blinkAt:-1});for(const [id,v] of Object.entries({mouth:0,mouthWidth:1,round:0,eyeL:1,eyeR:1,gaze:0}))$('#'+id).value=v;};
for(const b of document.querySelectorAll('[data-viseme]'))b.onclick=()=>{stopSpeech();const v={REST:[0,1,0],A:[.9,1,0],E:[.4,1.25,0],I:[.22,1.25,0],O:[.75,.9,.8],U:[.4,.8,1]}[b.dataset.viseme];[face.state.mouth,face.state.width,face.state.round]=v;['mouth','mouthWidth','round'].forEach((id,i)=>$('#'+id).value=v[i]);};
$('#original').ontoggle=()=>{if($('#original').open)pause();else $('video').pause()};audio.onended=()=>$('#speechState').textContent='대사 끝';
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','BUTTON','VIDEO','AUDIO'].includes(document.activeElement.tagName))return;if(e.code==='Space'){e.preventDefault();play.click()}if(e.code==='KeyB')$('#blink').click();if(e.code==='ArrowLeft'){e.preventDefault();$('#prev').click()}if(e.code==='ArrowRight'){e.preventDefault();$('#next').click()}});
document.title=config.title||'2damin 에디터';$('h1').textContent=config.title||'2damin 에디터';$('.dialogue').textContent=config.dialogue||'대사를 준비해 주세요.';audio.src=config.audio||'audio/dialogue.wav';
try{[m,face,speech]=await Promise.all([fetch(config.manifest||'manifest.json').then(r=>r.json()),FaceRig.load(config.faceBase||'face/'),fetch(config.lipsync||'audio/lipsync.json').then(r=>r.ok?r.json():null)]);$('#direction').value=mode;$('#speed').value='1';canvas.width=m.width;canvas.height=m.height;seek.max=m.count-1;$('#meta').textContent=`${m.duration.toFixed(2)}초 · ${m.fps} fps · ${m.count}장 · ${m.width}×${m.height}`;await Promise.all(Array.from({length:Math.min(19,m.count)},(_,i)=>load(i)));setFrame(0,cache.get(0));document.querySelectorAll('button,input,select').forEach(el=>el.disabled=false);status.textContent='정방향·역방향·왕복 재생 / 얼굴은 독립 조절';window.anim2d={get state(){return{index,framePos,playing,dir,mode,rate,audioRate:audio.playbackRate,cache:cache.size,face:{...face.state},speechTime:audio.currentTime,speaking:!audio.paused}},jump,blink:()=>face.blink(),face,speak,stopSpeech};resume();requestAnimationFrame(loop)}catch(e){fail(e)}
