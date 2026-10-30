# 수묵 제작 기준 v31

EP03 「옷을 두드리던 시간」 본문이 기준이다. 머리/얼굴 밑색→몸 채색→세선→다음 인물→물건→색별 배경. 한 획은 RGB 하나, 농담은 alpha만. 색 변경 .13초/배경 .2초 붓 들기. 4000×2608 작업화판/실제 경로 마스크/완성 팝 금지.

EP06에서 팔 옆 나무판 가로선이 인물 누끼에 섞이던 결함을 교정했다. 새 scene에는 `background_exclusions` 다각형 또는 `background_exclusion_mask` 경로(흰색=배경으로 남길 영역)를 명시한다. 원본과 실루엣을 비교하고 팔 바깥·팔 사이·다리 사이 배경선이 인물 단계에 나오지 않는지 확인한다. 마스크는 모든 인물/물건 안료에 우선 적용되며 검사기가 실제 PNG alpha를 확인한다. 새 그림마다 자신의 팔레트/장면 마스크를 작성한다.

표지1.5초 뒤 첫 프레임부터 붓과 첫 획이 나온다. 쓰기0~3.5초/전체4.15초/본문6초, 총66초 본편/67.5초 최종본. 기존 본문·음성·자막·음악 시각은 보존한다. 이전 '다음 제작에만 적용' 요청은 현재도 적용하라는 최신 지시로 갱신됐다. 기존 v18/v30 파일은 보존하고 v31을 만든다.

`sumuk.prepare_scene(project,episode,source,scene)`와 `validate_episode(episode_path)`를 사용한다. 프로젝트에 회차 art/painting.json, config/player-settings.json, episode.json(플레이어 메타데이터)이 있어야 한다. 좌표는1000×652. 누끼와 카메라는 장면별 시각 검수가 필요하다. 의존성 numpy/Pillow/scipy/opencv-python/scikit-image는 이 프로젝트 serise001/.venv에 있다.

실제 Aside u2 canvas를 WebCodecs AVC로 출력한다. 연속 dequeue/마지막 flush, 언어별 공통 그림 프레임과 원래 자막 함수를 쓴다. 일반/공유 렌더 KO/EN/JA, 카메라 합성 범위 최적화 전후/되감기 픽셀을 비교했다. EP03을 sample 새 회차로 만들어770개 획/전 PNG 바이트 일치도 검증했다. EP06 배경 대상13,187픽셀은 배경 전0개/배경 후전부 표시를 실제 플레이어에서 확인했다.

현재 실행: `SUMUK_REVISION=31 SUMUK_RENDER_PORT=5187 python3 series/scripts/render_v30_server.py` 후 Aside에서 `http://127.0.0.1:5187/series/site/render-v30.html`을 연다. lib sumuk.py CLI는 v31 환경을 사용한다. 기존 영상의 도입만 교체하는 `patch_intro_v31.py`는8초 이후 H264 그림과 전 AAC를 복사하고 픽셀·패킷 동일성을 검사한다. 결과는 output/v31/manifest.json. 공개 배포는 별도 작업이다.
