const status=document.getElementById('status'),iframe=document.getElementById('player');
const params=new URLSearchParams(location.search),worker=Number(params.get('worker')||0),workers=Number(params.get('workers')||1);
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function post(job,kind,body,extra=''){
 const r=await fetch('/api/render-v30?job='+job.id+'&kind='+kind+extra,{method:'POST',body});
 if(!r.ok)throw Error(await r.text());return r.json();
}
async function audioMix(job,duration){
 const settings=job.settings,sr=48000,cover=1.5,ac=new OfflineAudioContext(2,Math.ceil(duration*sr),sr),base='../episodes/'+job.episode+'/';
 const fx=ac.createDynamicsCompressor();fx.threshold.value=-5;fx.knee.value=5;fx.ratio.value=12;fx.attack.value=.003;fx.release.value=.15;
 const quarter=ac.createGain();quarter.gain.value=.25;const shaper=ac.createWaveShaper(),curve=new Float32Array(8193);
 for(let i=0;i<curve.length;i++){const x=i*2/(curve.length-1)-1,y=x*4;curve[i]=y/Math.pow(1+Math.pow(y,4),.25);}shaper.curve=curve;shaper.oversample='4x';fx.connect(quarter).connect(shaper).connect(ac.destination);
 async function source(url,at,offset,gain,end,effect=false,fade=false){
  const r=await fetch(url);if(!r.ok)throw Error(url);const b=await ac.decodeAudioData(await r.arrayBuffer()),s=ac.createBufferSource(),g=ac.createGain();s.buffer=b;g.gain.value=gain;s.connect(g).connect(effect?fx:ac.destination);
  if(fade){g.gain.setValueAtTime(0,at);g.gain.linearRampToValueAtTime(gain,at+.28);g.gain.setValueAtTime(gain,duration-1.8);g.gain.linearRampToValueAtTime(0,duration);}
  s.start(at,offset,Math.min(end-at,b.duration-offset));
 }
 if(settings.sound){
  await source(base+(job.locale?.voice||'audio/voice-director.m4a'),cover,0,settings.volume,duration);
  if(settings.musicEnabled){const lib=await fetch('/api/series-music').then(r=>r.json()),track=lib.tracks.find(x=>x.id===settings.musicTrack);if(!track)throw Error('Music missing');await source(track.url,cover+settings.musicStart,settings.musicOffset,settings.volume*settings.musicVolume*.55,duration,false,true);}
  if(settings.effectsEnabled){await source(base+'audio/roll-v7.m4a',cover,0,settings.volume*settings.rollVolume,cover+3.5,true);await source(base+'audio/court-finish-v9.m4a',cover+3.5,0,settings.volume*settings.finishVolume,cover+5.05,true);}
 }
 const rendered=await ac.startRendering(),n=rendered.length,buf=new ArrayBuffer(44+n*4),v=new DataView(buf);
 function str(at,s){for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));}str(0,'RIFF');v.setUint32(4,36+n*4,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,2,true);v.setUint32(24,sr,true);v.setUint32(28,sr*4,true);v.setUint16(32,4,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,n*4,true);
 let peak=0,power=0;for(let i=0;i<n;i++)for(let c=0;c<2;c++){const x=rendered.getChannelData(c)[i];peak=Math.max(peak,Math.abs(x));power+=x*x;v.setInt16(44+(i*2+c)*2,Math.max(-32768,Math.min(32767,Math.round(x*32767))),true);}
 await post(job,'audio',buf);return{peak,rms:Math.sqrt(power/(n*2)),cover_silent:true};
}

async function checkArmOwnership(player){
 const painting=await fetch('../episodes/ep06/art/painting.json').then(r=>r.json()),mask=new Image();
 await new Promise((resolve,reject)=>{mask.onload=resolve;mask.onerror=reject;mask.src='../episodes/ep06/art/'+painting.raster_paint.semantic_background_target_mask;});
 const x=277*4,y=294*4,w=400*4,h=72*4,c=Object.assign(document.createElement('canvas'),{width:w,height:h}),q=c.getContext('2d',{willReadFrequently:true});
 q.drawImage(mask,x,y,w,h,0,0,w,h);const target=q.getImageData(0,0,w,h).data;let total=0;for(let i=0;i<target.length;i+=4)if(target[i]>0)total++;
 const report={target_pixels:total,stages:{}};
 for(const [stage,t]of [['figures',44.6],['background',56.5]]){
  player.frame(t);q.clearRect(0,0,w,h);q.drawImage(player.artworkCanvas,x,y,w,h,0,0,w,h);const pixels=q.getImageData(0,0,w,h).data;let visible=0;
  for(let i=0;i<pixels.length;i+=4)if(target[i]>0&&pixels[i+3]>2)visible++;
  report.stages[stage]={time:t,visible,ratio:visible/total};
  q.save();q.globalCompositeOperation='destination-over';q.fillStyle='#f8f5ea';q.fillRect(0,0,w,h);q.restore();const binary=atob(c.toDataURL('image/png').split(',')[1]),bytes=new Uint8Array(binary.length);for(let i=0;i<bytes.length;i++)bytes[i]=binary.charCodeAt(i);
  const saved=await fetch('/api/render-intro?kind='+stage,{method:'POST',body:bytes});if(!saved.ok)throw Error(await saved.text());
 }
 report.passed=report.stages.figures.visible===0&&report.stages.background.ratio>.9;
 await fetch('/api/render-intro?kind=quality',{method:'POST',body:JSON.stringify(report)});
 if(!report.passed)throw Error('Arm background ownership QA failed: '+JSON.stringify(report));
}
async function renderEpisode(jobs){
 const ep=jobs[0].episode;
 status.textContent=ep+' 불러오는 중';for(const job of jobs)await post(job,'progress',JSON.stringify({state:'loading'}));
 iframe.src='studio.html?ep='+ep+'&lang=ko&export=1&revision=30';
 let player;for(let i=0;i<1200;i++){try{player=iframe.contentWindow.sumukExport;if(player?.ready)break;}catch{}await wait(100);}if(!player?.ready)throw Error('Player load timeout');
 if(ep==='ep06'&&params.get('checkArms')==='1')await checkArmOwnership(player);
 const variants=await player.prepareVariants(jobs),duration=1.5+variants.duration,n=Math.round(duration*30);
 const covers={},audio={},offsets={};
 for(const job of jobs){const cover=new Image();await new Promise((resolve,reject)=>{cover.onload=resolve;cover.onerror=reject;cover.src='../episodes/'+ep+'/art/covers-v18/'+job.language+'.png';});covers[job.id]=cover;audio[job.id]=await audioMix(job,duration);offsets[job.id]=0;}
 const out=Object.assign(document.createElement('canvas'),{width:1080,height:1920}),ctx=out.getContext('2d',{alpha:false});
 const cfg={codec:'avc1.64002a',width:1080,height:1920,bitrate:10000000,framerate:30,latencyMode:'realtime',hardwareAcceleration:'prefer-hardware',avc:{format:'annexb'}};
 if(!(await VideoEncoder.isConfigSupported(cfg)).supported)throw Error('AVC unsupported');
 const encoders=new Map();let failure=null;
 for(const job of jobs){
  const state={job,count:0,offset:0,chunks:[],bytes:0,pending:Promise.resolve()};
  state.send=()=>{if(!state.bytes)return;const payload=new Blob(state.chunks),at=state.offset;state.offset+=state.bytes;state.chunks=[];state.bytes=0;state.pending=state.pending.then(()=>post(job,'video',payload,'&offset='+at));};
  state.encoder=new VideoEncoder({output(chunk){const bytes=new Uint8Array(chunk.byteLength);chunk.copyTo(bytes);state.chunks.push(bytes);state.bytes+=bytes.byteLength;state.count++;if(state.bytes>1000000)state.send();},error(e){failure=e.message;}});state.encoder.configure(cfg);encoders.set(job.id,state);
 }
 const started=performance.now();
 for(let i=0;i<n;i++){
  window.renderStep={i,phase:'draw'};
  if(i>=45)variants.frameBase((i-45)/30);
  for(const job of jobs){
   if(i<45)ctx.drawImage(covers[job.id],0,0,1080,1920);else ctx.drawImage(variants.frameLocale(job.id),0,0);
   const f=new VideoFrame(out,{timestamp:Math.round(i*1e6/30),duration:Math.round(1e6/30)});encoders.get(job.id).encoder.encode(f,{keyFrame:i%60===0});f.close();
  }
  window.renderStep.phase='encode';
  // Dequeue backpressure keeps the platform encoder running continuously.
  // Flushing every few frames caused repeated long stalls in the real browser.
  for(const state of encoders.values())while(state.encoder.encodeQueueSize>8)await new Promise(r=>state.encoder.addEventListener('dequeue',r,{once:true}));
  if(failure)throw Error(failure);
  if(i%60===0){
   for(const state of encoders.values())state.send();await Promise.all([...encoders.values()].map(s=>s.pending));
   const progress={state:'rendering',frame:i,total:n,elapsed:(performance.now()-started)/1000};status.textContent=ep+' '+jobs.map(j=>j.language).join('/')+' '+i+'/'+n;
   await Promise.all(jobs.map(j=>post(j,'progress',JSON.stringify(progress))));
  }
 }
 window.renderStep.phase='flush';await Promise.all([...encoders.values()].map(s=>s.encoder.flush()));
 for(const state of encoders.values()){state.send();await state.pending;state.encoder.close();if(state.count!==n)throw Error('Encoded frame count mismatch');}
 for(const job of jobs){
  const report={frames:encoders.get(job.id).count,seconds:duration,elapsed:(performance.now()-started)/1000,audio:audio[job.id],cover_seconds:1.5,body_seconds:variants.duration,capture:'WebCodecs AVC / continuous dequeue / shared artwork and original locale annotation pixels'};
  status.textContent=job.id+' 완전 디코드 검사 중';await post(job,'progress',JSON.stringify({state:'verifying',...report}));await post(job,'complete',JSON.stringify(report));
 }
 iframe.src='about:blank';return;
}
window.renderV30={state:'starting'};
try{
 const plan=await fetch('/api/render-v30').then(r=>r.json()),groups=new Map();
 for(const job of plan.jobs){
  if((params.get('episode')&&params.get('episode')!==job.episode)||(params.get('job')&&params.get('job')!==job.id)||plan.status[job.id]?.state==='complete')continue;
  if(!groups.has(job.episode))groups.set(job.episode,[]);groups.get(job.episode).push(job);
 }
 for(const [ep,jobs]of groups){window.renderV30={state:'rendering',job:ep};await renderEpisode(jobs);}
 window.renderV30={state:'complete'};status.textContent='모든 출력과 검수 완료';
}catch(e){window.renderV30={state:'error',error:e.stack};status.textContent=e.stack;console.error(e);}
