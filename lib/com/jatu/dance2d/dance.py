"""dance2d — 회화풍 원화 한 장을 '실제 안무 영상'대로 춤추게 만드는 2D 파이프라인.

M004 v5-test8·test9·complete-1에서 검증한 방식을 재사용할 수 있게 묶었다.
방법 설명은 project/m004/README-dance2d.md, 브라우저 런타임은 같은 폴더의 web/를 본다.

    1) extract   안무 영상 → 프레임별 관절(MediaPipe) + 원곡 템포/첫 박
    2) choreo    여러 구간을 골라 이어 붙이고, 목표 곡의 박자에 1박씩 맞춘 춤 데이터(motion.json)
    3) autorig   새 캐릭터 원화에서 부위 경계·관절 중심선 초안(rig spec) 자동 추정 + 검수 그림
    4) cut       rig spec대로 원화를 부위 PNG로 자르고 parts.json 작성

춤 데이터는 캐릭터 크기와 무관하게 '각도 + 몸통 길이 비율'로 저장한다. 그래서 같은 안무를
봉식이·춘자·강아지처럼 체형이 다른 원화에 그대로 줄 수 있다.

실행(저장소 루트에서):
    python -m lib.com.jatu.dance2d.dance extract dance.mp4 --crop 400 880 -o pose-raw.json
    python -m lib.com.jatu.dance2d.dance choreo pose-raw.json --score score.json --beats 145 -o motion.json
    python -m lib.com.jatu.dance2d.dance autorig art.png -o rig-spec.json
    python -m lib.com.jatu.dance2d.dance cut rig-spec.json -o assets/name
MediaPipe가 필요한 명령은 /Users/jatu/.venvs/pose/bin/python 으로 실행한다(Python 3.12, mediapipe, opencv, numpy).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task'
MODEL = Path.home() / '.cache/dance2d/pose_landmarker_full.task'
# MediaPipe 관절 번호: 어깨 11/12, 팔꿈치 13/14, 손목 15/16, 골반 23/24, 무릎 25/26, 발목 27/28
SIDE = {'a': (11, 13, 15, 23, 25, 27), 'b': (12, 14, 16, 24, 26, 28)}


def _model() -> str:
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    return str(MODEL)


def _landmarker(video: bool):
    import mediapipe as mp
    v = mp.tasks.vision
    mode = v.RunningMode.VIDEO if video else v.RunningMode.IMAGE
    return mp, v.PoseLandmarker.create_from_options(v.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=_model()), running_mode=mode, num_poses=1,
        min_pose_detection_confidence=.5, min_tracking_confidence=.5))


# ───────────────────────────── 1) extract ─────────────────────────────
def beats_from_audio(path: str) -> tuple[float, float]:
    """onset 자기상관으로 (박 간격 초, 첫 박 초)를 추정한다. 90~180 BPM 범위."""
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '22050', '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    hop, win = 256, 1024
    rate = 22050 / hop
    spec = np.abs(np.fft.rfft(np.lib.stride_tricks.sliding_window_view(a, win)[::hop] * np.hanning(win), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spec * 20), axis=0)).sum(1)
    flux = (flux - flux.mean()) / flux.std()
    ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * rate / np.maximum(lags, 1)
    ok = (bpm > 90) & (bpm < 180)
    period = lags[ok][np.argmax(ac[ok])] / rate
    phases = np.linspace(0, period, 200, endpoint=False)
    score = [flux[np.clip((np.arange(p, len(flux) / rate, period) * rate).astype(int), 0, len(flux) - 1)].sum() for p in phases]
    return float(period), float(phases[int(np.argmax(score))])


def extract(video: str, crop: tuple[int, int] | None = None, step: float = 1 / 30) -> dict:
    """영상에서 한 명의 관절 33개를 step 간격으로 뽑는다. crop=(x0,x1)로 여러 명 중 한 명만 남긴다."""
    import cv2
    mp, det = _landmarker(True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    x0, x1 = crop or (0, W)
    frames, nxt, i = [], 0.0, 0
    with det:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            t = i / fps
            i += 1
            if t + 1e-6 < nxt:
                continue
            nxt += step
            part = np.ascontiguousarray(img[:, x0:x1, ::-1])
            r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=part), int(t * 1000))
            h, w = part.shape[:2]
            lm = [[round(p.x * w + x0, 2), round(p.y * h, 2), round(p.visibility, 3)] for p in r.pose_landmarks[0]] if r.pose_landmarks else None
            frames.append({'t': round(t, 4), 'lm': lm})
    period, first = beats_from_audio(video)
    return {'source': Path(video).name, 'videoFps': fps, 'crop': [x0, x1], 'size': [W, H], 'bpm': round(60 / period, 3),
            'beatPeriod': period, 'firstBeat': first, 'detected': sum(f['lm'] is not None for f in frames), 'frames': frames}


# ───────────────────────────── 2) choreo ─────────────────────────────
def _smooth(x: np.ndarray, s: float) -> np.ndarray:
    r = int(3 * s) + 1
    w = np.exp(-np.arange(-r, r + 1) ** 2 / (2 * s * s))
    w /= w.sum()
    return np.apply_along_axis(lambda c: np.convolve(np.pad(c, r, mode='edge'), w, 'valid'), 0, x)


class Source:
    """평활·결측 보간한 관절 시계열. y는 위쪽, 몸통 길이로 정규화한 값을 계산해 준다."""

    def __init__(self, raw: dict, sigma: float = 1.2):
        self.raw = raw
        self.t = np.array([f['t'] for f in raw['frames']])
        L = np.full((len(self.t), 33, 3), np.nan)
        for i, f in enumerate(raw['frames']):
            if f['lm']:
                L[i] = f['lm']
        L[..., 1] *= -1
        for j in range(33):
            for k in range(2):
                v = L[:, j, k]
                bad = np.isnan(v) | (np.nan_to_num(L[:, j, 2]) < .35)
                if (~bad).sum() > 2:
                    L[:, j, k] = np.interp(self.t, self.t[~bad], v[~bad])
        L[..., :2] = _smooth(L[..., :2], sigma)
        self.L = L
        P = self.P
        self.torso = _smooth(np.linalg.norm((P(11) + P(12)) / 2 - (P(23) + P(24)) / 2, axis=1), 15)
        self.valid = np.array([f['lm'] is not None for f in raw['frames']], float)
        self.front = np.linalg.norm(P(11) - P(12), axis=1) / self.torso
        self.energy = sum(np.linalg.norm(np.gradient(P(j), axis=0), axis=1) for j in (15, 16, 27, 28)) / self.torso
        # 화면 왼쪽 팔다리를 L로 쓴다(거울모드 영상도 그대로 맞는다).
        a_left = P(11)[:, 0].mean() < P(12)[:, 0].mean()
        self.side = {'L': SIDE['a'] if a_left else SIDE['b'], 'R': SIDE['b'] if a_left else SIDE['a']}

    def P(self, j: int) -> np.ndarray:
        return self.L[:, j, :2]

    def at(self, j: int, ts: np.ndarray) -> np.ndarray:
        return np.stack([np.interp(ts, self.t, self.L[:, j, k]) for k in range(2)], 1)

    def beat_time(self, b: float) -> float:
        return self.raw['firstBeat'] + b * self.raw['beatPeriod']

    def rate(self, b0: int, beats: int) -> float:
        s = self.beat_time(b0)
        m = (self.t >= s) & (self.t < s + beats * self.raw['beatPeriod'])
        if not m.any() or self.valid[m].mean() < .97 or self.front[m].min() < .45:
            return 0.0
        return float(self.energy[m].mean())

    def best_windows(self, count: int, beats: int, start_after: float = 8.0, step: int = 4) -> list[int]:
        """움직임이 많고, 정면이며, 인식이 끊기지 않은 구간 시작 박을 겹치지 않게 count개 고른다."""
        last = int((self.t[-1] - 1 - self.raw['firstBeat']) / self.raw['beatPeriod']) - beats
        cands = sorted(((self.rate(b, beats), b) for b in range(int((start_after - self.raw['firstBeat']) / self.raw['beatPeriod']), last, step)), reverse=True)
        chosen: list[int] = []
        for r, b in cands:
            if r > 0 and all(abs(b - c) >= beats for c in chosen):
                chosen.append(b)
            if len(chosen) == count:
                break
        return sorted(chosen)

    def segment(self, b0: float, beats: int, per_beat: int = 12) -> list[dict]:
        """b0박부터 beats박을 1박 per_beat 샘플의 각도 데이터로 바꾼다."""
        n = beats * per_beat
        ts = self.beat_time(b0) + np.arange(n) / per_beat * self.raw['beatPeriod']
        G = {j: self.at(j, ts) for j in range(33)}
        torso = np.interp(ts, self.t, self.torso)
        hip = (G[23] + G[24]) / 2
        sh = (G[11] + G[12]) / 2
        v = sh - hip
        lean = np.clip(np.arctan2(-v[:, 0], v[:, 1]), -.5, .5)
        ear = G[8] - G[7] if G[8][:, 0].mean() > G[7][:, 0].mean() else G[7] - G[8]
        nod = np.clip(np.arctan2(ear[:, 1], ear[:, 0]), -.45, .45) - lean * .55
        shift = np.clip((hip[:, 0] - hip[:, 0].mean()) / torso, -.75, .75)
        both = np.minimum(G[self.side['L'][5]][:, 1], G[self.side['R'][5]][:, 1])
        floor = np.array([both[max(0, i - per_beat):i + per_beat + 1].min() for i in range(n)])  # ±1박의 가장 낮은 발 = 바닥
        ang = lambda d: np.arctan2(d[:, 1], d[:, 0])
        def ratio(d, lo):
            l = np.linalg.norm(d, axis=1)
            return np.clip(l / np.percentile(l, 95), lo, 1)
        out = {k: [] for k in ('arms', 'legs', 'lift')}
        limbs = {}
        for tag in 'LR':
            s, e, w, h, k, a = self.side[tag]
            u, f, th, sn = G[e] - G[s], G[w] - G[e], G[k] - G[h], G[a] - G[k]
            limbs[tag] = dict(arm=np.stack([ang(u), ratio(u, .55), ang(f), ratio(f, .55)], 1),
                              leg=np.stack([ang(th), ratio(th, .8), ang(sn), ratio(sn, .8)], 1),
                              lift=np.maximum(0, (G[a][:, 1] - floor) / torso),
                              hand=np.where(G[w][:, 1] > G[0][:, 1], 'point', np.where(G[w][:, 1] > G[s][:, 1] + .25 * torso, 'wave', 'open')))
        air = np.clip(np.minimum(limbs['L']['lift'], limbs['R']['lift']), 0, .3)
        r4 = lambda a: [round(float(x), 4) for x in a]
        return [dict(shift=round(float(shift[i]), 4), air=round(float(air[i]), 4), lean=round(float(lean[i]), 4), nod=round(float(nod[i]), 4),
                     arms={t: r4(limbs[t]['arm'][i]) for t in 'LR'}, legs={t: r4(limbs[t]['leg'][i]) for t in 'LR'},
                     lift={t: round(float(limbs[t]['lift'][i]), 4) for t in 'LR'}, hands={t: str(limbs[t]['hand'][i]) for t in 'LR'})
                for i in range(n)]


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def mirror_frame(f: dict) -> dict:
    """좌우 반전: L↔R을 바꾸고 각도를 거울에 비춘다."""
    m = lambda v: [_wrap(math.pi - v[0]), v[1], _wrap(math.pi - v[2]), v[3]]
    return dict(f, shift=-f['shift'], lean=-f['lean'], nod=-f['nod'],
                arms={'L': m(f['arms']['R']), 'R': m(f['arms']['L'])}, legs={'L': m(f['legs']['R']), 'R': m(f['legs']['L'])},
                lift={'L': f['lift']['R'], 'R': f['lift']['L']}, hands={'L': f['hands']['R'], 'R': f['hands']['L']})


def amplify_frame(f: dict, k: float) -> dict:
    """'더 재미있게': 팔다리가 아래로 늘어진 자세(-90°)에서 벗어난 만큼, 몸 이동·기울기를 k배 키운다."""
    if k == 1:
        return f
    down = -math.pi / 2
    amp = lambda v, kk: [down + _wrap(v[0] - down) * kk, v[1], down + _wrap(v[2] - down) * kk, v[3]]
    return dict(f, shift=f['shift'] * k, lean=max(-.6, min(.6, f['lean'] * k)), nod=f['nod'] * k,
                arms={t: amp(f['arms'][t], k) for t in 'LR'}, legs={t: amp(f['legs'][t], 1 + (k - 1) * .5) for t in 'LR'})


def _blend(a: dict, b: dict, w: float) -> dict:
    lerp = lambda x, y: x + (y - x) * w
    angle = lambda x, y: x + _wrap(y - x) * w
    lim = lambda p, q: [angle(p[0], q[0]), lerp(p[1], q[1]), angle(p[2], q[2]), lerp(p[3], q[3])]
    return dict(shift=lerp(a['shift'], b['shift']), air=lerp(a['air'], b['air']), lean=lerp(a['lean'], b['lean']), nod=lerp(a['nod'], b['nod']),
                arms={t: lim(a['arms'][t], b['arms'][t]) for t in 'LR'}, legs={t: lim(a['legs'][t], b['legs'][t]) for t in 'LR'},
                lift={t: lerp(a['lift'][t], b['lift'][t]) for t in 'LR'}, hands=b['hands'] if w > .5 else a['hands'])


def choreo(raw: dict, plan: list[dict], beat_period: float, per_beat: int = 12, fade_beats: float = .5) -> dict:
    """plan의 구간들을 순서대로 이어 붙인다. 원곡의 1박 = 목표 곡의 1박.
    plan 항목: {"beats": 32, "start_beat": 97 | "start_seconds": 38.6 | "auto": 0, "mirror": false, "amplify": 1.2}
    "auto": n 은 best_windows가 고른 n번째 구간을 쓴다."""
    src = Source(raw)
    auto = src.best_windows(max([p.get('auto', -1) for p in plan] + [-1]) + 1, max(p['beats'] for p in plan)) if any('auto' in p for p in plan) else []
    frames, used = [], []
    for p in plan:
        if 'start_seconds' in p:
            b0 = round((p['start_seconds'] - raw['firstBeat']) / raw['beatPeriod'])
        else:
            b0 = p.get('start_beat', auto[p['auto'] % len(auto)] if 'auto' in p else 0)   # 고른 구간이 모자라면 돌려 쓴다
        seg = src.segment(b0, p['beats'], per_beat)
        seg = [amplify_frame(mirror_frame(f) if p.get('mirror') else f, p.get('amplify', 1.0)) for f in seg]
        fade = int(fade_beats * per_beat)
        if frames and fade:                                   # 이음매는 반 박 동안 섞는다
            for i in range(min(fade, len(seg))):
                seg[i] = _blend(frames[-1], seg[i], (i + 1) / (fade + 1))
        frames += seg
        used.append(dict(p, start_beat=int(b0), start_seconds=round(src.beat_time(b0), 3)))
    return {'format': 'dance2d/angles-v1', 'beatPeriod': beat_period, 'bpm': round(60 / beat_period, 3), 'perBeat': per_beat,
            'beats': len(frames) // per_beat, 'duration': len(frames) / per_beat * beat_period,
            'source': {'video': raw['source'], 'bpm': raw['bpm'], 'segments': used,
                       'note': '관절 좌표만 동작 참고로 사용. 원본 영상·음원은 결과에 넣지 않는다.'},
            'frames': frames}


# ───────────────────────────── 3) autorig ─────────────────────────────
def _gap_x(alpha: np.ndarray, y: int, x_from: float, x_to: float) -> float | None:
    """y행에서 x_from→x_to 방향으로 처음 나오는 투명 구간의 가운데 x."""
    xs = np.arange(int(x_from), int(x_to), 1 if x_to > x_from else -1)
    row = alpha[y, np.clip(xs, 0, alpha.shape[1] - 1)] < 24
    if not row.any():
        return None
    i = int(np.argmax(row))
    j = i
    while j < len(row) and row[j]:
        j += 1
    return float(xs[(i + j - 1) // 2])


def autorig(image: str) -> dict:
    """정면 중립 전신 원화에서 rig spec 초안을 만든다. 사람형 캐릭터에서 가장 잘 맞고,
    동물·특이 체형은 결과 그림(parts-map)을 보고 손으로 고친다."""
    import cv2
    img = cv2.imread(image, cv2.IMREAD_UNCHANGED)
    H, W = img.shape[:2]
    alpha = img[:, :, 3]
    rgb = img[:, :, :3].astype(np.float32)
    a = alpha[..., None] / 255.0
    flat = (rgb * a + 255 * (1 - a)).astype(np.uint8)
    mp, det = _landmarker(False)
    with det:
        r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(flat[:, :, ::-1])))
    if not r.pose_landmarks:
        raise SystemExit('관절을 찾지 못했습니다. rig spec을 손으로 작성하세요.')
    p = {i: (lm.x * W, lm.y * H) for i, lm in enumerate(r.pose_landmarks[0])}
    ys, xs = np.where(alpha > 128)
    floor = int(ys.max())
    cx = (p[23][0] + p[24][0]) / 2
    # 화면 왼쪽(L) 관절
    pick = lambda a_, b_: (p[a_], p[b_]) if p[a_][0] < p[b_][0] else (p[b_], p[a_])
    (shL, shR), (elL, elR), (wrL, wrR) = pick(11, 12), pick(13, 14), pick(15, 16)
    (hpL, hpR), (knL, knR), (anL, anR) = pick(23, 24), pick(25, 26), pick(27, 28)
    (ixL, ixR) = pick(19, 20)
    mouth = (p[9][1] + p[10][1]) / 2
    neck_y = mouth + .62 * ((shL[1] + shR[1]) / 2 - mouth)
    tipL = (wrL[0] + (ixL[0] - wrL[0]) * 2.2, wrL[1] + (ixL[1] - wrL[1]) * 2.2)
    # 팔/몸통 경계: 팔 중심선에서 몸 쪽으로 소매 반폭만큼 떨어진 선. 그 사이에 원화의 투명 빈틈이 있으면 빈틈을 따른다.
    upper = math.dist(shL, elL)
    def boundary(sh, el, wr):
        pts = []
        for t in np.linspace(0, 1, 9):
            a_, b_, f = (sh, el, t * 2) if t < .5 else (el, wr, t * 2 - 1)
            c = (a_[0] + (b_[0] - a_[0]) * f, a_[1] + (b_[1] - a_[1]) * f)
            w = upper * (.34 - .1 * t)
            g = _gap_x(alpha, int(c[1]), c[0] + 8, c[0] + w + 45)
            pts.append((g if g is not None else c[0] + w, c[1]))
        return [(sh[0] + upper * .25, neck_y + 30)] + pts + [(pts[-1][0], wr[1] + 30)]
    bL = boundary(shL, elL, wrL)
    cut_y = int(min(wrL[1], wrR[1]) + .9 * (tipL[1] - wrL[1]) + 60)
    crotch = (cx, (hpL[1] + hpR[1]) / 2 + .32 * (knL[1] - hpL[1]))
    shoe_y = int(anL[1] + .1 * (floor - anL[1]))
    hem_y = int(anL[1] + .55 * (floor - anL[1]))
    pelvis_top = int((hpL[1] + hpR[1]) / 2 - .32 * ((hpL[1] + hpR[1]) / 2 - (shL[1] + shR[1]) / 2))
    m = lambda pts: [(round(2 * cx - x), round(y)) for x, y in pts]
    R = lambda pts: [(round(x), round(y)) for x, y in pts]
    arm = R([(0, bL[0][1])] + bL + [(bL[-1][0] - 6, cut_y), (0, cut_y)])
    leg = R([(0, crotch[1] - 70), (cx - 3, crotch[1] - 70), (cx - 3, hem_y + 10), (0, hem_y + 10)])
    shoe = R([(0, shoe_y), (cx - 3, shoe_y), (cx - 3, H), (0, H)])
    torso = R([(bL[0][0], neck_y - 10)] + bL + [(bL[-1][0], crotch[1] - 40)])
    torso = torso + m(torso[::-1])
    spec = {
        'image': str(Path(image).resolve()), 'floor': floor, 'kind': 'biped',
        'order': ['shoe.L', 'shoe.R', 'leg.L', 'leg.R', 'pelvis', 'torso', 'head', 'arm.L', 'arm.R'],
        'regions': {
            'shoe.L': shoe, 'shoe.R': m(shoe), 'leg.L': leg, 'leg.R': m(leg),
            'pelvis': R([(cx - 1.7 * (cx - hpL[0]), pelvis_top), (cx + 1.7 * (hpR[0] - cx), pelvis_top), (cx + 1.7 * (hpR[0] - cx), crotch[1] + 6), (cx, crotch[1] + 14), (cx - 1.7 * (cx - hpL[0]), crotch[1] + 6)]),
            'torso': torso,
            'head': R([(0, 0), (W, 0), (W, neck_y), (0, neck_y)]),
            'arm.L': arm, 'arm.R': m(arm),
        },
        'centers': {
            'arm.L': R([(shL[0] + 30, shL[1] - 40), shL, elL, wrL, tipL]),
            'leg.L': R([(hpL[0] + 6, hpL[1] - 60), hpL, knL, anL, (anL[0] - 6, anL[1] + 60)]),
        },
        'pivots': {'head': R([(cx, neck_y)])[0], 'torso': R([(cx, pelvis_top - 30)])[0], 'pelvis': R([(cx, (hpL[1] + hpR[1]) / 2)])[0],
                   'shoe.L': R([anL])[0], 'shoe.R': R([m([anL])[0]])[0]},
        'feather': {'pelvis': 34},
        'landmarks': {k: R([v])[0] for k, v in p.items()},
    }
    spec['centers']['arm.R'] = m(spec['centers']['arm.L'])
    spec['centers']['leg.R'] = m(spec['centers']['leg.L'])
    return spec


# ───────────────────────────── 4) cut ─────────────────────────────
def cut(spec: dict, out_dir: str) -> dict:
    """spec의 다각형대로 원화를 부위 PNG로 자른다. 가장자리는 4배로 칠해 부드럽게.
    feather[name]=px 이면 그 부위 아랫단을 px만큼 흐려 아래 부위와의 이음매를 숨긴다."""
    import cv2
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(spec['image'], cv2.IMREAD_UNCHANGED)
    H, W = img.shape[:2]
    alpha = img[:, :, 3]
    parts = {}
    for name in spec['order']:
        poly = spec['regions'][name]
        mask = np.zeros((H * 4, W * 4), np.uint8)
        cv2.fillPoly(mask, [np.array(poly, np.int32) * 4], 255, cv2.LINE_AA)
        mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
        if name in spec.get('feather', {}):
            bottom = max(y for _, y in poly)
            mask *= np.clip((bottom - np.arange(H)) / spec['feather'][name], 0, 1)[:, None]
        a = (alpha.astype(np.float32) * mask / 255).astype(np.uint8)
        ys, xs = np.where(a > 4)
        x0, x1, y0, y1 = max(0, xs.min() - 2), min(W, xs.max() + 3), max(0, ys.min() - 2), min(H, ys.max() + 3)
        part = img[y0:y1, x0:x1].copy()
        part[:, :, 3] = a[y0:y1, x0:x1]
        cv2.imwrite(str(out / f'{name}.png'), part)
        info = {'file': f'{name}.png', 'box': [int(x0), int(y0), int(x1), int(y1)]}
        if name in spec.get('centers', {}):
            info['center'] = spec['centers'][name]
        if name in spec.get('pivots', {}):
            info['pivot'] = spec['pivots'][name]
        if name in spec.get('extras', {}):
            info.update(spec['extras'][name])
        parts[name] = info
    rig = {'source': spec['image'], 'size': [W, H], 'floor': spec['floor'], 'kind': spec.get('kind', 'biped'),
           'centerX': spec.get('centerX', W / 2), 'order': spec['order'], 'parts': parts}
    (out / 'parts.json').write_text(json.dumps(rig, ensure_ascii=False, indent=1))
    preview(spec, str(out / 'parts-map.png'))
    return rig


def preview(spec: dict, path: str) -> None:
    """부위 경계와 중심선을 원화 위에 그린 검수 그림."""
    import cv2
    img = cv2.imread(spec['image'], cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3:4] / 255.0
    vis = (img[:, :, :3] * a * .55 + 235 * (1 - a) + 90 * a).astype(np.uint8)
    colors = [(80, 80, 230), (80, 160, 230), (60, 200, 60), (200, 160, 60), (200, 60, 200), (60, 200, 200), (230, 120, 60), (120, 60, 230), (60, 120, 160), (20, 20, 20)]
    for (name, poly), c in zip(spec['regions'].items(), colors * 2):
        cv2.polylines(vis, [np.array(poly, np.int32)], True, c, 3)
    for pts in spec.get('centers', {}).values():
        cv2.polylines(vis, [np.array(pts, np.int32)], False, (0, 0, 0), 4)
        for q in pts:
            cv2.circle(vis, tuple(map(int, q)), 9, (255, 255, 255), -1)
    cv2.imwrite(path, vis)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('extract', help='안무 영상 → 관절/박자 json')
    e.add_argument('video'); e.add_argument('--crop', nargs=2, type=int); e.add_argument('-o', required=True)
    c = sub.add_parser('choreo', help='관절 json → 목표 곡 박자의 춤 데이터')
    c.add_argument('raw'); c.add_argument('--score', required=True, help='beatPeriod가 든 json(예: 음악 분석 score.json)')
    c.add_argument('--beats', type=int, default=32, help='plan이 없을 때 자동 구간으로 채울 총 박수')
    c.add_argument('--plan', help='구간 계획 json 파일(list)'); c.add_argument('--window', type=int, default=32)
    c.add_argument('--amplify', type=float, default=1.0); c.add_argument('-o', required=True)
    a = sub.add_parser('autorig', help='원화 → rig spec 초안 + 검수 그림')
    a.add_argument('image'); a.add_argument('-o', required=True)
    k = sub.add_parser('cut', help='rig spec → 부위 PNG + parts.json')
    k.add_argument('spec'); k.add_argument('-o', required=True)
    args = ap.parse_args()
    if args.cmd == 'extract':
        Path(args.o).write_text(json.dumps(extract(args.video, tuple(args.crop) if args.crop else None)))
    elif args.cmd == 'choreo':
        raw = json.loads(Path(args.raw).read_text())
        score = json.loads(Path(args.score).read_text())
        period = score['beatPeriod']
        if args.plan:
            plan = json.loads(Path(args.plan).read_text())
        else:
            n = math.ceil(args.beats / args.window)
            plan = [{'auto': i, 'beats': args.window, 'amplify': args.amplify, 'mirror': i % 2 == 1} for i in range(n)]
        out = choreo(raw, plan, period)
        out['firstBeat'] = score.get('firstBeat', 0.0)
        Path(args.o).write_text(json.dumps(out, ensure_ascii=False))
        print(json.dumps({k: v for k, v in out.items() if k != 'frames'}, ensure_ascii=False))
    elif args.cmd == 'autorig':
        spec = autorig(args.image)
        Path(args.o).write_text(json.dumps(spec, ensure_ascii=False, indent=1))
        preview(spec, str(Path(args.o).with_suffix('.png')))
        print('spec', args.o, '검수 그림', Path(args.o).with_suffix('.png'))
    elif args.cmd == 'cut':
        rig = cut(json.loads(Path(args.spec).read_text()), args.o)
        print('parts', rig['order'])


if __name__ == '__main__':
    main()
