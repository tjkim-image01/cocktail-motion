import * as THREE from '../vendor/three.module.js';
// Line boil measured on the reference (01_레퍼런스/analysis-v4/boil): a new hand-drawn
// state every 1/8 s (state = floor(t*8), from frame 0), ink displaced ~0.85px std per
// axis, decorrelated after ~14px.  amplitude/cell calibrated by re-measuring a render
// with scripts/v4/boil_field.py (state-to-state std 1.2px, 8px correlation 0.49).
export function createBoil(renderer,{amplitude=1.36,cell=17}={}){
 const target=new THREE.WebGLRenderTarget(1080,1080,{samples:4});target.texture.colorSpace=THREE.SRGBColorSpace;
 const material=new THREE.ShaderMaterial({
  uniforms:{map:{value:target.texture},seed:{value:0},amp:{value:amplitude/1080},cell:{value:cell}},
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
  fragmentShader:`uniform sampler2D map;uniform float seed,amp,cell;varying vec2 vUv;
   float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7))+seed*17.31)*43758.5453)*2.-1.;}
   float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+1.),f.x),f.y);}
   void main(){vec2 p=vUv*1080./cell;vec2 d=vec2(n(p),n(p+vec2(41.7,19.3)));gl_FragColor=texture2D(map,vUv+d*amp);
    #include <colorspace_fragment>
   }`});
 const quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),material);const post=new THREE.Scene();post.add(quad);const cam=new THREE.Camera();
 return {render(scene,camera,t){material.uniforms.seed.value=Math.floor(t*8+1e-6);renderer.setRenderTarget(target);renderer.render(scene,camera);renderer.setRenderTarget(null);renderer.render(post,cam);}};
}
