"""anim_object — 정면 원화 한 장을 Live2D식 부위 레이어로 나눠 Three.js에서 고개를 돌리게 하는 2D 파이프라인.

M007 세라 V8(project/m007/head_turn_v8)에서 검증한 방식을 재사용할 수 있게 묶었다.
왜 이 방식인지, 무엇을 조심해야 하는지는 같은 폴더의 README.md를 먼저 본다.

    1) labels   선화의 닫힌 영역에 번호를 매긴 지도 → 얼굴 피부 영역을 고를 점(skin_seeds)을 정한다
    2) cut      spec(JSON)대로 원화를 7개 레이어 PNG로 나누고 layers.json + 검수 그림을 만든다
    3) fill     얼굴이 옆으로 밀릴 때 드러나는 뒷머리 띠를 옆모습 원화에서 가져와 채운다
    4) preview  rig.json의 깊이장으로 여러 각도를 근사 렌더(브라우저 없이 빠른 확인)
    5) init     Three.js 플레이어(web/)와 rig.json 예시를 작업 폴더에 복사한다

레이어(그리기 순서): hair_back → neck → face → eye_l → eye_r → hair_front → bun(선택)
변형: 정점 x' = x + sin(각도) × 깊이. 얼굴·머리카락이 서로 다른 깊이장을 써서 시차가 생긴다.

실행(저장소 루트에서):
    PY=/Users/jatu/.venvs/bongsik-morph/bin/python   # numpy, opencv
    $PY -m lib.com.jatu.anim.anim_object labels front.png -o labels.png
    $PY -m lib.com.jatu.anim.anim_object init  project/xxx/head_turn
    $PY -m lib.com.jatu.anim.anim_object cut   spec.json -o project/xxx/head_turn
    $PY -m lib.com.jatu.anim.anim_object fill  spec.json -o project/xxx/head_turn
    $PY -m lib.com.jatu.anim.anim_object preview project/xxx/head_turn --angles=-30,0,30
같은 내용을 `python lib/com/jatu/anim/anim-object.py <명령> ...` 으로도 실행할 수 있다.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ORDER = ['hair_back', 'neck', 'face', 'eye_l', 'eye_r', 'hair_front', 'bun']
COLORS = dict(hair_back=(200, 120, 60), neck=(120, 120, 120), face=(90, 200, 120),
              eye_l=(40, 40, 230), eye_r=(230, 40, 200), hair_front=(240, 180, 40), bun=(60, 220, 240))


# ───────────────────────────── 공통 ─────────────────────────────
def _cv2():
    import cv2
    return cv2


def load_spec(path: str | Path) -> tuple[dict, Path]:
    p = Path(path).resolve()
    return json.loads(p.read_text(encoding='utf-8')), p.parent


def read_gray(path: Path, crop: list[int] | None = None) -> np.ndarray:
    cv2 = _cv2()
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    if crop:  # [x0, x1] 가로로 여러 장이 붙은 시트에서 한 칸
        img = img[:, crop[0]:crop[1]]
    return img


def fill_holes(m: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    ff = m.astype(np.uint8).copy()
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 1)
    return m | (ff == 0)


def near(mask: np.ndarray, d: float) -> np.ndarray:
    cv2 = _cv2()
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) <= d


def poly_mask(points, shape) -> np.ndarray:
    cv2 = _cv2()
    m = np.zeros(shape, np.uint8)
    if points:
        cv2.fillPoly(m, [np.array(points, np.int32)], 1)
    return m.astype(bool)


def region_labels(gray: np.ndarray, hard: int = 170):
    """선(hard보다 어두운 곳)으로 닫힌 흰 영역에 번호를 매긴다. 1번이 보통 배경."""
    cv2 = _cv2()
    ink = cv2.dilate((gray < hard).astype(np.uint8), np.ones((2, 2), np.uint8))
    return cv2.connectedComponentsWithStats((1 - ink).astype(np.uint8), connectivity=4)


# ───────────────────────────── 1) labels ─────────────────────────────
def labels(image: str, out: str) -> None:
    """번호 지도. 얼굴 피부·눈썹 사이·눈 안쪽처럼 '얼굴'에 속하는 영역 안의 한 점씩을 skin_seeds에 적는다."""
    cv2 = _cv2()
    gray = read_gray(Path(image))
    n, lab, st, cen = region_labels(gray)
    rng = np.random.default_rng(3)
    col = rng.integers(60, 255, (n, 3)).astype(np.uint8)
    col[0] = 0
    vis = col[lab]
    vis[gray < 170] = 0
    big = cv2.resize(vis, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    for i in range(1, n):
        if st[i, 4] < 150:
            continue
        m = (lab == i).astype(np.uint8)
        y, x = np.unravel_index(cv2.distanceTransform(m, cv2.DIST_L2, 3).argmax(), m.shape)
        for c, w in ((0, 2), (255, 1)):
            cv2.putText(big, f'{i}', (int(x * 2) - 8, int(y * 2) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (c, c, c), w)
    cv2.imwrite(out, big)
    print(f'{out}: {n - 1}개 영역. 큰 영역:', [(i, int(st[i, 4])) for i in range(1, n) if st[i, 4] > 3000])


# ───────────────────────────── 2) cut ─────────────────────────────
def cut(spec_path: str, out_dir: str) -> dict:
    """spec대로 레이어 PNG(2배)와 parts/layers.json을 만든다. 정면 합성 차이를 qa/에 남긴다."""
    cv2 = _cv2()
    spec, base = load_spec(spec_path)
    out = Path(out_dir)
    (out / 'parts').mkdir(parents=True, exist_ok=True)
    (out / 'qa').mkdir(parents=True, exist_ok=True)
    src = read_gray(base / spec['image'])
    shutil.copyfile(base / spec['image'], out / 'parts/source_front.png')
    H, W = src.shape
    up = spec.get('scale', 2)
    P = {k: poly_mask(v, (H, W)) for k, v in spec['poly'].items()}
    head = spec['head']
    ink_t, own_d = spec.get('ink', 235), spec.get('own_d', 4.5)

    # 기본 영역
    ink = src < ink_t
    _, lab, _, _ = region_labels(src)
    background = lab == lab[spec.get('background_seed', [0, 0])[1], spec.get('background_seed', [0, 0])[0]]
    figure = fill_holes(~background)
    skin_ids = {int(lab[y, x]) for x, y in spec['skin_seeds']} - {0}
    skin = fill_holes(np.isin(lab, list(skin_ids)))
    skin = cv2.morphologyEx(skin.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    yy, xx = np.mgrid[0:H, 0:W]
    head_ell = ((xx - head['cx']) / head['rx']) ** 2 + ((yy - head['cy']) / head['ry']) ** 2 <= 1
    front_zone = yy < spec['front_y']
    for k in spec.get('front_extra', []):
        front_zone |= P[k]
    hair_pix = figure & ~skin & ~ink
    # 얼굴 안쪽의 선 사이 틈(눈썹 사이 등)은 머리카락이 아니다
    face_zone = fill_holes(cv2.morphologyEx(skin.astype(np.uint8), cv2.MORPH_CLOSE,
                                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))).astype(bool))
    hair_core = hair_pix & ~face_zone
    n, hl, st, _ = cv2.connectedComponentsWithStats(hair_core.astype(np.uint8), connectivity=8)
    hair_core = np.isin(hl, [i for i in range(1, n) if st[i, 4] >= spec.get('hair_min_area', 300)])
    has_bun = 'bun' in P
    bun_poly = P.get('bun', np.zeros((H, W), bool))
    tie = P.get('tie', np.zeros((H, W), bool))
    bun_out = bun_poly & ~head_ell

    # 레이어별 흰 채움(서로 가리는 면)
    fill = {}
    fill['bun'] = (bun_out & figure) | tie
    fill['hair_front'] = (hair_core & front_zone & ~fill['bun']) | (head_ell & bun_poly)
    fill['face'] = skin | (P['forehead'] & figure)
    fill['eye_l'], fill['eye_r'] = P['eye_l'], P['eye_r']
    fill['hair_back'] = hair_core & ~front_zone & ~fill['bun']
    fill['neck'] = P['neck']

    # 선 소유: 선 한 줄이 두 레이어에 나뉘거나 위아래로 복사되면 움직일 때 끊기거나 유령선이 생긴다
    own = {}
    ext_hair = P['forehead'] & hair_core            # 이마를 덮는 앞머리
    own['bun'] = ink & (bun_out | tie)
    eyes = fill['eye_l'] | fill['eye_r']
    own['hair_front'] = ink & near(hair_core & front_zone & ~fill['bun'], own_d) & ~own['bun'] & ~(eyes & ~near(ext_hair, 2.0))
    own['eye_l'] = ink & fill['eye_l'] & ~near(ext_hair, 2.0)
    own['eye_r'] = ink & fill['eye_r'] & ~near(ext_hair, 2.0)
    face_ink = ink & near(skin & ~ink, own_d) & ~near(ext_hair, own_d)
    # 턱 끝의 굵은 선은 아래 가장자리까지 얼굴이 갖는다(목에 남으면 두 번째 턱선)
    face_ink |= ink & near(skin & ~ink, 10) & (yy > spec.get('chin_line_y', H)) & ~near(hair_core, 2)
    own['face'] = face_ink & ~own['eye_l'] & ~own['eye_r']
    # 관자놀이 머리카락 위로 그려진 눈꼬리 선 자리는 머리카락 채움에서 비운다
    fill['hair_front'] &= ~near(own['eye_l'] | own['eye_r'], 1.0)
    own['hair_back'] = ink & near(hair_core & ~front_zone, own_d) & ~own['bun']
    own['neck'] = ink & fill['neck'] & ~own['face']
    left = ink & ~np.any([own[k] for k in own], axis=0)
    own['hair_back'] |= left & (yy >= spec['front_y'])
    own['hair_front'] |= left & (yy < spec['front_y'])

    # 원화에 없던(가려진) 선 보충
    extra = {k: np.zeros((H, W), np.uint8) for k in fill}
    if has_bun and spec.get('bun_cap'):  # 묶음 밑을 지나는 머리 외곽선: 묶음이 뒤로 숨을 때 보인다
        c = spec['bun_cap']
        cap = np.zeros((H, W), np.uint8)
        cv2.ellipse(cap, (head['cx'], head['cy']), (head['rx'], head['ry']), 0, c['from'], c['to'], 255, 3, cv2.LINE_AA)
        cap[~near(bun_out, 3) | (yy < c.get('min_y', 0))] = 0
        extra['hair_front'] = cap
    if spec.get('neck_ext'):  # 턱 밑으로 이어지는 목선: 얼굴이 밀리면 보인다
        e = spec['neck_ext']
        lines = np.zeros((H, W), np.uint8)
        for x_top, x_bot in e['x']:
            cv2.line(lines, (x_top, e['y'][0]), (x_bot, e['y'][1]), 255, 3, cv2.LINE_AA)
        lines[~fill['face']] = 0
        extra['neck'] = lines

    order = [k for k in ORDER if k != 'bun' or has_bun]

    def layer_rgba(name):
        f = fill[name] & ~ink
        o = own[name]
        body = cv2.morphologyEx((f | o).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
        body &= near(f, 6) | o
        gray = np.where(o, src, 255).astype(np.float32)
        alpha = np.where(body, 1.0, np.where(o, (255 - src.astype(np.float32)) / 255, 0.0))
        ex = extra[name].astype(np.float32) / 255
        gray = np.minimum(gray, 255 * (1 - ex) + 20 * ex)
        alpha = np.maximum(alpha, ex)
        big = cv2.resize(np.dstack([gray, gray, gray, alpha * 255]).astype(np.float32), (W * up, H * up), interpolation=cv2.INTER_CUBIC)
        big = np.clip(big, 0, 255).astype(np.uint8)
        ys, xs = np.nonzero(big[..., 3] > 2)
        x0, x1 = max(xs.min() - 4, 0), min(xs.max() + 5, W * up)
        y0, y1 = max(ys.min() - 4, 0), min(ys.max() + 5, H * up)
        cv2.imwrite(str(out / f'parts/{name}.png'), cv2.cvtColor(big[y0:y1, x0:x1], cv2.COLOR_RGBA2BGRA))
        return dict(name=name, file=f'parts/{name}.png', x=x0 / up, y=y0 / up, w=(x1 - x0) / up, h=(y1 - y0) / up)

    meta = dict(source='parts/source_front.png', size=[W, H], scale=up, head=head, layers=[layer_rgba(k) for k in order])
    (out / 'parts/layers.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')

    # 검수: 부위 색 지도 + 정면 합성 차이
    vis = np.full((H, W, 3), 255, np.uint8)
    for k in order:
        vis[fill[k] & ~ink] = (0.35 * np.array(COLORS[k]) + 0.65 * 255).astype(np.uint8)
    for k in order:
        vis[own[k]] = COLORS[k]
    cv2.imwrite(str(out / 'qa/layer_map.png'), cv2.resize(vis, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_NEAREST))
    comp = composite(out)
    diff = np.abs(comp.astype(np.float32) - src.astype(np.float32))
    cv2.imwrite(str(out / 'qa/front_composite.png'), comp)
    cv2.imwrite(str(out / 'qa/front_diff.png'), np.clip(255 - diff * 3, 0, 255).astype(np.uint8))
    stats = dict(mean_abs_diff=round(float(diff.mean()), 3), pixels_over_40=int((diff > 40).sum()), layers=order)
    print('cut:', stats, '→ qa/layer_map.png, qa/front_diff.png 확인')
    return stats


def composite(out_dir: Path) -> np.ndarray:
    """레이어를 정면(0°)으로 겹친 회색 이미지(원화 크기)."""
    cv2 = _cv2()
    meta = json.loads((Path(out_dir) / 'parts/layers.json').read_text(encoding='utf-8'))
    up, (W, H) = meta['scale'], meta['size']
    comp = np.full((H * up, W * up, 3), 255, np.float32)
    for L in meta['layers']:
        im = cv2.imread(str(Path(out_dir) / L['file']), cv2.IMREAD_UNCHANGED).astype(np.float32)
        x0, y0 = int(round(L['x'] * up)), int(round(L['y'] * up))
        h, w = im.shape[:2]
        a = im[..., 3:4] / 255
        comp[y0:y0 + h, x0:x0 + w] = comp[y0:y0 + h, x0:x0 + w] * (1 - a) + im[..., :3] * a
    return cv2.resize(comp, (W, H), interpolation=cv2.INTER_AREA)[..., 0].astype(np.uint8)


# ───────────────────────────── 깊이장 (web/headturn.js와 같은 식) ─────────────────────────────
def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def depth(rig: dict, field_name: str, x, y):
    """돔(cos 단면) + 가우스 돌출 + 세로 경사. 값이 클수록 고개를 돌릴 때 더 많이 움직인다."""
    f = rig['fields'][field_name]
    d = np.zeros(np.broadcast(x, y).shape)
    if 'dome' in f:
        o = f['dome']
        r = np.hypot((x - o['cx']) / o['rx'], (y - o['cy']) / o['ry'])
        d += o['rz'] * np.where(r >= 1, 0, np.cos(np.pi / 2 * np.minimum(r, 1)))
    for b in f.get('bumps', []):
        d += b['amp'] * np.exp(-(((x - b['x']) ** 2) / (2 * b['sx'] ** 2) + ((y - b['y']) ** 2) / (2 * b['sy'] ** 2)))
    if 'ramp' in f:
        d += f['ramp']['depth'] * smooth(f['ramp']['y0'], f['ramp']['y1'], y)
    return d


def fold_check(rig: dict, depth_scale: float = 1.6) -> dict:
    """가로 기울기 × sin(최대각) × 입체감이 1을 넘으면 메시가 접힌다. 필드별 최대값을 돌려준다."""
    s = np.sin(np.radians(rig['maxAngle'])) * depth_scale
    yy, xx = np.mgrid[0:800:2, 0:800:2].astype(float)
    return {k: round(float(np.abs(np.gradient(depth(rig, k, xx, yy), 2, axis=1)).max() * s), 3) for k in rig['fields']}


def _layer_canvas(out_dir: Path, meta: dict, name: str, up: int | None = None):
    """레이어 PNG를 원화(또는 up배) 캔버스에 펼친 RGBA float."""
    cv2 = _cv2()
    L = next(l for l in meta['layers'] if l['name'] == name)
    s = meta['scale']
    W, H = meta['size']
    im = cv2.imread(str(out_dir / L['file']), cv2.IMREAD_UNCHANGED)
    big = np.zeros((H * s, W * s, 4), np.uint8)
    x0, y0 = int(round(L['x'] * s)), int(round(L['y'] * s))
    big[y0:y0 + im.shape[0], x0:x0 + im.shape[1]] = im[:H * s - y0, :W * s - x0]
    if up == s:
        return big, (x0, y0, im.shape[1], im.shape[0])
    return cv2.resize(big.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA), None


# ───────────────────────────── 4) preview ─────────────────────────────
def render(out_dir: str | Path, angle: float, rig: dict | None = None) -> np.ndarray:
    """가로 깊이 이동만으로 근사 렌더(머리카락 지연·숙임·깜빡임·묶음 가림 제외)."""
    out_dir = Path(out_dir)
    rig = rig or json.loads((out_dir / 'rig.json').read_text(encoding='utf-8'))
    meta = json.loads((out_dir / 'parts/layers.json').read_text(encoding='utf-8'))
    W, H = meta['size']
    s = np.sin(np.radians(angle))
    xs = np.arange(W, dtype=float)
    comp = np.full((H, W), 255.0)
    for L in meta['layers']:
        spec = rig['layers'][L['name']]
        rgba, _ = _layer_canvas(out_dir, meta, L['name'])
        gray, alpha = rgba[..., 0], rgba[..., 3] / 255
        g2, a2 = np.zeros_like(gray), np.zeros_like(alpha)
        for y in range(H):
            d = depth(rig, spec['field'], xs, y)
            if 'tuck' in spec:
                t = spec['tuck']
                d = d + t['depth'] * smooth(0, t['range'], np.hypot(xs - t['x'], y - t['y']))
            src = np.interp(xs, xs + d * s, xs, left=-1, right=-1)
            ok = src >= 0
            g2[y, ok] = np.interp(src[ok], xs, gray[y])
            a2[y, ok] = np.interp(src[ok], xs, alpha[y])
        comp = comp * (1 - a2) + g2 * a2
    return comp.astype(np.uint8)


def preview(out_dir: str, angles: list[float], out: str | None = None) -> str:
    cv2 = _cv2()
    imgs = [render(out_dir, a) for a in angles]
    for im, a in zip(imgs, angles):
        cv2.putText(im, f'{a:+g}', (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2)
    path = out or str(Path(out_dir) / 'qa/preview.png')
    cv2.imwrite(path, np.hstack(imgs))
    rig = json.loads((Path(out_dir) / 'rig.json').read_text(encoding='utf-8'))
    print('preview:', path, '| 접힘 검사(1 미만이어야 함, 입체감 160%):', fold_check(rig))
    return path


# ───────────────────────────── 3) fill ─────────────────────────────
def fill(spec_path: str, out_dir: str) -> dict:
    """얼굴이 밀릴 때 드러나는 뒷머리 띠를 옆모습 원화에서 가져와 hair_back.png에 채운다.

    대응: 같은 높이의 줄에서 '얼굴 경계 바깥으로 k픽셀' 위치끼리 맞춘다.
      sign=+1 (화면 오른쪽을 보는 각도) → 왼쪽 띠가 드러난다 → 오른쪽을 보는 옆모습에서 가져온다
      sign=-1 (화면 왼쪽을 보는 각도)   → 오른쪽 띠 → 왼쪽을 보는 옆모습
    붙인 그림은 얼굴보다 아래(hair_back)에 들어가므로 정면에서는 보이지 않는다.
    반드시 cut 다음에 실행한다(cut이 hair_back.png를 새로 만든다).
    """
    cv2 = _cv2()
    spec, base = load_spec(spec_path)
    cfg = spec['fill']
    out = Path(out_dir)
    rig = json.loads((out / 'rig.json').read_text(encoding='utf-8'))
    meta = json.loads((out / 'parts/layers.json').read_text(encoding='utf-8'))
    up = meta['scale']
    W, H = meta['size']
    W2, H2 = W * up, H * up
    face_rgba, _ = _layer_canvas(out, meta, 'face', up)
    face_m = face_rgba[..., 3] > 128
    face_m = fill_holes(cv2.morphologyEx(face_m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool))
    front_cover = _layer_canvas(out, meta, 'hair_front', up)[0][..., 3] > 128
    back, (bx, by, bw, bh) = _layer_canvas(out, meta, 'hair_back', up)
    back = back.astype(np.float32)
    before = back.copy()
    xs2 = np.arange(W2, dtype=np.float64)
    xs1 = xs2 / up
    s_map, s_fill = cfg.get('s_map', 0.5), cfg.get('s_fill', 0.8)
    report = {}
    for src_cfg in cfg['sources']:
        side, sgn = src_cfg['side'], src_cfg['sign']
        img = read_gray(base / src_cfg['image'], src_cfg.get('crop'))
        img2 = cv2.resize(img, (W2, H2), interpolation=cv2.INTER_CUBIC).astype(np.float32)
        ex, ey = np.array(src_cfg['edge'], float).T
        map_x = np.full((H2, W2), -1, np.float32)
        map_y = np.zeros((H2, W2), np.float32)
        target = np.zeros((H2, W2), bool)
        on_side = (xs2 < W2 // 2) if side == 'left' else (xs2 >= W2 // 2)
        for y2 in range(cfg['y_range'][0] * up, cfg['y_range'][1] * up):
            y = y2 / up
            row = face_m[y2]
            cols = np.nonzero(row & on_side)[0]
            if len(cols) == 0:
                continue
            x_edge = (cols.min() if side == 'left' else cols.max()) / up
            dh = depth(rig, 'hair', xs1, y)
            df = depth(rig, 'face', xs1, y)
            # 드러나는 곳: 원래 얼굴 밑 + 앞머리에 안 가림 + s_fill 각도에서 얼굴 밖
            under = np.interp(xs1 + dh * sgn * s_fill, xs1 + df * sgn * s_fill, xs1)
            covered = row[np.clip(np.round(under * up).astype(int), 0, W2 - 1)]
            rev = row & ~front_cover[y2] & ~covered & on_side
            if not rev.any():
                continue
            e_r = x_edge + depth(rig, 'face', np.array([x_edge]), y)[0] * sgn * s_map
            q = xs1 + dh * sgn * s_map
            k = (e_r - q) if side == 'left' else (q - e_r)
            ys = y * src_cfg['chin'] / cfg['chin']
            if not (ey[0] <= ys <= ey[-1]):
                continue
            e_s = float(np.interp(ys, ey, ex)) + (-3 if side == 'left' else 3)  # 경계선 굵기만큼 바깥
            sx = (e_s - k) if side == 'left' else (e_s + k)
            map_x[y2, rev] = (sx[rev] * up).astype(np.float32)
            map_y[y2, rev] = ys * up
            target[y2] |= rev
        sample = cv2.remap(img2, map_x, map_y, cv2.INTER_LINEAR, borderValue=255)
        core = cv2.erode(target.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        edge = target & ~core  # 가장자리 2px은 기존 선과 겹쳐(더 진한 쪽) 잇는다
        g = back[..., 0]
        g[core] = sample[core]
        g[edge] = np.where(back[..., 3][edge] > 128, np.minimum(g[edge], sample[edge]), sample[edge])
        for c in range(3):
            back[..., c] = g
        back[..., 3][target] = 255
        report[side] = dict(source=src_cfg['image'], pixels_2x=int(target.sum()))
        dbg = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        cv2.polylines(dbg, [np.array(src_cfg['edge'], np.int32)], False, (0, 160, 0), 2)
        for x, y in np.stack([map_x[target] / up, map_y[target] / up], 1)[::7]:
            if 0 <= x < W and 0 <= y < H:
                dbg[int(y), int(x)] = (0, 0, 255)
        cv2.imwrite(str(out / f'qa/fill_hidden_source_{side}.png'), dbg)
    L = next(l for l in meta['layers'] if l['name'] == 'hair_back')
    cv2.imwrite(str(out / L['file']), back[by:by + bh, bx:bx + bw].clip(0, 255).astype(np.uint8))
    changed = np.abs(back - before).max(-1) > 0
    vis = cv2.cvtColor(back[..., 0].astype(np.uint8), cv2.COLOR_GRAY2BGR)
    vis[changed] = (0.5 * vis[changed] + [0, 0, 127]).astype(np.uint8)
    cv2.imwrite(str(out / 'qa/fill_hidden_back.png'), cv2.resize(vis, (W, H), interpolation=cv2.INTER_AREA))
    (out / 'qa/fill_hidden.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('fill:', report)
    return report


# ───────────────────────────── 5) init ─────────────────────────────
def init(out_dir: str, force: bool = False) -> None:
    """플레이어(web/)와 rig.json 예시, Three.js(r186)를 작업 폴더에 복사한다. 기존 파일은 덮어쓰지 않는다."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pairs = [(HERE / 'web' / n, out / n) for n in ('index.html', 'app.js', 'headturn.js', 'style.css')]
    pairs.append((HERE / 'examples/rig.json', out / 'rig.json'))
    pairs += [(p, out / 'vendor' / p.name) for p in sorted((HERE / 'web/vendor').iterdir())]
    for a, b in pairs:
        if b.exists() and not force:
            print('있음(건너뜀):', b)
            continue
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a, b)
        print('복사:', b)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='anim-object', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('labels', help='닫힌 영역 번호 지도')
    a.add_argument('image')
    a.add_argument('-o', '--out', default='labels.png')
    a = sub.add_parser('cut', help='spec대로 레이어 나누기')
    a.add_argument('spec')
    a.add_argument('-o', '--out', required=True)
    a = sub.add_parser('fill', help='가려진 뒷머리를 옆모습에서 채우기 (cut 다음)')
    a.add_argument('spec')
    a.add_argument('-o', '--out', required=True)
    a = sub.add_parser('preview', help='여러 각도 근사 렌더')
    a.add_argument('dir')
    a.add_argument('--angles', default='-30,-15,0,15,30')
    a.add_argument('-o', '--out')
    a = sub.add_parser('init', help='플레이어·rig.json 예시 복사')
    a.add_argument('dir')
    a.add_argument('--force', action='store_true')
    args = ap.parse_args(argv)
    if args.cmd == 'labels':
        labels(args.image, args.out)
    elif args.cmd == 'cut':
        cut(args.spec, args.out)
    elif args.cmd == 'fill':
        fill(args.spec, args.out)
    elif args.cmd == 'preview':
        preview(args.dir, [float(v) for v in args.angles.split(',')], args.out)
    elif args.cmd == 'init':
        init(args.dir, args.force)


if __name__ == '__main__':
    main()
