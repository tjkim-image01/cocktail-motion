# Bottles + pour streams — frame measurement (V4)

Source: `01_레퍼런스/original.mp4` (1080×1080, 30 fps). Frame = 0-based sequential `cv2.VideoCapture` read, t = frame/30.
All numbers are pixels in the 1080 frame (y down) unless stated. Full per-frame data: `data.json` (has a `schema` key).

## Pose convention (use this to draw)

- **anchor** = mouth tip = centre of the top edge of the lip ring (upright art origin).
- **angle** = long-axis angle in degrees, 0 = upright neck up, **positive = clockwise on screen**.
- An upright-art point `p` (x right, y down, origin = anchor, body toward +y) is drawn at `anchor + scale·R(angle)·p`, `R = [[cos,-sin],[sin,cos]]`.
- `track` rows: `[frame, anchor_x, anchor_y, angle, scale, rmse, visible_fraction, centre_x, centre_y]`. centre = body centroid = anchor + R(angle)·(≈1, 163) (gin; campari −1.5,162; vermouth −1,162).
- scale is **1.00 in every frame** (anisotropic check sx,sy ∈ 0.96…1.04 returned 1/1 in 181 of 186 tested frames, the other 5 differ by 2% with no pattern): **no squash/stretch, no wobble — purely rigid**.

## Choreography (all three bottles are the same animation shifted by exactly 150 frames)

Same-choreography check (gin vs campari at +150 / vermouth at +300): median |Δx|,|Δy|,|Δangle| = 1.8, 3.7 px, 1.3° / 1.2, 2.0 px, 0.6°, max 5.4, 11.9 px, 3.0° (max values come from the fast frames). Use each bottle's own track.

| phase | gin | campari | vermouth | what happens |
|---|---|---|---|---|
| first visible | 189 | 339 | 489 | already upright-ish, half outside the **left edge** (visible 21%) |
| slide in | 189–202 | 339–352 | 489–502 | centre x −24 → 107 (ease-out: +25,+21,+18,+15,+13,+11,+10,+7,+5,+4,+2.5,+1.5 px/frame), centre y 335 → 325.6, angle −3.5° → +0.3° (top trails, straightens) |
| hold | 202–203 | 352–353 | 502–503 | |
| tilt in | 203–217 | 353–367 | 503–517 | rotates **about the body centre** (measured pivot (1…4, 161…165) in art coords = centroid); centre stays at ≈(107–109, 325→323). angle 0.9, 2.3, 5.3, 10.1, 17.3, 27.2, 40.5, 57.5, 74.6, 88.0, 98.2, 105.9, 111.0, 114.2, 116.1 (ease-in-out, peak 17°/frame at 210) |
| pour | 217–296 | 367–446 | 517–596 | angle rocks sinusoidally 114.6° ↔ 117.6° (mean ≈116°): maxima 222/249/276, minima 236/263/289 (gin) → **period 26.7 frames (0.89 s), amplitude ±1.5°**; centre drifts y 323 → 320. mouth tip moves x 253.7–257.6, y 387.4–398.6 with the rock |
| tilt out | 296–308 | 446–458 | 596–608 | about the centre again, faster: 115.2, 112.7, 107.9, 99.7, 87.3, 69.8, 48.0, 30.4, 17.9, 9.4, 4.2, 1.6, 0.6 (peak 22°/frame) — ends upright at x≈107, y≈159 (anchor) |
| hold | 308–311 | 458–461 | 608–611 | angle ≈0.4° |
| slide out | 311–317 | 461–467 | 611–617 | ease-in to the left: centre x 107 → 101 → 92 → 78 → 57 → 28 → (anchor −11), y 322 → 328, angle constant 0.4° |
| last visible | 317 | 467 | 617 | 35% visible; 318/468/618 nothing |

No fade, no motion blur, no smear lines, no shake marks around the bottle in any frame (residual check + overlays). Track high-pass noise during the pour is σ 0.35 px x, 0.75 px y, 0.29° — this is the line boil, keep or smooth as you like.

## Bottle art (upright, origin = anchor/mouth tip, +y toward the base)

All three bottles share **one silhouette** (IoU vs gin 0.93/0.95 after aligning tips; the differences are boil). Total length **273–275 px**.

Width profile (outer silhouette edge, x_left..x_right; full table every 2 px in `art.<name>.width_profile_every_2px`, simplified contour in `outline_polygon`):

| y | 0–15 | 16–20 | 20–72 | 72–100 | 100–112 | 112–120 | 120–262 | 262–273 |
|---|---|---|---|---|---|---|---|---|
| part | lip ring | notch under ring | neck | neck flare | shoulder (fast) | shoulder end | body | rounded base |
| x range | −17..+19 (≈37 wide) | −14..+15 (≈30) | −16..+16 (≈32) | widening to −25..+26 | −25 → −37..+41 | → −43..+44 | −44..+45 (≈90) | corners r≈10 |

- **Outline ink**: 2 px, near-black, tinted per bottle: gin `#282d33`, campari `#382926`, vermouth `#3f2328`. Outer ink edges on body rows x = −40/−42..+41/+44.
- **Fill is printed off-register**: the colour fill is the outline shape shifted ≈4 px to the **left** (upright art): it pokes ≈3 px out past the left outline and leaves a 4–6 px paper-coloured gap inside the right outline (body fill x −44/−45..+35/+36 on campari/vermouth vs ink −42..+41).
- **Fill colours** (body = neck): gin `#cae5eb`, campari `#c81c2e`, vermouth `#591924`. Colour clusters (k-means) in `art.<name>.colour_clusters`.
- **Highlight stripe**: vertical rounded bar on the left body, centre x ≈ −29.5, width ≈4–6 px, y ≈124 → 255 (hidden behind the label 156–231). campari `#f4a4a5`, vermouth `#c8aaaa`, gin almost white (`#e7f8ff`, low contrast — not detected automatically).
- **Label** (cream rectangle, 2 px ink border, small corner radius ≈4, axis-aligned within ±1°): outer box gin x −33..38, y 156..231; campari −37..35, 155..230; vermouth −35..34, 156..230 → **≈72×76 px, centre ≈(0±3, 193)**. Paper colour gin `#fbfbf7`, campari `#f4eee0`, vermouth `#ede1c3` (cream).
- **Label text** (upright in the art, rotates with the bottle): line 1 bold display caps centred, cap height ≈20 px, y ≈178–199: `GIN` navy `#2e3543`, `CAMPARI` red `#a71f33`, `ROSSO` dark maroon `#581a18`. Line 2 hand-lettered lowercase, y ≈204–218: `london dry` grey `#3a3f4a`–`#585d61`, `bitter` `#9e454e`, `vermouth` `#553221`. (Text boxes are approximate; see crops.)
- No liquid level is drawn inside the bottles; the bottle look does not change while pouring.
- Crops: `art-<name>-upright-x4.png` (4× nearest-neighbour, derotated by the source tilt 0.20–0.30°), `art-<name>-spec.png` (4× with outline polygon, tip, lip/shoulder lines, label/text boxes, y ruler every 20 px), `art-<name>-upright-raw.png` (1×, 340 px canvas, centroid at 170,170).

## Pour stream

| | gin | campari | vermouth |
|---|---|---|---|
| first frame (blob at mouth) | 217 | 367 | 517 |
| head reaches surface/ice | 224 | 374 | 524 |
| last attached to mouth | 293 | 443 | 593 |
| detached tail falls | 294–298 | 444–448 | 594–598 |
| outer width (ink edge to edge) median / p10–p90 | 12.5 / 12.2–12.75 | 12.5 / 12.0–12.75 | 12.5 / 12.0–12.75 |
| core (fill) width | 8.5 | 9.5 | 7.25 |
| ink thickness each side | 1.9 | 1.5 | 2.6 (dark fill blends into ink) |
| ink / fill / highlight | `#384247` / `#deebef` / `#e6f2f7` | `#4b2e32` / `#d9344a` / `#f98189` | `#4c262f` / `#7b2436` / `#c27786` |

- **Constant width** along the whole stream (no taper) — a 12–13 px band = 2 px ink + ~8.5 px fill + 2 px ink, with a thin highlight line inside the core ≈30% from the screen-left ink.
- **Start**: emerges at upright-art point ≈(2, −9) from the anchor (just beyond the lip, slightly right of the axis), leaves along the bottle axis and bends down into a near-vertical fall (polyline per frame). Growth from the mouth, head accelerates: length 14, 37, 74, 121, 178, 243, 319 px (gin 217–223, ≈gravity, +10 px/frame²); rounded head.
- **Steady pour**: polyline from mouth to the liquid surface; `band_end` y (stream enters liquid) rises with the fill: gin ≈749 → 684, campari ≈690 → 625, vermouth ≈590 → 535 (noisy ±25 px where the stream ends on an ice cube instead of the liquid). Inside red liquid the stream stays visible for a short distance (traced on its ink edges: `raw_extension_px`).
- **End**: 3 frames before the bottle starts tilting back the stream detaches at the mouth; its top falls (campari top y 423, 449, 481, 512, 553) while the bottom stays at the surface; gone at 299/449/599.
- Per frame in `streams.<name>.frames.<f>.stream.pts`: 12 points `[x, y, mask_width, outer_width, core_width, ink]`.
- **Droplets**: campari/vermouth draw **solid dark-red dots** (median colour campari `#a52b49`, vermouth `#641e32`), radius median 3.5 px (p10–p90 2.5–4.5 / 2.5–5.5), typically 2–6 per frame clustered within ±35 px horizontally and 0–35 px **above** the stream's surface entry, many touching the stream; present 374–449 and 524–599. Only ~45% reappear within 3 px in the next frame → they are redrawn/jump almost every frame (not simulated particles). Gin instead shows tiny **ink-ring bubbles** (r ≈3.5) beside the stream just above the surface (270–296); `drops` rows `[x, y, r, colour, kind, score]`.

## Verification images

- `overlay-<name>-sheet.jpg` — every 2nd frame of the whole bottle window: tracked outline (magenta), axis (green), anchor (red dot), stream polyline (orange attached / blue detached) with width ticks, droplets (green circle) / bubbles (cyan).
- `overlay-<name>-closeup.jpg` — 1:1 crops of entry/tilt/pour/return/exit frames with the tracked outline.
- `overlay-<name>-stream.jpg` — 12 frames across the pour, glass region at 0.6×.

## Uncertainties

- Bottle track: masked colour template match, fully rigid; RMS residual 30–38 (0–255) mostly from the line boil; outline sits on the ink within ~1 px in the close-ups, including half-off-screen frames (189–191, 316–317). Anchor x is the template's top-row centre: ≈1.5 px right of the neck centre line for campari/vermouth (0 for gin).
- Stream polyline: the centre line can step 1–3 px where it crosses the glass rim or ice edges (5-tap smoothing applied); a few frames end early on an ice cube (e.g. gin 224 length 262 vs 356 next frame). `outer/core/ink` widths from raw cross-sections are reliable (±0.5 px); `mask_width` is only approximate.
- Droplets: estimated recall ~70–80% (dots fused into the stream or into each other are partly missed) and some false dots on ice/liquid edges near the surface; gin bubble recall is low (rings touching the stream). Treat counts per frame as approximate, positions/radii of detected ones as accurate to ~1 px.
- Label/text boxes are approximate (±2 px); the text itself should be re-lettered, not traced. The blue/orange boxes in `art-*-spec.png` and `art.<name>.label` come from an automatic pass that mis-grows on the pale gin label; the authoritative label box is `art.<name>.probe.label_outer_box` (values in the table above).

## Scripts (`scripts/v4/`)

`bottle_track.py` (templates + rigid track + aniso check) → `bottle_stream.py` (streams, droplets) → `bottle_art.py` (art crops and measurements) → `bottle_overlay.py` (sheets) → `bottle_data.py` (data.json). Intermediate caches: `.cache-*.json/.npy` in this folder. Run each with `uv run -q --with opencv-python-headless --with numpy python scripts/v4/<script>.py`.
