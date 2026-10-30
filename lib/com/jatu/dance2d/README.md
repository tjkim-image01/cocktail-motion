# dance2d — 회화풍 원화를 실제 안무대로 춤추게 하는 2D 파이프라인

M004 봉식이 춤(v5-test8 → test9 → complete-1)에서 검증한 방법을 재사용할 수 있게 묶었다. 왜 이 방식인지는 [project/m004/README-dance2d.md](../../../../project/m004/README-dance2d.md)를 본다.

```
lib/com/jatu/dance2d/
  dance.py        extract / choreo / autorig / cut  (Python, MediaPipe)
  web/figure.js   부위 원화 → Three.js 메시, 마디 블렌딩으로 팔·다리를 텍스처째 휨
  web/choreo.js   motion.json을 곡 시간으로 읽기, 플래시 2컷·스쿼시·점프
```

## 준비

- Python 3.12 가상환경: `/Users/jatu/.venvs/pose` (mediapipe, opencv-python, numpy). 다시 만들 때:
  `uv venv --python 3.12 ~/.venvs/pose && VIRTUAL_ENV=~/.venvs/pose uv pip install mediapipe opencv-python numpy`
- ffmpeg, (안무 영상 내려받기) yt-dlp
- MediaPipe 모델은 처음 실행할 때 `~/.cache/dance2d/`에 자동으로 받는다.
- 모든 명령은 저장소 루트(`/Users/jatu/app/model3d`)에서 `-m lib.com.jatu.dance2d.dance`로 실행한다.

```sh
PY=/Users/jatu/.venvs/pose/bin/python
```

## 새 캐릭터를 춤추게 하는 순서

### 1) 원화 (이미지 생성)

정면 중립 전신, 1024×1536, **투명 배경**. 생성 프롬프트에 꼭 넣을 조건은 다음과 같다.

- 팔이 몸에서 살짝 떨어져 있고 **팔·손과 몸통 사이에 투명한 빈틈**이 있다.
- **두 다리 사이**에도 빈틈이 있다. 발바닥은 한 기준선에 놓인다.
- 소품, 글자, 그림자, 배경이 없다.

예시 프롬프트: `project/m004/complete-1/assets/cast/prompt-*.txt`. Codex CLI로 생성하는 경우, ChatGPT 계정에서는 기본 모델이 거절될 수 있으므로 모델을 지정한다.

```sh
codex exec -m gpt-5.6-sol --skip-git-repo-check -s workspace-write -C <작업폴더> -i <화풍참고.png> -i <정체성참고.png> - < prompt.txt
```

### 2) 부위 나누기

```sh
$PY -m lib.com.jatu.dance2d.dance autorig art.png -o rig/name.json     # 초안 + rig/name.png 검수 그림
# rig/name.png를 보고 경계를 고친다(아래 체크리스트). 고친 spec으로:
$PY -m lib.com.jatu.dance2d.dance cut rig/name.json -o assets/name      # 부위 PNG + parts.json + parts-map.png
```

`autorig`는 사람형에 맞춘 **초안**이다. 다음을 반드시 손으로 확인한다. 강아지처럼 관절 인식이 안 되는 경우는 spec을 직접 쓴다(예: `complete-1/scripts/build_rigs.py`의 복실이).

- 팔/몸통 경계가 **소매와 몸판 사이**를 지나는가(몸통 쪽에 소매가 남으면 소매 자국이 생긴다).
- 어깨 윗부분(y가 어깨점보다 위)이 몸통에 있는가.
- 다리 영역이 **바지 바깥선**을 따라 손가락보다 아래에서 시작하는가.
- 머리 경계가 스카프나 넥타이를 가르지 않는가. 가르면 통째로 몸통에 넣는다.
- 마디점(`centers`)이 소매·바지 폭의 가운데를 지나는가.

spec 형식(요점):

```json
{"image": "...png", "floor": 1478, "centerX": 512, "kind": "biped",
 "order": ["shoe.L","shoe.R","leg.L","leg.R","pelvis","torso","head","arm.L","arm.R"],
 "regions": {"arm.L": [[x,y], ...], ...},
 "centers": {"arm.L": [어깨위, 어깨, 팔꿈치, 손목, 손끝], "leg.L": [골반위, 골반, 무릎, 발목, 바짓단], ...},
 "pivots": {"head": [x,y], "torso": [x,y], "pelvis": [x,y], "shoe.L": [x,y], "shoe.R": [x,y]},
 "feather": {"pelvis": 34},
 "extras": {"tail": {"pivot": [x,y], "wag": 0.35}}}
```

L/R은 **화면 왼쪽/오른쪽**이다(거울모드 안무와 그대로 맞는다).

### 3) 안무

```sh
yt-dlp -f "bv*[height<=720][ext=mp4]+ba[ext=m4a]" -o dance.mp4 <정면 고정 카메라 안무 영상>
$PY -m lib.com.jatu.dance2d.dance extract dance.mp4 --crop 400 880 -o pose-raw.json   # 여러 명이면 한 명만 남게 가로 범위
$PY -m lib.com.jatu.dance2d.dance choreo pose-raw.json --score music/score.json --beats 144 --window 16 --amplify 1.2 -o motion.json
```

`--score`는 목표 곡의 `beatPeriod`가 든 json이다(v5 `music/score.json` 형식). 구간을 직접 정하려면 `--plan plan.json`을 쓴다.

```json
[{"start_beat": 103, "beats": 16, "mirror": false, "amplify": 1.25},
 {"start_seconds": 34.6, "beats": 16, "mirror": true},
 {"auto": 0, "beats": 16}]
```

캐릭터마다 다른 plan으로 서로 다른 춤을 만들고, 마지막 구간을 같게 해 군무로 끝내는 예시는 `complete-1/scripts/build_dance.py`에 있다. 출력의 `firstBeat`에 곡의 첫 박 시각을 넣어 두면 `choreo.js`가 곡 시간에 맞춘다.

### 4) 브라우저에서 재생

`web/figure.js`, `web/choreo.js`를 프로젝트 폴더로 복사한다(4334 서버는 m004 폴더만 제공한다).

```js
import {createFigure} from './figure.js';
import {createChoreo} from './choreo.js';
const figure=await createFigure(await (await fetch('assets/name/parts.json')).json(),'assets/name/');
figure.group.scale.setScalar(키_무대단위/figure.height);figure.setOrder(1000);scene.add(figure.group);
const choreo=createChoreo(await (await fetch('motion.json')).json(),{hopEvery:8});
// 매 프레임: 2컷으로 붙잡은 시각의 자세를 놓는다.
figure.update(choreo.poseAt(choreo.drawingTime(audio.currentTime,'twos')));
```

`figure.update`는 `{rootz, joints}`를 돌려준다. 그림자나 카메라를 따라가게 할 때 쓴다.

## 함수 (Python)

- `extract(video, crop=None)` → `{bpm, beatPeriod, firstBeat, frames:[{t, lm:[[x,y,vis]×33]}]}`
- `beats_from_audio(path)` → `(박 간격, 첫 박)`
- `Source(raw)`: `.best_windows(count, beats)`, `.segment(start_beat, beats)`
- `choreo(raw, plan, beat_period)` → motion(`format: dance2d/angles-v1`)
- `mirror_frame(f)`, `amplify_frame(f, k)`
- `autorig(image)` → spec 초안, `cut(spec, out_dir)` → parts.json, `preview(spec, path)`
