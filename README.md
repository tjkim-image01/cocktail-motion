# Cocktail — 손그림 레시피 모션그래픽

2026-10-29 사용자 요청으로 model3d의 Negroni 작업을 독립 작업공간으로 복사했다.

2026-10-31 전체 자료를 공개 GitHub 저장소와 Pages에 게시한다. [공유 비교 페이지](https://tjkim-image01.github.io/cocktail-motion/) · [전체 자료 목록](https://tjkim-image01.github.io/cocktail-motion/files.html) · [전체 ZIP](https://github.com/tjkim-image01/cocktail-motion/archive/refs/heads/main.zip). 원본·V1~V4·검수 자료·위키·lib를 포함하고, 가상환경과 실행 캐시는 제외한다. 배포 설정은 `publication.json`, 목록 재생성은 `python3 scripts/build_catalog.py`를 사용한다. 서버에 파일을 저장하는 일괄 캡처·H.264 출력은 로컬에서 실행한다.

- **작업 샘플:** [project/sample](project/sample/README.md) — 원본 영상, 생성 원화·프롬프트, V1~V4 소스·측정값·검수 사진·MP4·효과음
- **제작 위키:** [project/wiki](project/wiki/README.md) — 같은 스타일을 새 소재에 적용하는 방법
- **공용 코드:** [lib](lib/README-cocktail.md) — model3d의 lib 복사본

## 실행

```sh
cd /Users/jatu/app/cocktail
npm start
```

비교 페이지: http://127.0.0.1:4343/  
제작본 단독: http://127.0.0.1:4343/index.html

`플레이어 실행.command`를 더블클릭해도 된다. Node.js만 있으면 플레이어를 실행할 수 있고, Three.js·서체·영상·데이터는 이 폴더 안에서 읽는다.

## 분석 도구

분석 스크립트용 Python 환경은 `.venv/`, 패키지 목록은 `requirements-analysis.txt`다. 스크립트는 `project/sample`을 현재 작업 폴더로 실행한다.

```sh
cd /Users/jatu/app/cocktail/project/sample
../../.venv/bin/python scripts/v4/make_ui_v4.py
```

새 작품은 `project/c001`, `project/c002`처럼 별도 폴더에서 진행한다. [새 작품 시작 문서](project/wiki/새_작품_시작.md)를 먼저 읽는다. `sample`은 비교 가능한 기준으로 보존한다.

## 복사 기록

원본: `/Users/jatu/app/model3d/project-threejs/tree002`, `/Users/jatu/app/model3d/lib`. 원본 파일은 보존했다. 캐시(`__pycache__`, `*.pyc`)와 Finder 메타데이터(`.DS_Store`)는 제외했다. 원본과의 파일 체크섬 확인 및 경로 수정 내역은 `migration.json`에 기록한다. 10월 29일에는 로컬 이관만 했고, 10월 31일 사용자 요청으로 별도 공개 저장소와 Pages를 구성한다.
