import {DrawingDirector} from './director.js?revision=raster-v31';
const status=document.getElementById('status'),canvas=document.getElementById('intro'),ctx=canvas.getContext('2d',{alpha:false});
window.renderV30={state:'loading'};
async function post(kind,body,offset=0){const r=await fetch('/api/render-intro?kind='+kind+'&offset='+offset,{method:'POST',body});if(!r.ok)throw Error(await r.text());return r.json();}
try{
 const info=await fetch('../episodes/ep03/episode.json').then(r=>r.json()),director=new DrawingDirector({strokes:[]},[],{},info.player_director);await director.prepareIntro();
 const settings={showBrush:true,camera:'auto'},cfg={codec:'avc1.64002a',width:1080,height:1920,bitrate:10000000,framerate:30,latencyMode:'realtime',hardwareAcceleration:'prefer-hardware',avc:{format:'annexb'}};
 let count=0,offset=0,chunks=[],size=0,pending=Promise.resolve(),failure=null;
 const send=()=>{if(!size)return;const payload=new Blob(chunks),at=offset;offset+=size;size=0;chunks=[];pending=pending.then(()=>post('video',payload,at));};
 const encoder=new VideoEncoder({output(chunk){const bytes=new Uint8Array(chunk.byteLength);chunk.copyTo(bytes);chunks.push(bytes);size+=bytes.byteLength;count++;if(size>1000000)send();},error(e){failure=e.message;}});encoder.configure(cfg);
 const started=performance.now();window.renderV30={state:'rendering'};
 for(let i=0;i<180;i++){
  ctx.fillStyle='#f8f5ea';ctx.fillRect(0,0,1080,1920);director.intro(ctx,i/30,settings);
  if(i===0){const b=atob(canvas.toDataURL('image/png').split(',')[1]),bytes=new Uint8Array(b.length);for(let j=0;j<b.length;j++)bytes[j]=b.charCodeAt(j);await post('preview',bytes);}
  const frame=new VideoFrame(canvas,{timestamp:Math.round(i*1e6/30),duration:Math.round(1e6/30)});encoder.encode(frame,{keyFrame:i%60===0});frame.close();while(encoder.encodeQueueSize>8)await new Promise(r=>encoder.addEventListener('dequeue',r,{once:true}));if(failure)throw Error(failure);
  status.textContent='첫 프레임부터 붓 · '+i+'/180';
 }
 await encoder.flush();send();await pending;encoder.close();await post('complete',JSON.stringify({frames:count,seconds:6,first_brush:0,write_end:3.5,body_start:6,elapsed:(performance.now()-started)/1000}));
 window.renderV30={state:'complete'};status.textContent='즉시 등장 도입 완성';
}catch(e){window.renderV30={state:'error',error:e.stack};status.textContent=e.stack;}
