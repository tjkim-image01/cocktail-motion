# Glass, liquid, ice, spoon, peel, rays — v4 frame measurements

Source: `01_레퍼런스/original.mp4` (1080×1080, 30 fps). Frame = 0-based sequential `cv2.VideoCapture` index, t = frame/30. Pixel coordinates, origin top-left, y down. Angles are clockwise-positive screen degrees.
Scripts: `scripts/v4/glass_*.py`. Run with `uv run -q --with opencv-python-headless --with numpy python scripts/v4/<script>` in this order: pose, ice, liquid, spoon, peel, rays, bubbles, art, merge.
Main output: `data.json`. Its `schema` key defines every row format. The `*_raw.json` files keep the unmerged values; `liquid_raw.json` also holds the per-column back and front arc y values.

Everything is drawn with hand-drawn line boil: holds of 3–4 frames, ±0.3–1 px on the glass and about ±1–2 px on the lines. All values below are raw measurements that still include this boil.

## 1. Glass pose (`glass.pose`, frames 100–899)
- The glass is static from frame 100 to 821: centre (352.2–352.8, 617.2–617.9), scale 0.996–1.004. All of that variation is boil, so the glass does not shake or bounce.
- **The finale grows the glass by 3.4 %.** Scale goes from 1.000 at frame 822 to 1.010 (829), 1.020 (835), 1.030 (840) and 1.034 (848). It then holds at 1.030–1.036 up to frame 899. The scale is about the glass centre (352.5, 617.5), because cy stays at 617.5–617.9.
- The peel (centroid 480.5,438.5 → 485.5,432.5), the liquid level (559 → 557.3) and the ice (scale 1.01 → 1.03–1.05) all follow this scale, so they belong to the same group. A good model is one group that scales about (352.5, 617.5) with an ease from frame 822 to 848.
- The scale is quantised to about 0.6 % steps because the template is resized to whole pixels.

## 2. Glass art (`glass.art`, frame 119 = empty glass, fully drawn; frames 100–110 are still drawing in)
- **Rim ellipse:** centre (353.3, 457.0), full width 285.9, full height 44.5. Back arc top y = 434.8, front arc y = 479.3. Spread over frames 110/114/118: ±0.8 px.
- **Sides** (centre line of the stroke):
  - left: x = 212.7 at y 495 → 232.2 at y 770
  - right: x = 491.8 at y 495 → 471.2 at y 770
  - Straight, residual 0.5 px.
- **Bottom outline:** parabola with vertex (353.1, 798.1). y = 786.8 at x 240 and 787.0 at x 465. The corners round into the sides at about y 780.
- **Inner bottom line:** grey `#8c9fa5`, x 240–463, y 745.6 at the ends and 756.1 at the centre (curved like a smile).
- **Outline:** core `#2f292c`, 2 px at max-channel < 110, about 3 px with antialiasing.
- **Fills:**
  - glass `#ddeff2` (same inside the rim ellipse)
  - base below the inner bottom line `#c3dfeb`
  - background `#faf9f5`
- **Highlight streaks:**
  - main left streak (234.7,506.9)–(257.3,692.8), 6.6 px wide, `#f0f9fe`
  - thin second streak (253.3,524.2)–(272.1,600.0), 2.7 px, `#e8f9fb`
  - thin light line along the inner right wall: (489,480)–(484,562) and (483,564)–(467,778), about 2.5 px, `#f0f6f6`
- The white left streak is drawn **in front of** the liquid in the red phases.
- Upscaled crop: `glass_f119_x3.png` (region x190–515, y420–815, ×3).

## 3. Liquid (`liquid.rows`, frames 180–899)
**Surface model.** The surface is an ellipse with x centre 349 and half-width a(y) = 122.5 − 0.075·(y−580). For example, a = 114.9 at the 682 level and 124.1 at the 559 level.
- Half-height b ≈ 16 px in every phase (phase medians 15.5–16.5). The per-frame b jitters ±2 px from boil.
- The back arc and the front arc are both drawn as lines.
- The band between them (the top face) is **lighter** than the body.
- Left and right midlines agree within ±1 px, so the surface does not tilt.
- Per-column residuals are 0.5–1.6 px (boil level), so there are **no measurable waves**.
- During the stir there are faint thin ripple arcs inside the band and body. They are not measured per frame; see `verify_liquid.jpg` frames 648–720.

**Body shape.** The body is a rounded box with dark red side and bottom edges (2–3 px; `#7b2233`/`#712133` in the red phase). Its bottom is at about y 757 at x 352. The body spans x 238–459 at y 740, inset from the glass wall.

**Level timeline:**

| Phase | Frames | Level (yc) | Body | Band (top face) |
|---|---|---|---|---|
| Empty | to 227 | no liquid | — | — |
| Gin, rising | 228 → ~285 | 743 → 682 (fast 249–274, about 2 px/frame) | `#d4ebf2`–`#d8ebf0`; back/front arcs grey `#849196`/`#98abaf` | `#e1eff3` |
| Gin, hold | 286–380 | 682 | `#d4ebf2` | `#e1eff3` |
| Campari, rising | 381 → ~440 | 682 → 620.5 (fast 396–420) | ramps `#d7dbe2` (384) → `#d6c1ca` (390) → `#d98d9b` (400) → `#d96876` (410) → `#da5867` (425) → `#da5665` (≥435) | final `#e67e8a` |
| Campari, hold | 445–528 | 620.5 | `#da5665` | `#e67e8a` |
| Vermouth, rising | ~530 → ~585 | 620.5 → 559 (fast 544–567) | ramps `#d35260` (540) → `#bd4252` (555) → `#a93b46` (570) → `#a63745` (≥585) | `#bd6873` |
| Stir overlay | 631–733 | 559 | `#a4333f` | `#ad4856` |
| After stir | 734–821 | 559 | `#a63745` | `#bd6771` |
| Finale | 822–848 | 559 → 557.3 (glass scale) | `#a63745` | `#bd6771` |

- The whole body changes colour at once while it rises; there is no layering.
- In the red phase the back-arc line is about `#51222c` and the front-arc line about `#862533`.
- The step between levels is exactly 61.5 px, and the levels 682 / 620.5 / 559 match the "1 oz / 2 oz / 3 oz" dashes to the right of the glass.
- **Stir overlay (631–733):** the body darkens, the band darkens, and the ice inside darkens from `#c48490` to `#b25461`. Ice outlines become soft dark red, so a translucent red layer is drawn over the ice and the spoon bowl. The overlay switches on and off on whole frames (631 and 734), with no fade.

**Ice colour.** Inside a cube (box shrunk to 55 %, `liquid.iceInsideColour`):

| Frame(s) | Ice colour | Note |
|---|---|---|
| 200 | `#eef7fb` | empty glass |
| 300 | `#e0f0f4` | submerged cubes in gin; ice3 sticks out above the gin and stays `#eef7fb` |
| 420 | `#e499a5` | |
| 600 | `#c48490` | |
| 660 | `#b25461` | stir |
| 740–880 | `#c48490` | |

This matches your mix(cube, liquid, 0.62) rule.

**Bubbles and drops** (`bubbles`, filtered to x 250–455, inside the glass):
- **Gin, 237–297:** hollow grey rings, r 2.5–7, `#5b686d`–`#a2b2b6`. They appear next to the stream entry point (about x 290–350) and rise from y about 718 (at 237) to about 648 (at 288), 1–3 per frame.
- **Campari, 375–445:** filled drops, r 1.5–6.7, `#9e2456`–`#ca2e50`. They sit just above the surface beside the stream (x 280–335), 1–6 per frame.
- **Vermouth, 525–595:** darker drops, `#5e1b34`–`#741431`, same layout.
- Drops below the surface cannot be seen (same colour as the liquid).
- Expect a few misses and false rings near ice edges. Check against `verify_bubbles.jpg`.

## 4. Ice cubes (`ice.tracks`, frames 180–899, columns frame,x,y,angle,scale,score)
- Tracking uses a black-hat line feature (it works in red liquid), rotated templates, and the analysis-01 angle convention. At frame 180 it matches analysis-01 within 0.6 px and 0.5°.
- **Gin:** the cubes do not move.
- **Campari (about 381–445):** small rise only. ice1 712 → 703.6, ice2 704 → 688.4, ice3 646.8 → 643.6.
- **Vermouth (547–570):** all three rise about 61.5 px, together with the level, to rest poses:
  - ice1 (295.8, 642.0, 18.5°)
  - ice2 (402.5, 627.0, −12.5°)
  - ice3 (351.0, 582.5, −54.5°)
- **Stir (631–733):** periodic shove with a **period of 24 frames (0.8 s)**, peaks at 662/686/710. Ranges:
  - ice1: x 275–311, y 638–649, angle 11–27°
  - ice2: x 388–418, y 623–631, angle −21 to −1°
  - ice3: x 336–366, y 578–586, angle −63 to −45.5°
  - Each cube runs a small orbit, phase-shifted from the others. At frame 734 they are back at the rest poses exactly.
- **Finale:** the cubes scale with the glass (scale 1.02–1.05 by frame 899).
- Scores are 0.45–0.7 normally and 0.3–0.4 during the stir (blurred overlay, spoon crossing). Frames with score < 0.4 are listed in the merge output (stir frames only) and were checked in `verify_ice_stir.jpg`: the boxes follow the cubes.

## 5. Bar spoon (`spoon.rows`, frames 631–733)
**Art (frame 640):**
- Ball top: diameter 22 px including the outline, fill `#bcbdc3`, outline `#252322` about 2 px.
- Shaft: 7 px wide in total (light fill `#bebcc2` about 3 px plus a dark outline each side), with small diagonal tick marks along it (a twisted shaft).
- Bowl: oval about 17×28 px, centred on the shaft line.
- Ball centre to bowl centre: L = 325.8 px (median; hand check at frame 640 gives 326.6). Total length is about 351 px.

**Layering:**
- The spoon is in front of the title and the glass rim.
- Below the surface the shaft and bowl are covered by the liquid tint. The bowl shows as `#ac6d77` in the stir overlay.

**Motion:**
- **Entry:** the spoon cuts in at 631 with the ball off-screen (ball y about −21, bowl y 304), then drops fast:

  | Frame | Ball y |
  |---|---|
  | 632 | 54 |
  | 633 | 119 |
  | 634 | 173 |
  | 635 | 219 |
  | 636 | 256 |
  | 637 | 286 |
  | 638 | 309 |
  | 639 | 326 |
  | 640 | 339 |
  | 642 | 353 |
  | 643–721 | 355–357 (rest) |

  Angle is about 4° during the drop.
- **Stir:** the ball rests at y about 356. x swings 358–391 while the angle oscillates between −2.5° and +11.1°. Period 24 frames, maxima at 672/696/720, minima at 684/708. The bowl moves x 298–405, y 674–681.
- **Exit:**

  | Frame | Ball y |
  |---|---|
  | 722 | 349 |
  | 723 | 335 |
  | 724 | 308 |
  | 725 | 262 |
  | 726 | 193 |
  | 727 | 100 |
  | 728 | 18 |
  | 729 | −38 |
  | 730 | −76 |
  | 731 | −96 |
  | 732 | −106 (bowl 220) |
  | 733 | −109 (bowl 217) |

  The spoon is gone at frame 734, a hard cut.
- `ballFrom = 'bowl'` marks frames where the ball was derived from the bowl end. For 732–733 the bowl y was measured separately (lowest spoon pixel − 14).

## 6. Orange peel and spritz (`peel`, frames 739–899)
**Art (frame 830, rest pose):**
- Shape: an open spiral with 2 loops and 2 tails. The contour polygon in `peel.art.contours` uses even-odd fill and holds one eye hole; the second eye merged during closing, so redraw it from the crop.
- Tube width: about 25 px including the outline; orange core about 14 px.
- Colours: fill `#fbb754`, speckles `#c27c1e`, outline `#422818` about 2.5–3 px.
- At rest, loop eyes are at about (463,418) and (530,425); tails end at about (388,418) and (575,465).
- The peel is drawn in front of the glass rim. Finale rays pass behind it.
- Crops: `peel_rest_x3.png`, and every frame in `peel_frames.jpg`.

**Pose** is relative to the frame-830 shape (x, y, angle, sx, sy, score):

| Frames | What happens | Pose values |
|---|---|---|
| 739–749 | Scale pop-in with overshoot | scale 0.5 (739), 0.7 (741), 0.9 (743), 1.10 (745), 1.05 (747), 1.0 (749); centre (371,379); angle about −21° |
| 751–767 | Twist / wring: x-squash, so a squash in sx plus rotation reproduces the twist | sx 0.94 (751) → 0.72 (759) → 1.0 (767); angle swings −15° → −29.5° (759) → −16°; score ≥ 0.94 |
| 769–775 | Falls onto the rim | y 384 → 433, angle → −4.5° |
| 775–785 | Slides right | x 400 → 480 |
| 787–821 | Rests | (480.5, 438.5), angle 0, scale 1.0 |
| 829–848 | Grows with the glass | ends at (485.5, 432.5), scale 1.03 |

**Spritz dots** (`peel.spritz`, frames 754–771): pale orange dots.
- Size and colour: r 1–10 (most are 1.5–4), median colours `#ecc270`–`#e1d4a8`, paler and more transparent as they fall.
- Count: 1 dot at 754, rising to 7–10 at 757–760 and 12–15 at 761–770, then 5 at 771 and gone at 772.
- Path: they fall from under the loops (x 313–436, starting y about 407) down to the rim and into the glass mouth (y up to 479).

## 7. Finale rays (`rays`, 7 rays, frames 814–899)
Rays appear staggered and fade in over about 10 frames (saturation 27 → about 110 by 824–830). Each ray then **slides and pulses along its own radial direction**, length 24 ↔ 40 px, period about 33 frames, with a different phase per ray. They never disappear before frame 899.

| id | Colour (core) | First frame | Midpoint | Width |
|---|---|---|---|---|
| 0 | orange `#eba231` | 814 | (297, 405) | 6.6 |
| 1 | orange `#e6a531` | 814 | (134, 606) | 6.0 |
| 2 | orange `#eca235` | 815 | (550, 507) | 6.7 |
| 3 | pink `#e26982` | 816 | (180, 478) | 5.5 |
| 4 | pink `#ec6c8a` | 817 | (442, 413) | 4.7 |
| 5 | pink `#ee6978` | 817 | (568, 643) | 5.6 |
| 6 | pink `#e16b7e` | 821 | (145, 671) | 5.5 |

Widths include the antialias, so the solid stroke is about 4–5 px. Ray 4 is partly behind the peel. The oz-label dashes and text (x 495–560) also change slightly in the finale; they were excluded and are not measured here.

## Verification images (this folder)
- `verify_glass_pose.jpg`: rim, sides and bottom of the frame-119 glass, posed per frame.
- `verify_liquid.jpg`: fitted surface ellipse every 12 frames.
- `verify_ice_all.jpg`, `verify_ice_stir.jpg`: ice boxes, highlight corner and score.
- `verify_spoon.jpg`: ball, shaft and bowl, frames 630–735.
- `verify_peel.jpg`: posed peel contour and spritz dots. `peel_frames.jpg` has the raw crops.
- `verify_rays.jpg`: ray segments with ids.
- `verify_bubbles.jpg`: gin rings and Campari/vermouth drops.

## Uncertainties
- **Liquid b:** ±2 px per frame (boil). Use the per-phase median of 16.
- **Liquid colours:** medians. The 381–440 and 530–585 colour ramps are per frame in `liquid.rows`.
- **Ice during the stir:** ±2 px and ±2°. Cubes overlap each other and the spoon.
- **Spoon L:** the per-frame bowl estimate is noisy (std 14 px); L = 325.8 is used as rigid.
- **Peel 739–743:** the peel is very small; the scale values are approximate.
- **Bubbles and drops:** threshold detections. Expect some missed faint rings and a few false hits at cube edges.
- **Stir ripple arcs:** inside the liquid; seen but not measured.
