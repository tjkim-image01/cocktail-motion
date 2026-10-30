"""Assemble 01_레퍼런스/analysis-v4/bottles/data.json from the bottle_track / bottle_stream / bottle_art
caches, plus derived choreography numbers (phases, pour rock, rotation pivot, stream start/end,
droplet persistence) and a few direct pixel probes of the upright art (label box, fill offset).

usage: uv run -q --with opencv-python-headless --with numpy python scripts/v4/bottle_data.py
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '01_레퍼런스/analysis-v4/bottles'
TR = json.loads((OUT / '.cache-bottle-track.json').read_text())
ST = json.loads((OUT / '.cache-streams.json').read_text())
ART = json.loads((OUT / '.cache-art.json').read_text())
R = lambda a: np.array([[np.cos(np.radians(a)), -np.sin(np.radians(a))], [np.sin(np.radians(a)), np.cos(np.radians(a))]])


def probe(name):
    """Label border / outline / fill-offset positions read straight off the upright art (anchor-relative)."""
    a = np.load(str(OUT / f'.cache-art-{name}.npy')); img = np.clip(a[..., :3], 0, 255)
    tx, ty = TR[name]['art_tip']; tx = int(round(tx)); top = int(round(ty)) + 1
    g = img @ np.array([0.114, 0.587, 0.299]); sat = img.max(2) - img.min(2)
    ink = (g < 110) & (sat < 40)
    inkl = (g < 110) & (sat < 70)                              # border ink (vermouth fill also passes; handled below)
    col = inkl[:, tx - 20]
    top_rows = [y - top for y in range(top + 140, top + 172) if col[y] and not col[y + 1]]   # lower edge of top border
    bot_rows = [y - top for y in range(top + 222, top + 242) if col[y] and not col[y - 1]]   # upper edge of bottom border
    row = inkl[top + 165]
    l_cols = [x - tx for x in range(tx - 40, tx - 27) if row[x] and not row[x + 1]]
    r_cols = [x - tx for x in range(tx + 28, tx + 41) if row[x] and not row[x - 1]]
    lab_top, lab_bot = top_rows[-1] - 1, bot_rows[0] + 1        # 2 px border
    lab_l, lab_r = l_cols[-1] - 1, r_cols[0] + 1
    # body outline ink and fill extents on rows 130-150 / 240-255 (outside the label)
    outl, outr, fl, fr_ = [], [], [], []
    fill_ref = np.median(img[top + 245, tx - 10:tx + 10], 0)
    for y in list(range(top + 128, top + 150)) + list(range(top + 238, top + 256)):
        r = ink[y]; xi = [x - tx for x in range(tx - 52, tx + 54) if r[x]]
        if not xi: continue
        outl.append(min(xi)); outr.append(max(xi))
        fm = [x - tx for x in range(tx - 52, tx + 54) if np.linalg.norm(img[y, x] - fill_ref) < 45]
        if fm: fl.append(min(fm)); fr_.append(max(fm))
    return dict(label_outer_box=dict(x0=lab_l, x1=lab_r, y0=lab_top, y1=lab_bot, w=lab_r - lab_l + 1, h=lab_bot - lab_top + 1),
                body_ink_outer_x=[int(np.median(outl)), int(np.median(outr))],
                body_fill_x=[int(np.median(fl)), int(np.median(fr_))] if fl else None)


def phases(rows):
    f = np.array([r[0] for r in rows]); x = np.array([r[1] for r in rows]); y = np.array([r[2] for r in rows]); a = np.array([r[3] for r in rows])
    da = np.r_[0, np.diff(a)]; dx = np.r_[0, np.diff(x)]
    pour = f[a > 110]
    tilt_in = f[(da > 0.5) & (f < pour[0])]; tilt_out = f[(da < -0.5) & (f > pour[-1] - 5)]
    # pour rock: local extrema of the angle while pouring
    m = (a > 110)
    ext = []
    for k in range(2, len(a) - 2):
        if m[k] and a[k] == a[k - 2:k + 3].max(): ext.append(['max', int(f[k]), round(float(a[k]), 2)])
        if m[k] and a[k] == a[k - 2:k + 3].min(): ext.append(['min', int(f[k]), round(float(a[k]), 2)])
    mx = [e[1] for e in ext if e[0] == 'max' and e[2] > 117.0]
    mn = [e[1] for e in ext if e[0] == 'min' and e[2] < 115.0]
    mx = [v for k, v in enumerate(mx) if k == 0 or v - mx[k - 1] > 3]; mn = [v for k, v in enumerate(mn) if k == 0 or v - mn[k - 1] > 3]
    return dict(first_visible=int(f[0]), last_visible=int(f[-1]),
                slide_in=[int(f[0]), int(f[np.argmax((f > f[0]) & (np.abs(dx) < 1.6))])],
                tilt_in=[int(tilt_in[0]), int(pour[0])], pour_angle_over_110=[int(pour[0]), int(pour[-1])],
                tilt_out=[int(tilt_out[0]), int(tilt_out[-1])],
                slide_out=[int(f[np.argmax((f > tilt_out[-1]) & (dx < -1.0))]), int(f[-1])],
                pour_angle_range=[round(float(a[m].min()), 2), round(float(a[m].max()), 2)],
                pour_extrema=ext, pour_rock_maxima=mx, pour_rock_minima=mn, pour_rock_period_frames=round(float(np.mean(np.r_[np.diff(mx), np.diff(mn)])), 2),
                peak_angular_speed_in=round(float(da[f <= pour[0]].max()), 2), peak_angular_speed_out=round(float(-da[f >= pour[-1]].min()), 2))


def pivot(rows, f0, f1):
    """Instantaneous rotation centre (in upright-art coords, anchor = origin) for frame pairs f0..f1."""
    by = {r[0]: r for r in rows}; out = []
    for i in range(f0, f1):
        a, b = by[i], by[i + 1]
        th = b[3] - a[3]
        if abs(th) < 2: continue
        # point p (art) with  A_a + R(a) p == A_b + R(b) p   →  (R(a) - R(b)) p = A_b - A_a
        M = R(a[3]) - R(b[3]); p = np.linalg.solve(M, np.array([b[1] - a[1], b[2] - a[2]]))
        out.append([i, round(float(p[0]), 1), round(float(p[1]), 1)])
    return out


def jitter(rows, f0, f1):
    sel = np.array([r for r in rows if f0 <= r[0] <= f1])
    res = {}
    for k, nm in ((1, 'x'), (2, 'y'), (3, 'angle')):
        v = sel[:, k]; sm = np.convolve(np.pad(v, 2, mode='edge'), np.ones(5) / 5, mode='valid')
        res[nm] = round(float(np.std(v - sm)), 3)
    return res


def main():
    # cross-bottle comparison (same choreography, 150-frame offset?)
    by = {n: {r[0]: r for r in TR[n]['rows']} for n in TR}
    comp = {}
    for n, off in (('campari', 150), ('vermouth', 300)):
        d = np.array([[by[n][i + off][1] - r[1], by[n][i + off][2] - r[2], by[n][i + off][3] - r[3]]
                      for i, r in by['gin'].items() if i + off in by[n] and r[6] > 0.95 and by[n][i + off][6] > 0.95])
        comp[n] = dict(offset_frames=off, frames_compared=len(d),
                       median_abs_dx_dy_dangle=[round(float(v), 2) for v in np.median(np.abs(d), 0)],
                       max_abs_dx_dy_dangle=[round(float(v), 2) for v in np.abs(d).max(0)])
    bottles = {}
    for n in TR:
        rows = TR[n]['rows']; ph = phases(rows)
        tip_off = np.array(TR[n]['tip_from_centre'])
        bottles[n] = dict(
            visible_frames=[ph['first_visible'], ph['last_visible']],
            choreography=ph,
            rotation_pivot_tilt_in=pivot(rows, ph['tilt_in'][0], ph['tilt_in'][1]),
            rotation_pivot_tilt_out=pivot(rows, ph['tilt_out'][0] - 1, ph['tilt_out'][1]),
            pour_highpass_jitter_std=jitter(rows, ph['pour_angle_over_110'][0], ph['pour_angle_over_110'][1]),
            template=dict(frame=TR[n]['tmpl'], base_frame=TR[n]['base'], template_axis_deg_in_source=TR[n]['template_axis_deg'],
                          centroid_from_anchor_upright=[round(float(-tip_off[0]), 2), round(float(-tip_off[1]), 2)]),
            aniso_check=TR[n]['aniso_check'],
            track=[[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]] for r in rows])
    # streams
    streams = {}
    for n, sd in ST.items():
        fr = {int(k): v for k, v in sd['frames'].items()}
        sf = sorted(k for k, v in fr.items() if 'stream' in v)
        att = [k for k in sf if fr[k]['stream']['attached']]
        # stream start point relative to the bottle anchor, in upright-art coords
        rel = []
        for k in att:
            r = by[n].get(k)
            if r is None: continue
            p0 = np.array(fr[k]['stream']['pts'][0][:2]); rel.append(R(-r[3]) @ (p0 - [r[1], r[2]]))
        # droplet persistence: share of drops with a partner within 3 px in the next frame
        pers, tot = 0, 0
        for k in sorted(fr):
            a = fr[k].get('drops', []); b = fr.get(k + 1, {}).get('drops', [])
            for d in a:
                tot += 1
                if any(np.hypot(d[0] - e[0], d[1] - e[1]) < 3 for e in b): pers += 1
        drops = [d for v in fr.values() for d in v.get('drops', [])]
        ends = {k: fr[k]['stream'].get('band_end') for k in att}
        streams[n] = dict(
            pre_frame=sd['pre'], post_frame=sd['post'],
            first_frame=sf[0], last_frame=sf[-1], attached_frames=[att[0], att[-1]], detached_frames=[k for k in sf if k not in att],
            length_px_by_frame={k: fr[k]['stream']['length'] for k in sf},
            start_point_from_anchor_upright_median=[round(float(v), 1) for v in np.median(rel, 0)],
            surface_entry_y_by_frame={k: (e[1] if e else None) for k, e in ends.items()},
            cross_section=sd['cross_section_summary'],
            droplets=dict(frames_with_drops=sum(1 for v in fr.values() if v.get('drops')), total=len(drops),
                          radius_px_median=round(float(np.median([d[2] for d in drops])), 2) if drops else None,
                          radius_px_p10_p90=[round(float(np.percentile([d[2] for d in drops], q)), 2) for q in (10, 90)] if drops else None,
                          kinds={k: sum(1 for d in drops if d[4] == k) for k in ('drop', 'bubble')},
                          persist_next_frame_within_3px=round(pers / max(tot, 1), 2)),
            frames={k: fr[k] for k in sorted(fr)})
    art = {}
    for n, a in ART.items():
        art[n] = dict(a); art[n]['probe'] = probe(n)
    schema = {
        'units': 'pixels in the 1080x1080 reference frame (origin top-left, y down) unless noted; frame = 0-based index of sequential cv2 reads, t = frame/30 s',
        'pose_convention': 'anchor = mouth tip of the bottle = centre of the top edge of the lip ring. angle = long-axis angle in degrees, 0 = upright neck-up, positive = clockwise on screen. A point p of the upright art (x right, y down, origin = anchor, body toward +y) is drawn at anchor + scale * R(angle) p with R = [[cos,-sin],[sin,cos]].',
        'bottles.<name>.track': '[frame, anchor_x, anchor_y, angle_deg, scale, rmse, visible_fraction, centre_x, centre_y]; centre = body centroid (= anchor + R(angle) * template.centroid_from_anchor_upright), also the measured rotation pivot; rmse = masked colour RMS difference template vs frame in 0-255 units (boil + interpolation keep it ~30-38; ~17-20 on frames with the template boil phase); visible_fraction = share of the bottle silhouette inside the frame (the bottle enters/leaves through the left edge). scale was fixed at 1.0 after the aniso check found no change.',
        'bottles.<name>.choreography': 'phase frame ranges [first,last] derived from the track: slide_in, tilt_in (angle rising to >110), pour_angle_over_110, tilt_out, slide_out; pour_extrema = local max/min of the pour rocking angle [kind, frame, angle].',
        'bottles.<name>.rotation_pivot_*': '[frame, px, py]: instantaneous centre of rotation between frame and frame+1 in upright-art coordinates relative to the anchor (only pairs with >=2 deg rotation).',
        'bottles.<name>.pour_highpass_jitter_std': 'std of (value - 5-frame moving average) during the pour, px / deg: measures frame-to-frame noise (line boil) in the track.',
        'bottles.<name>.aniso_check': '[frame, sx_across, sy_along, rmse_at_track_pose, rmse_best] best anisotropic scale in {0.96..1.04}; (1,1) almost always = no squash/stretch.',
        'bottles.<name>.template': 'source frame of the template art, base (empty) frame, residual tilt of the bottle in the source frame (the art was derotated by it), body-centroid position relative to the anchor in upright art.',
        'streams.<name>.frames.<frame>.stream': 'attached (bool: band starts at the mouth), length (px along centre line), raw_extension_px (part traced on raw ink edges below the new-pixel band, i.e. inside liquid/over ice), band_end [x,y] (end of the new-pixel band = where the stream meets the liquid surface or an ice cube), pts = 12 points from mouth (or detached top) to end: [x, y, mask_width, outer_width, core_width, ink_thickness]; mask_width = width of the closed new-pixel band (approx.), outer_width = ink outer edge to outer edge from the raw cross-section, core_width = fill between the two ink lines, ink_thickness = mean of both sides; the 3 last are null at the two end points or where the profile was ambiguous.',
        'streams.<name>.frames.<frame>.drops': '[x, y, radius, colour_hex, kind, score]; kind drop = solid dark dot (campari/vermouth: distance-transform peak, radius = DT+0.5, score = DT), bubble = small ink ring (gin: ring correlation, score = NCC). Only within 75 px of the stream surface entry and not lower than 8 px below it.',
        'streams.<name>.cross_section': 'medians over all measured cross-sections: outer/core width, ink thickness, ink/fill/highlight colour; highlight_pos_in_core = position of the brightest core pixel measured from the screen-right ink line toward the screen-left one (0..1).',
        'art.<name>': 'upright-art measurements, origin = anchor (mouth tip), +y toward the base. width_profile_every_2px = [y, x_left, x_right] of the silhouette outer edge (includes the fill that sticks out left of the outline); outline_polygon = simplified outer contour; probe = direct pixel reads: label_outer_box (ink border included), body_ink_outer_x (outer edge of the outline ink on body rows), body_fill_x (fill colour extent on the same rows).',
    }
    data = dict(schema=schema, source='01_레퍼런스/original.mp4 (1080x1080, 30 fps)', scripts='scripts/v4/bottle_track.py, bottle_stream.py, bottle_art.py, bottle_overlay.py, bottle_data.py',
                same_choreography_check=comp, bottles=bottles, streams=streams, art=art)
    (OUT / 'data.json').write_text(json.dumps(data, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o)))
    # console summary for the README
    print(json.dumps(comp))
    for n in bottles:
        b = bottles[n]; c = b['choreography']
        print(n, {k: c[k] for k in c if k != 'pour_extrema'})
        print('  extrema', c['pour_extrema'])
        print('  pivot in', b['rotation_pivot_tilt_in']); print('  pivot out', b['rotation_pivot_tilt_out'])
        print('  jitter', b['pour_highpass_jitter_std'], 'template', b['template'])
    for n in streams:
        s = streams[n]; print(n, {k: s[k] for k in ('first_frame', 'last_frame', 'attached_frames', 'detached_frames', 'start_point_from_anchor_upright_median', 'cross_section', 'droplets')})
        print('  len', list(s['length_px_by_frame'].items())[:10], list(s['length_px_by_frame'].items())[-8:])
        se = [v for v in s['surface_entry_y_by_frame'].values() if v]
        print('  entry y', [round(v) for v in se[::5]])
    for n in art: print(n, art[n]['probe'], art[n]['total_length'], art[n].get('silhouette_iou_vs_gin'))


if __name__ == '__main__':
    main()
