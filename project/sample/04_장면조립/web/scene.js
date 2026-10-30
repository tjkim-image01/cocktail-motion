import * as THREE from '../vendor/three.module.js';
import {createBoil} from './boil.js';
import {introTitle,iceMarks} from './intro.js';
import {drawUI} from './ui.js';
import {drawWorld,glassScaleAt} from './world.js';
import {createBottles} from './bottles.js';
const ROOT='../../';
// V4: every layer is drawn per frame from reference measurements into one 2D canvas in the
// reference's stacking order; Three.js shows it on a plane and applies the measured line boil.
export async function createScene(canvas){
 await Promise.all([document.fonts.load('80px Lilita'),document.fonts.load('150px Lucky'),document.fonts.load('29px Hand')]);
 const get=f=>fetch(ROOT+'03_모션제작/'+f).then(r=>r.json());
 const [intro,ui,glass]=await Promise.all([get('intro-motion-v3.json'),get('ui-v4.json'),get('glass-v4.json')]);
 const bottles=await createBottles(ROOT);
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
 renderer.setPixelRatio(1);renderer.setSize(1080,1080,false);renderer.outputColorSpace=THREE.SRGBColorSpace;
 const boil=createBoil(renderer);
 const scene=new THREE.Scene();scene.background=new THREE.Color('#faf9f5');
 const camera=new THREE.OrthographicCamera(0,1080,0,1080,-100,100);camera.position.z=50;
 const layer=document.createElement('canvas');layer.width=layer.height=1080;const ctx=layer.getContext('2d');
 const tx=new THREE.CanvasTexture(layer);tx.colorSpace=THREE.SRGBColorSpace;
 const geo=new THREE.PlaneGeometry(1080,1080);geo.scale(1,-1,1);
 const plane=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:tx,transparent:true,depthTest:false,depthWrite:false}));plane.position.set(540,540,0);scene.add(plane);
 function render(t){
  t=Math.min(30,Math.max(0,t));ctx.clearRect(0,0,1080,1080);
  const title=introTitle(ctx,t,intro);                 // title + subtitles
  const world=drawWorld(ctx,t,glass,intro);           // glass, liquid, ice, spoon, peel, rays
  iceMarks(ctx,t,world.ice,intro);                    // intro impact strokes ride with the cubes
  bottles.draw(ctx,t,world);                          // bottles, pour stream, splash drops
  drawUI(ctx,t,ui,glassScaleAt(glass,t*30));                                   // oz scale, card, timeline
  tx.needsUpdate=true;boil.render(scene,camera,t);
  return {time:t,title,ice:world.ice,liquid:world.liquid};
 }
 render(0);return {render,renderer};
}
