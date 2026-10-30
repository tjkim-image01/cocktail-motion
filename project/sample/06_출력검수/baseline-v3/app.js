import {createScene} from './scene.js';
const $=id=>document.getElementById(id),canvas=$('canvas'),video=$('reference');
let time=0,playing=false,speed=1,last=performance.now(),ready=false;
const cues=[['타이틀',0],['얼음',3.6],['진',6.0],['캄파리',11.2],['베르무트',16.2],['젓기',21],['껍질',24.6],['완성',26.8]];
let scene;
function updateUI(){ $('time').textContent=`${time.toFixed(2).padStart(5,'0')} / 30.00`; $('timeline').value=time;$('play').textContent=playing?'일시정지 Ⅱ':'함께 재생 ▶';const ci=cues.findLastIndex(c=>time>=c[1]);document.querySelectorAll('#steps button').forEach((b,i)=>b.classList.toggle('active',i===ci));}
async function syncVideo(force=false){if(!video)return;if(force||Math.abs(video.currentTime-time)>.12){video.currentTime=Math.min(time,29.999);}video.playbackRate=speed;if(playing){try{await video.play();}catch(e){if(e.name==='AbortError'||!playing)return;playing=false;$('status').textContent='브라우저에서 원본 재생을 시작하지 못했습니다. 재생 버튼을 다시 눌러주세요.';}}else video.pause();}
function seek(t){time=Math.min(30,Math.max(0,t));scene.render(time);syncVideo(true);updateUI();return time;}
function pause(){playing=false;video?.pause();updateUI();}
$('play').onclick=()=>{if(!ready)return;const [from,to]=ranges[$('segment').value];if(time>=to||time<from)time=from;playing=!playing;last=performance.now();syncVideo(true);updateUI();};
$('restart').onclick=()=>seek(0);
$('prev').onclick=()=>{pause();seek(time-1/30);};$('next').onclick=()=>{pause();seek(time+1/30);};
$('prev-tenth').onclick=()=>{pause();seek(Math.round((time-.1)*1000)/1000);};$('next-tenth').onclick=()=>{pause();seek(Math.round((time+.1)*1000)/1000);};
const ranges={all:[0,30],title:[0,3.6],ice:[3.9,5.8]};
$('segment').onchange=()=>{pause();seek(ranges[$('segment').value][0]);};
$('timeline').oninput=e=>{pause();seek(+e.target.value);};
$('speed').onchange=e=>{speed=+e.target.value;syncVideo(true);};
$('png').onclick=()=>{const a=document.createElement('a');a.href=canvas.toDataURL('image/png');a.download=`tree002-${time.toFixed(2)}s.png`;a.click();};
for(const [label,t] of cues){const b=document.createElement('button');b.textContent=`${t.toFixed(1)}s · ${label}`;b.onclick=()=>{pause();seek(t);};$('steps').append(b);}
function fillFilmstrip(){
 const selection=$('inspection').value,[from,to]=selection==='title'?[0,35]:selection==='ice'?[39,56]:[0,299];
 $('filmstrip').replaceChildren();for(let i=from;i<=to;i++){const n=String(i).padStart(3,'0'),t=i/10,b=document.createElement('button');b.className='frame';b.title=t.toFixed(1)+'초로 이동';b.innerHTML=`<div class="pair"><img loading="lazy" alt="원본 ${t.toFixed(1)}초" src="../../01_레퍼런스/deciseconds/frame-${n}.jpg"><img loading="lazy" alt="제작본 ${t.toFixed(1)}초" src="../../06_출력검수/qa/deciseconds/frame-${n}.jpg?v=3"></div><span>${t.toFixed(1)}s · 원본 / 제작본</span>`;b.onclick=()=>{pause();seek(t);window.scrollTo({top:0,behavior:'smooth'});};$('filmstrip').append(b);}
}
$('inspection').onchange=fillFilmstrip;fillFilmstrip();
const assetLabels={glass:'빈 잔',ice:'얼음 한 개',gin:'진 병',campari:'캄파리 병',vermouth:'스위트 베르무트 병',spoon:'바 스푼',peel:'오렌지 껍질','liquid-clear':'투명한 진 액체','liquid-red':'붉은 칵테일 액체'};
for(const [name,label] of Object.entries(assetLabels)){const d=document.createElement('div');d.className='asset';d.innerHTML=`<img loading="lazy" alt="${label}" src="../../02_아이콘제작/assets/${['glass','ice'].includes(name)?name+'-v2':name}.png"><p>${label} · ${name}.png</p>`;$('assets').append(d);}
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','BUTTON'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click();}if(e.code==='ArrowRight'){pause();seek(time+1);}if(e.code==='ArrowLeft'){pause();seek(time-1);}});
try{
 scene=await createScene(canvas);ready=true;$('play').disabled=false;$('loading').classList.add('hidden');
 $('status').textContent=video?'원본과 제작본을 같은 시간으로 맞춰 재생합니다. 하단의 0.1초 캡처를 눌러 동작을 비교하세요.':'각 물건과 액체를 별도 이미지로 배치한 30초 Three.js 실시간 애니메이션입니다.';
 // Deterministic capture API: a seek always produces the same frame.
 window.app={exportProgress:0,async exportVideo(){pause();let failure;const chunks=[],fps=30,count=900,config={codec:'avc1.420028',width:1080,height:1080,bitrate:5500000,framerate:fps,avc:{format:'annexb'},latencyMode:'quality'};if(!(await VideoEncoder.isConfigSupported(config)).supported)throw new Error('H264 unsupported');const enc=new VideoEncoder({output(chunk){const bytes=new Uint8Array(chunk.byteLength);chunk.copyTo(bytes);chunks.push(bytes);},error(e){failure=e;}});enc.configure(config);try{for(let f=0;f<count;f++){if(failure)throw failure;scene.render(f/fps);const frame=new VideoFrame(canvas,{timestamp:Math.round(f/fps*1e6),duration:Math.round(1e6/fps)});enc.encode(frame,{keyFrame:f%60===0});frame.close();window.app.exportProgress=f/count;if(enc.encodeQueueSize>8)await new Promise(r=>enc.addEventListener('dequeue',r,{once:true}));if(f%30===0)await new Promise(r=>setTimeout(r,0));}await enc.flush();if(failure)throw failure;const blob=new Blob(chunks,{type:'video/h264'});const res=await fetch('/__export-v3',{method:'POST',body:blob});if(!res.ok)throw Error('export save '+res.status);window.app.exportProgress=1;seek(time);return {frames:count,fps,width:1080,height:1080,duration:30,bytes:blob.size};}finally{enc.close();}},async captureTenths(){pause();for(let i=0;i<300;i++){scene.render(i/10);const blob=await new Promise(r=>canvas.toBlob(r,'image/jpeg',.9));const res=await fetch('/__capture-tenth/'+String(i).padStart(3,'0'),{method:'POST',body:blob});if(!res.ok)throw Error('capture '+res.status);if(i%10===0)await new Promise(r=>setTimeout(r,0));}seek(0);fillFilmstrip();return {frames:300,interval:.1};},seek(t){pause();return seek(t);},renderAt(t){return scene.render(t);},get time(){return time;},get playing(){return playing;},scene,async captureSeconds(){pause();for(let i=0;i<30;i++){seek(i);await new Promise(r=>requestAnimationFrame(r));const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));const response=await fetch('/__capture/'+String(i).padStart(2,'0'),{method:'POST',body:blob});if(!response.ok)throw new Error('capture '+response.status);}seek(0);document.querySelectorAll('#filmstrip img:nth-child(2)').forEach(img=>{img.src=img.src.split('?')[0]+'?v='+Date.now();});return {frames:30,width:canvas.width,height:canvas.height};}};
 window.__ready=true;
 const initial=Number(new URLSearchParams(location.search).get('t')||0);seek(initial);
 function tick(now){const dt=Math.min((now-last)/1000,.12);last=now;if(playing){time+=dt*speed;const [from,to]=ranges[$('segment').value];if(time>=to){if($('loop').checked){time=from+(time-to);syncVideo(true);}else{time=to;pause();}}if(video&&!video.paused&&!video.seeking)time=video.currentTime;scene.render(time);updateUI();}requestAnimationFrame(tick);}requestAnimationFrame(tick);
}catch(error){$('loading').textContent='장면을 불러오지 못했습니다: '+error.message;$('status').textContent=error.stack;console.error(error);}
