# tree002 v4 — UI layer measurement (card, headline, progress, timeline, oz scale)

Source `01_레퍼런스/original.mp4` (1080², 30 fps, 900 frames). Frame i = 0-based sequential read, t = i/30.
Pixels, origin top-left, y down, angles in degrees with **+ = clockwise on screen**.
Every frame 0–899 was measured. Values below are measurements. Fitted curves are labelled as fits.
Line boil: static UI jitters 0.1–0.35 px (σ) every 3.75 frames, so ±1 px differences between frames are boil, not motion.

Scripts (in `scripts/v4/`, run with `uv run -q --with opencv-python-headless --with numpy python <script>`):
`ui_common.py` (frame reader + crop sheets), `ui_card.py`, `ui_headline.py`, `ui_text.py`, `ui_progress.py`, `ui_counter.py`
(segmentation only; the strings were read by eye), `ui_timeline.py`, `ui_oz.py`, `ui_misc.py`, `ui_build.py` (→ `data.json`), `ui_verify.py` (→ `verify_*.jpg`).
`_*.json` are the raw passes. `_med_step1..7.png` are median rest crops of the card, origin (640,505).

## 1. Event table (frame numbers)

| frame | event |
|---|---|
| 88–98 | title "NEGRONI" slides up to its rest position (red bbox at rest: x348–728, y92–156) |
| 101–111 | subtitle "equal parts · stirred · on the rocks" fades in (darkest gray 190→95) and rises 6 px (bbox top y187→181, rest bbox 341,181,398×31) |
| 115–129 | timeline fades in: all 6 nodes, labels and grey lines together, linear over about 15 frames. Radius goes 22→23 px. Node 1 fades in already in the *current* style |
| **108** | card 1 entry, frame N (headline "FILL" alone) |
| 143 / 153 / 164 | counter 1/3, 2/3, 3/3. Progress fill jumps 0→78→155→233 px at once (no tween) |
| 166 | node 1 done. Segment 1→2 fill runs 166–178 |
| **180** | card 2 (GIN). Node 2 current |
| 212 | "1 oz" grey label and dashed line appear (pulsing) |
| 221 | progress pill appears at 12 px. It grows 240→285 |
| 238–279 | counter 0.1 … 1.0 / 1 oz |
| 288 | 1 oz reached: grey label and dash vanish, red label pops 296–300 |
| 298 | node 2 done. Segment 2→3 fill runs 298–310 |
| **330** | card 3 (CAMPARI). Node 3 current |
| 361 | "2 oz" grey label and dash appear |
| 371 / 390–436 | progress pill 12 px / grows |
| 438 | 2 oz reached. Red pop 446–450 |
| 448 | node 3 done |
| **480** | card 4 (SWEET VERMOUTH). Node 4 current |
| 514 | "3 oz" grey label and dash appear |
| 521 / 540–589 | progress pill 12 px / grows |
| 588 | 3 oz reached. Red pop 596–600 |
| 598 | node 4 done |
| **630** | card 5 (STIR). Node 5 current |
| 643 / 648–723 | progress pill 10 px / linear grow, about 2.9 px per frame |
| 647–722 | counter 19 s … 1 s, one step every 4 frames. 723 is "0 s" |
| 727 | node 5 done |
| **735** | card 6 (ORANGE PEEL). Node 6 current |
| 745 / 747–786 | progress pill / linear grow, about 5.6 px per frame |
| 786 | counter "twist…" → "done!" |
| 787 | node 6 done (last segment 5→6 filled at 727–739) |
| **810** | final card ("THAT'S A NEGRONI / CIN CIN!"). It has no progress bar. From about 815 the glass and the oz labels sway together, and orange/pink spark strokes appear around the glass (glass motion is measured by the glass agent) |

Card entry frames **N = 108, 180, 330, 480, 630, 735, 810** (t = 3.600, 6.000, 11.000, 16.000, 21.000, 24.500, 27.000 s).

## 2. Card choreography (identical at all 7 transitions)

- **Exit is a hard cut.** At N−1 the old card is fully at rest. At N the whole card is gone: body, border, shadow, all text and the old headline.
- **Frame N:** only the **new headline** is drawn. It is fully opaque (fill #E8737C, outline darkest gray 35–38, same as at rest). It uses the transform of frame k=0 below, so it looks smaller, tilted clockwise, and shifted up-right.
- **From N+1** the card is back, with the same transform. Its opacity is about 0.58 at N+1, 0.98 at N+2 and 1 from N+3. The headline stays opaque throughout.
- At N+1 the card body looks pink (249,240,237). This means the pink shadow rectangle is drawn under the semi-transparent body at a higher opacity than the card. Reproduce it as: shadow layer opacity 1 (or ≥ card), body/border/text at α.
- **Pivot = card centre (843.3, 636.3)**, for both the card and the headline. With this pivot, the headline offsets at N are reproduced to within 0.5 px: FILL dx +12.8 / dy −6.2, "1" +17.8/−8.3, "CIN CIN!" +6.8/−1.1.
- The centre does not translate (σ 0.15 px at rest; entry frames within ±0.3 px).

Entry profile (mean of 7 entries; scale = card size / rest size; rot = angle − rest angle):

| k = f−N | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scale | 0.902* | 0.9355 | 0.9641 | 0.9844 | 0.9985 | 1.0068 | 1.0110 | 1.0117 | 1.0101 | 1.0071 | 1.0038 | 1.0011 | 1.000 |
| rot ° | +4.64* | +2.93 | +1.63 | +0.69 | +0.12 | −0.26 | −0.47 | −0.51 | −0.49 | −0.36 | −0.19 | −0.07 | 0 |
| card α | 0 | 0.58 | 0.98 | 1 | 1 | … | | | | | | | |

\*k=0 values come from the headline, because the card is invisible. The per-entry scatter is σ ≤ 0.0008.

**Fit** (rms scale error 0.0005, rot error 0.03°):
`e = easeOutBack(u, c1=1.65)` with `u = (k + 0.5)/12.5`, where `easeOutBack(u) = 1 + (c1+1)(u−1)³ + c1(u−1)²` and u is clamped to [0,1].
`scale = 0.88 + 0.12·e` and `rot = 5.58°·(1 − e)`.
So the animation starts half a frame before N and lasts 12.5 frames (417 ms). Card opacity is roughly linear from 0 at k=−0.5 to 1 at k≈2.

**Rest geometry** (outer edge of the ink border, median of all rest frames):
- centre (843.34, 636.28), w 387.3, h 243.8, giving left 649.7, right 1037.0, top 514.4, bottom 758.2. Corner radius is about 14 px.
- **Rest rotation −0.69°** (counter-clockwise). The progress track shows the same tilt, so the whole card is rendered rotated about −0.7°.
- Border: #2C2A29, about 2.5 px, hand-drawn wobble.
- Body #FDFCF9 (253,252,249). Page background #FAF9F5 (250,249,245).
- Pink shadow #F3D3D4 (243,211,212) is a copy of the card rect offset about (+8, +8) with a soft edge of about 2–3 px. Its outer extent at rest is x 1046, y 769 (99.5 percentile).

Verification image: `verify_card_entry_178-194.jpg` (measured rotated card box in green, headline red bbox in magenta).

## 3. Headline (big red word)

- Font: chunky rounded all-caps display face. The closest Google font is **Luckiest Guy** (lowercase renders as caps: "1 oz" → "1 OZ", "20 sec" → "20 SEC"). This match is a judgement, not a measurement.
- Fill #E8737C (232,115,124). Dark maroon outline, darkest about #4B2A2B. A darker red extrusion (about #8A4E56, 3–4 px) sits down-left of the glyphs.
- Rest position, same for every step (red-fill bbox incl. extrusion): x0 670–674, top 584–586, baseline (bottom of dense ink) 636–637, cap height about 52 px.
- Width per word: FILL 124, 1 OZ 126, 20 SEC 216, 1 28, CIN CIN! 256 (final top 583, baseline 640).
- Per-frame values are in `headline.per_frame` (scale / rot / dx / dy / red_bbox, template score 0.93–0.99). During a step the headline does not pulse or move; only boil (±1 px) remains.

## 4. Card text, per state (median rest image)

Columns: top = top of dense ink, base = baseline row. Colours are the core-pixel cluster centre; thin anti-aliased text reads lighter than its CSS colour.

| state | small line (red, x 676) | headline | label (dark, x 678) | detail (grey, x 678–679) | counter |
|---|---|---|---|---|---|
| 1 (108–179) | STEP 1 OF 6 | FILL | ICE | big cubes · rocks glass | n / 3 |
| 2 (180–329) | STEP 2 OF 6 | 1 oz | GIN | London dry · 30 ml | x.x / 1 oz |
| 3 (330–479) | STEP 3 OF 6 | 1 oz | CAMPARI | the bitter one · 30 ml | x.x / 1 oz |
| 4 (480–629) | STEP 4 OF 6 | 1 oz | SWEET VERMOUTH | vermouth rosso · 30 ml | x.x / 1 oz |
| 5 (630–734) | STEP 5 OF 6 | 20 sec | STIR | until nice and cold | N s |
| 6 (735–809) | STEP 6 OF 6 | 1 | ORANGE PEEL | express the oils, drop it in | twist… / done! |
| final (810–) | THAT'S A NEGRONI | CIN CIN! | 1:1:1 | gin · Campari · sweet vermouth | (no bar) |

Row geometry (steps 1–6):

| row | top | base | height | colour |
|---|---|---|---|---|
| STEP line | 545 | 559 | caps about 14–15 px | core about (163,78,92), roughly #A34E5C (CSS colour probably about #B5485A) |
| headline | 584 | 636 | 52 | see §3 |
| label | 650–652 | 680–681 | caps 30 | #2A262C (42,38,44); same display font, no outline |
| detail | x-height top 700–701 | 710–711 | x-height about 10, ascenders from 694–695 | core #6F6B6B (111,107,107) |
| bar row | 725 (track) | counter text base about 741 | | counter text dark #302D2B |

Final card rows: "THAT'S A NEGRONI" top 544 / base 559, x 675–830. CIN CIN! 587/640. "1:1:1" 658/687 (height 30). Detail line top 711 / base 723 (ascenders from 705).

Small-text font: hand-printed sans similar to **Patrick Hand**. This is a judgement. The timeline labels use the same font (caps about 14 px, rows y970–986).

## 5. Progress bar

- **Track**: rounded pill outline, x 677.5→916 (outer), y 725.5→742 (outer, about 16 px tall), stroke about 2 px #2C2A29, end radius about 8. It is tilted about −0.5° with the card.
- **Fill**: red #EA747F (234,116,127). Left edge x 680. Full width 233–234 px (x 680→914), y about 728–740.
- **Fill per step** (`progress.per_frame.fill_w`):
  - Ice: instant jumps 78 / 155 / 233 at frames 143 / 153 / 164.
  - Gin, Campari, Vermouth: a 12 px minimum pill appears 19 frames before growth starts (221 / 371 / 521). Growth then follows an ease-in-out over about 45 frames (240→285, 390→436, 540→589). Peak growth is about 10 px per frame around the midpoint.
  - Stir: linear, 10 px at 643, then 648→723.
  - Peel: linear, 747→786.
- **Counter** (`progress.per_frame.counter`, read visually; `verify_counter_readings.jpg` shows every string segment):
  - 0 / 3 (109–142), 1 / 3 (143–152), 2 / 3 (153–163), 3 / 3 (164–179).
  - Gin: 0.0 / 1 oz 181–237, 0.1 238–245, 0.2 246–250, 0.3 251–253, 0.4 254–256, 0.5 257–259, 0.6 260–262, 0.7 263–265, 0.8 266–270, 0.9 271–278, 1.0 279–329.
  - Campari: 0.0 331–387, 0.1 388–395, 0.2 396–400, 0.3 401–403, 0.4 404–406, 0.5 407–409, 0.6 410–412, 0.7 413–415, 0.8 416–420, 0.9 421–428, 1.0 429–479.
  - Vermouth: 0.0 481–537, 0.1 538–545, 0.2 546–550, 0.3 551–553, 0.4 554–556, 0.5 557–559, 0.6 560–562, 0.7 563–565, 0.8 566–570, 0.9 571–578, 1.0 579–629.
  - Stir: 20 s 631–646, then 19 s … 1 s, each lasting 4 frames (19 s = 647–650 … 1 s = 719–722), 0 s 723–734.
  - Peel: twist… 736–785, done! 786–809.
  - The counter text is left-aligned at x about 928, with the same baseline as the bar.

## 6. Timeline (6 nodes)

**Geometry**
- Node centres x = 150 + 156k, y = 927. Labels ICE / GIN / CAMPARI / VERMOUTH / STIR / PEEL are centred under the nodes, rows y 970–986.
- Ring outer radius about 23.5 (incl. a 3 px stroke). The connecting line runs between nodes at y 925–928.
- Grey line #D1D0CC, about 3 px. Red line #E76F7C, about 4 px.

**States** (`timeline.per_frame.state`: 0 none, 1 empty, 2 current, 3 done)

| state | ring | number / mark | label colour |
|---|---|---|---|
| empty | grey #B4B1AD | grey number #96908D | grey #938F8C (147,144,140) |
| current | black #2E2C2C | red number about #B5485A | red (165–173, 67–74, 80–93), about #AB4A5A |
| done | black ring | red disc #E4757F (radius about 19–20, concentric within 1–2 px) plus a cream check | dark #2E2926 |

**Change frames**
- Current: 125 (fade-in), 180, 330, 480, 630, 735. Each switch is instant, on the card's frame N.
- Done: 166, 298, 448, 598, 727, 787.
- The label colour switches on the same frame as the node.

**Current-node pulse** (one global clock, independent of when the node became current). Sine fit over 527 frames, rms 0.23 px:
`radius = 23.64 + 1.41·sin(2π·f/31.44 + 0.078)` px, so P = 31.44 frames (1.048 s), first peak at frame 7.5, ring scale about ±6 %.
The number scales with the ring.

**Done pop** (same at all 6), radius at D+0…D+10:
25.0, 25.5–26, 27, 27.5, 27.5, 27, 26.5, 25.3, 24.5, 23.5, 23.5. That is a scale of about 1.17 peaking at D+3–4 and settling by D+8.

**Check mark draw-on** (white px inside the disc, `check_white_px`):
- D…D+4/5: only the short first stroke (about 60–79 px).
- At D+5 or D+6: the full check appears (about 135–157 px).
- It settles to about 110–117 px by D+8 as the pop shrinks.
- See `verify_timeline_done_node2.jpg`.

**Segment fill** (red line progressively drawn left→right; `seg_red_x1`)
- It starts on the node's done frame D. The front is hidden under the nodes before D+3 and after D+12.
- Measured front x − cx_left, identical for all 5 segments (±2 px):

  | D+ | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
  |---|---|---|---|---|---|---|---|---|---|
  | front, px | 37–41 | 45 | 55 | 70 | 87 | 102 | 113 | 120 | 123 |

- The curve is a symmetric ease-in-out, centre to centre (156 px), mid-point at about D+6.6, peak speed about 17 px per frame. It completes at about D+13 (0.43 s).
- A standard sine or cubic ease does not reproduce this shape. Replay the measured table.

## 7. Oz scale and dashed target line

**Levels** (tick and text left edge to the right of the glass wall)

| level | label rows | ink x range | red label width at rest |
|---|---|---|---|
| 1 oz | y674–690 (centre 682) | 486–557 | about 70 |
| 2 oz | 612–628 (620) | 489–564 | about 72 |
| 3 oz | 551–567 (559) | 492–568 | about 74–76 |

Each label is a short tick of about 28 px, a 6 px gap, then "n oz" in the hand font (digit height 16).

**Pending state (grey)**
- Appears at 212 (1 oz), 361 (2 oz), 514 (3 oz).
- The grey label (core #66655F at full opacity) and a **dashed line across the glass** at the same y pulse together.
- Opacity (`oz.N.grey_alpha_est`) oscillates between about 0.18 and 1.0 with a period of about 23–23.5 frames (0.78 s). Peaks: 219, 241, 264, 287 / 382, 406, 430 / 523, 547, 571.
- The peaks fit one global clock: peak ≈ 219.5 + 23.4·n.
- On appearance there is a short fade (3–6 frames) multiplied by the pulse.
- Dash geometry:
  - from x about 227 (inner left wall) to about 480–488 (right wall, joining the tick);
  - 3 px thick (rows yc−1…yc+1);
  - about 11 px dash, 9 px gap (period 19–20 px);
  - neutral dark grey, drawn over ice and liquid.

**Reached**
- At 288 / 438 / 588 the grey label and dash vanish in one frame.
- For about 8 frames only a 4 px red dot remains at the tick start.
- The red label (#B3505F core (179,81,95); fill reads (175–181, 81–84, 95–97)) then pops in, scaling from the tick's left end. Widths (1 oz): 6 (296), 56 (297), 66 (298), 70 (299), 72 (300), then 70 at rest. Level 2 overshoots to 77 at 450 and settles to 72 by 453.
- Labels stay red to the end. They move with the glass after about 815.
- See `verify_oz_completion.jpg`.

## 8. Verification images

- `verify_card_entry_178-194.jpg`: frame-by-frame card and headline entry with measured box, scale, rotation and alpha.
- `verify_overlay_frames.jpg`: frames 150/260/420/560/700/790/880 with card box, progress-fill box, node radius circles (green = current, blue = done) and red oz-label boxes.
- `verify_timeline_done_node2.jpg`: node-2 done pop, check draw-on and segment fill (frames 296–309).
- `verify_oz_completion.jpg`: 1 oz (284–300) and 3 oz (586–600) grey → dot → red pop.
- `verify_counter_readings.jpg`: every counter string segment with the reading assigned to it.

## 9. Uncertain / not measured

- Font identities (Luckiest Guy, Patrick Hand) are visual matches, not measured.
- CSS colours of thin text are estimated from anti-aliased cores.
- Card α at N+1 (0.58) comes from border darkness. The body pink tint suggests 0.6–0.7. Either way it is fully opaque by N+2–3.
- The −0.69° rest tilt could be a hand-drawn slant rather than a rotation. The track and border agree on it, so treat it as a rotation.
- The pending-label pulse may reset per level rather than run on a global clock. Its phases agree with a global 23.4-frame clock to within about 1–2 frames.
- Not measured here:
  - the end-of-video glass/label sway and spark strokes (from about 815);
  - title intro frames 0–88 (bboxes only, `misc.title_red_bbox`; see `analysis-01/title-observations.json`);
  - glass contents, bottles, spoon, peel and ice.
