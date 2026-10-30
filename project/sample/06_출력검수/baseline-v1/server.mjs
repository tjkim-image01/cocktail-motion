import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createReadStream} from 'node:fs';
import {stat,mkdir,writeFile} from 'node:fs/promises';
const root=path.dirname(fileURLToPath(import.meta.url)),port=Number(process.env.PORT||4342);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.mp4':'video/mp4','.ttf':'font/ttf','.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8'};
http.createServer(async(req,res)=>{try{
 let route=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 if(route==='/'||route==='/compare.html'||route==='/index.html'){res.writeHead(302,{Location:encodeURI('/04_장면조립/web/'+(route==='/index.html'?'index.html':'compare.html'))}).end();return;}
 if(req.method==='POST'&&/^\/__capture\/\d{2}$/.test(route)){
  if(req.headers.origin!==`http://127.0.0.1:${port}`&&req.headers.origin!==`http://localhost:${port}`){res.writeHead(403).end();return;}
  const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>8e6){res.writeHead(413).end();return;}chunks.push(chunk);}const dir=path.join(root,'06_출력검수/qa/seconds');await mkdir(dir,{recursive:true});await writeFile(path.join(dir,'sec-'+route.slice(-2)+'.png'),Buffer.concat(chunks));res.writeHead(200).end('ok');return;
 }
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return;}
 const file=path.resolve(root,'.'+route);if(!file.startsWith(root+path.sep)||/(?:^|\/)\./.test(route)){res.writeHead(403).end();return;}
 const info=await stat(file);if(!info.isFile()){res.writeHead(404).end();return;}
 let start=0,end=info.size-1,status=200;const headers={'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache','Accept-Ranges':'bytes'};
 if(req.headers.range){const m=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range);if(!m){res.writeHead(416).end();return;}start=+m[1];if(m[2])end=Math.min(+m[2],end);if(start>end||start>=info.size){res.writeHead(416).end();return;}status=206;headers['Content-Range']=`bytes ${start}-${end}/${info.size}`;}
 res.writeHead(status,{...headers,'Content-Length':end-start+1});if(req.method==='HEAD')res.end();else createReadStream(file,{start,end}).pipe(res);
 }catch{res.writeHead(404).end('Not found');}
}).listen(port,'127.0.0.1',()=>console.log(`TREE002 comparison: http://127.0.0.1:${port}/`));
