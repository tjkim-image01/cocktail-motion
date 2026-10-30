// 플레이어 화면 조작. 리그 엔진은 headturn.js에 있다.
import { createHeadTurn, COLORS, NAMES } from './headturn.js';

const $ = (id) => document.getElementById(id);

if (location.protocol === 'file:') {
  $('loading').hidden = true;
  $('error').hidden = false;
  $('error').textContent = 'file://로는 열 수 없습니다. 이 폴더를 http 서버로 열어 주세요.';
} else {
  createHeadTurn($('stage'), {
    onFrame({ yawDeg }) {
      if (rigApi?.state.playing) $('angle').value = yawDeg.toFixed(1);
      $('angleValue').textContent = `${yawDeg >= 0 ? '+' : '−'}${Math.abs(yawDeg).toFixed(1)}°`;
      $('direction').textContent = Math.abs(yawDeg) < 3 ? '정면' : yawDeg < 0 ? '화면 왼쪽을 봄' : '화면 오른쪽을 봄';
    },
  }).then(wire).catch((err) => {
    $('loading').hidden = true;
    $('error').hidden = false;
    $('error').textContent = `불러오기 실패: ${err.message}`;
    console.error(err);
  });
}

let rigApi = null;
function wire(api) {
  rigApi = api;
  window.__headturn = api;
  $('loading').remove();
  const max = api.rig.maxAngle;
  Object.assign($('angle'), { min: -max, max });
  $('rangeLabel').textContent = `−${max}° ~ +${max}°`;
  $('layerCount').textContent = api.layers.length;
  $('vertCount').textContent = api.verts.toLocaleString();
  $('legend').innerHTML = api.layers.map((l) => `<li><i style="background:#${(COLORS[l.name] ?? 0x999999).toString(16).padStart(6, '0')}"></i>${NAMES[l.name] ?? l.name}</li>`).join('');
  const setPlaying = (on) => {
    api.setPlaying(on);
    $('play').textContent = on ? '일시정지' : '재생';
    $('play').setAttribute('aria-pressed', String(on));
  };
  $('play').onclick = () => setPlaying(!api.state.playing);
  $('speed').onchange = (e) => { api.state.speed = +e.target.value; };
  $('angle').oninput = (e) => { setPlaying(false); api.setManual(+e.target.value); };
  document.querySelectorAll('[data-pose]').forEach((b) => {
    b.onclick = () => { setPlaying(false); api.setManual(+b.dataset.pose * max); $('angle').value = +b.dataset.pose * max; };
  });
  $('depth').oninput = (e) => { api.setDepthScale(+e.target.value); $('depthValue').textContent = `${Math.round(e.target.value * 100)}%`; };
  $('physics').onchange = (e) => { api.state.physics = e.target.checked; };
  $('blink').onchange = (e) => { api.state.blinkOn = e.target.checked; };
  $('blinkNow').onclick = () => api.blinkNow();
  $('tint').onchange = (e) => { api.setTint(e.target.checked); $('legend').hidden = !e.target.checked; };
  $('mesh').onchange = (e) => api.setWire(e.target.checked);
  $('savePng').onclick = () => api.canvas.toBlob((b) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(b);
    a.download = `headturn_${$('angle').value}deg.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); setPlaying(!api.state.playing); }
  });
}
