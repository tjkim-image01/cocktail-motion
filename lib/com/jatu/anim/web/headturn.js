// headturn.js — Live2D식 부위 레이어를 각도 하나로 움직이는 Three.js 런타임.
// 입력: parts/layers.json (anim_object.py cut 결과), rig.json (깊이장·연기 설정)
// 원리: 레이어마다 5px 격자 메시, 정점 x' = x + sin(각도) × 깊이. 얼굴과 머리카락의 깊이 차이가 시차를 만든다.
// M007 세라 V8(project/m007/head_turn_v8/app.js)에서 검증한 코드를 그대로 옮겼다.
import * as THREE from './vendor/three.module.js';

export const COLORS = { hair_back: 0x4f7fd0, neck: 0x8a8a8a, face: 0x4fb878, eye_l: 0xe04848, eye_r: 0xc848c8, hair_front: 0x3aa8e8, bun: 0xe8b830 };
export const NAMES = { hair_back: '뒷머리', neck: '목', face: '얼굴', eye_l: '눈(화면 왼쪽)', eye_r: '눈(화면 오른쪽)', hair_front: '앞머리·옆머리', bun: '묶음' };

const vertexShader = /* glsl */`
attribute float depth;
attribute float lagw;
uniform float yaw, hairYaw, pitch, roll, depthScale;
uniform float blink, blinkY, lashY, blinkOn;
uniform vec2 pivot;
varying vec2 vUv;
varying vec2 vPos;
void main() {
  vec2 p = position.xy;
  if (blinkOn > 0.5) {
    // 속눈썹 띠는 그대로 내려오고(약간 납작해짐), 그 아래 눈동자만 아래 눈꺼풀 쪽으로 접힌다
    float drop = (blinkY - lashY) * blink;
    p.y = p.y < lashY ? lashY + (p.y - lashY) * (1.0 - 0.35 * blink) + drop : blinkY + (p.y - blinkY) * (1.0 - blink);
  }
  float th = mix(yaw, hairYaw, lagw);
  float d = depth * depthScale;
  p.x += sin(th) * d;
  p.y += sin(pitch) * d;
  vec2 q = p - pivot;
  float c = cos(roll), s = sin(roll);
  p = pivot + vec2(c * q.x - s * q.y, s * q.x + c * q.y);
  vUv = uv;
  vPos = p;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p.x, -p.y, 0.0, 1.0);
}`;

const fragmentShader = /* glsl */`
uniform sampler2D map;
uniform vec3 tint;
uniform float tintAmt;
uniform float clipS;
uniform vec4 clipEll;
varying vec2 vUv;
varying vec2 vPos;
void main() {
  if (clipS > 0.0) {
    vec2 q = (vPos - clipEll.xy) / clipEll.zw;
    if (dot(q, q) < clipS * clipS) discard;
  }
  vec4 c = texture2D(map, vUv);
  c.rgb = mix(c.rgb, c.rgb * tint, tintAmt);
  gl_FragColor = c;
}`;

const wireFragment = /* glsl */`
uniform vec3 tint;
void main() { gl_FragColor = vec4(tint, 0.35); }`;

// ---- 깊이장 (anim_object.py depth()와 같은 식) ----
const profile = (r) => (r >= 1 ? 0 : Math.cos(Math.PI / 2 * r));
export const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function fieldDepth(field, x, y) {
  let d = 0;
  if (field.dome) {
    const { cx, cy, rx, ry, rz } = field.dome;
    d += rz * profile(Math.hypot((x - cx) / rx, (y - cy) / ry));
  }
  for (const b of field.bumps || []) {
    d += b.amp * Math.exp(-(((x - b.x) ** 2) / (2 * b.sx * b.sx) + ((y - b.y) ** 2) / (2 * b.sy * b.sy)));
  }
  if (field.ramp) d += field.ramp.depth * smooth(field.ramp.y0, field.ramp.y1, y);
  return d;
}

function buildGeometry(L, spec, rig) {
  const step = 5;
  const sx = Math.max(2, Math.ceil(L.w / step)), sy = Math.max(2, Math.ceil(L.h / step));
  const n = (sx + 1) * (sy + 1);
  const pos = new Float32Array(n * 3), uv = new Float32Array(n * 2), depth = new Float32Array(n), lagw = new Float32Array(n);
  const field = rig.fields[spec.field];
  let k = 0;
  for (let j = 0; j <= sy; j++) for (let i = 0; i <= sx; i++, k++) {
    const x = L.x + L.w * i / sx, y = L.y + L.h * j / sy;
    pos.set([x, y, 0], k * 3);
    uv.set([i / sx, 1 - j / sy], k * 2);
    let d = fieldDepth(field, x, y);
    if (spec.tuck) d += spec.tuck.depth * smooth(0, spec.tuck.range, Math.hypot(x - spec.tuck.x, y - spec.tuck.y));
    depth[k] = d;
    lagw[k] = spec.lag ? spec.lag.amount * smooth(spec.lag.y0, spec.lag.y1, y) : 0;
  }
  const idx = [];
  for (let j = 0; j < sy; j++) for (let i = 0; i < sx; i++) {
    const a = j * (sx + 1) + i, b = a + 1, c = a + sx + 1, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setAttribute('depth', new THREE.BufferAttribute(depth, 1));
  g.setAttribute('lagw', new THREE.BufferAttribute(lagw, 1));
  g.setIndex(idx);
  return g;
}

const deg = Math.PI / 180;
const ease = (t) => t * t * t * (t * (t * 6 - 15) + 10);

function blinkCurve(s) { // 깜빡임 시작 후 경과 비율 0..1 (빠르게 감고 천천히 뜸)
  if (s < 0 || s > 1) return 0;
  return s < 0.35 ? smooth(0, 0.35, s) : 1 - smooth(0.35, 1, s);
}

/**
 * stage(요소)에 캔버스를 붙이고 리그를 불러온다.
 * opts.base: layers.json·rig.json이 있는 폴더 URL(기본 './')
 * opts.onFrame({yawDeg}): 매 프레임 호출(화면 표시 갱신용)
 * 반환: { state, layers, setPlaying, setDepthScale, setTint, setWire, blinkNow, set(각도, {nod,tilt,blink}), canvas }
 */
export async function createHeadTurn(stage, opts = {}) {
  const base = opts.base || './';
  const [meta, rig] = await Promise.all([
    fetch(`${base}parts/layers.json`).then((r) => r.json()),
    fetch(`${base}rig.json`).then((r) => r.json()),
  ]);
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0xffffff, 1);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, 1, 0, -1, -10, 10);
  const [W, H] = meta.size;
  const view = rig.view || { x0: 0, x1: W, y0: 0, y1: H };
  const pivot = rig.pivot || [W / 2, H * 0.83];
  const shared = {
    yaw: { value: 0 }, hairYaw: { value: 0 }, pitch: { value: 0 }, roll: { value: 0 },
    depthScale: { value: 1 }, blink: { value: 0 }, pivot: { value: new THREE.Vector2(pivot[0], pivot[1]) },
  };
  const loader = new THREE.TextureLoader();
  const layers = [];
  let verts = 0;
  await Promise.all(meta.layers.map(async (L, order) => {
    const spec = rig.layers[L.name];
    const tex = await loader.loadAsync(`${base}${L.file}`);
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    const geo = buildGeometry(L, spec, rig);
    verts += geo.attributes.position.count;
    const uniforms = {
      ...shared, map: { value: tex },
      tint: { value: new THREE.Color(COLORS[L.name] ?? 0x999999) }, tintAmt: { value: 0 },
      blinkY: { value: spec.blink ? spec.blink.y : 0 }, lashY: { value: spec.blink ? spec.blink.lash : 0 }, blinkOn: { value: spec.blink ? 1 : 0 },
      clipS: { value: 0 }, clipEll: { value: new THREE.Vector4(meta.head.cx, meta.head.cy, meta.head.rx, meta.head.ry) },
    };
    const mesh = new THREE.Mesh(geo, new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, transparent: true, depthTest: false, depthWrite: false }));
    mesh.renderOrder = order;
    mesh.frustumCulled = false;
    const wire = new THREE.Mesh(geo, new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader: wireFragment, wireframe: true, transparent: true, depthTest: false }));
    wire.renderOrder = 100 + order;
    wire.frustumCulled = false;
    wire.visible = false;
    scene.add(mesh, wire);
    layers[order] = { name: L.name, spec, mesh, wire, uniforms };
  }));

  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight;
    renderer.setSize(w, h, false);
    const s = Math.max((view.x1 - view.x0) / w, (view.y1 - view.y0) / h);
    const cx = (view.x0 + view.x1) / 2, cy = (view.y0 + view.y1) / 2;
    Object.assign(camera, { left: cx - w * s / 2, right: cx + w * s / 2, top: -cy + h * s / 2, bottom: -cy - h * s / 2 });
    camera.updateProjectionMatrix();
  }
  stage.appendChild(renderer.domElement);
  new ResizeObserver(resize).observe(stage);
  resize();

  // ---- 연기: 정지 → 가속·감속 회전 → 정지 → 반대로. 회전 중 숙임 호·갸웃·깜빡임, 머리카락 용수철 ----
  const state = { playing: true, t: 0, speed: 1, manual: 0, physics: true, blinkOn: true, hy: 0, hv: 0, blinkT: -1, hold: null, yawDeg: 0 };
  const m = rig.motion, max = rig.maxAngle;
  function pose(t) {
    const period = 2 * (m.hold + m.turn);
    let u = ((t % period) + period) % period;
    let dir = 1;
    if (u >= m.hold + m.turn) { u -= m.hold + m.turn; dir = -1; }
    if (u < m.hold) return { yaw: -dir * max, prog: -1, dir };
    const prog = (u - m.hold) / m.turn;
    return { yaw: -dir * max + dir * 2 * max * ease(prog), prog, dir };
  }
  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    let yawDeg, nod = 0, tilt = 0, blink = 0;
    if (state.playing) {
      state.t += dt * state.speed;
      const p = pose(state.t);
      yawDeg = p.yaw;
      if (p.prog >= 0) {
        const arc = Math.sin(Math.PI * p.prog);
        nod = m.nod * arc;
        tilt = m.tilt * arc * p.dir;
        if (state.blinkOn) blink = blinkCurve((p.prog * m.turn - m.blinkAt * m.turn) / m.blinkLength);
      }
    } else {
      yawDeg = state.manual;
      if (state.hold) ({ nod = 0, tilt = 0, blink = 0 } = state.hold);
    }
    if (state.blinkT >= 0) {
      state.blinkT += dt * state.speed;
      blink = Math.max(blink, blinkCurve(state.blinkT / m.blinkLength));
      if (state.blinkT > m.blinkLength) state.blinkT = -1;
    }
    const yaw = yawDeg * deg;
    if (state.physics) {
      const { k, c } = m.hairSpring;
      let left = dt * state.speed;
      while (left > 0) {
        const h = Math.min(left, 1 / 240);
        state.hv += (k * (yaw - state.hy) - c * state.hv) * h;
        state.hy += state.hv * h;
        left -= h;
      }
    } else { state.hy = yaw; state.hv = 0; }
    shared.yaw.value = yaw;
    shared.hairYaw.value = state.hy;
    shared.pitch.value = nod * deg;
    shared.roll.value = tilt * deg;
    shared.blink.value = blink;
    for (const l of layers) {
      if (!l.spec.clip) continue;
      // 먼 쪽으로 돌 때 머리 외곽 타원 안쪽을 지워 머리 뒤로 숨는다. clip: 1이면 +각도, -1이면 −각도에서
      const side = l.spec.clip === true ? 1 : l.spec.clip;
      const a = yaw * side;
      l.uniforms.clipS.value = a > 0 ? 0.9 + 0.1 * smooth(0, 0.15, a) : 0;
    }
    state.yawDeg = yawDeg;
    opts.onFrame?.({ yawDeg });
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    state, layers, rig, meta, verts, canvas: renderer.domElement,
    setPlaying(on) { state.playing = on; },
    setManual(yawDeg) { state.playing = false; state.manual = yawDeg; },
    setDepthScale(v) { shared.depthScale.value = v; },
    setTint(on) { for (const l of layers) l.uniforms.tintAmt.value = on ? 0.75 : 0; },
    setWire(on) { for (const l of layers) l.wire.visible = on; },
    blinkNow() { state.blinkT = 0; },
    // 검수용: 각도·숙임·깜빡임을 고정(머리카락 지연 끔)
    set(yawDeg, hold = {}) { state.playing = false; state.physics = false; state.manual = yawDeg; state.hold = hold; },
  };
}
