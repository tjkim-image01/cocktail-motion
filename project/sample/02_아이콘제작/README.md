# 02 — 개별 오브젝트

생성 경로: **imagegen 스킬의 내장 image_gen 도구**. CLI/API 우회 미사용. 원본 생성 파일은 Codex generated_images에 보존하고 채택 원화를 이 폴더 `assets/`에 복사했다.

최종 프롬프트 전체는 `prompts/`의 같은 이름 txt에 저장한다. 기본 그림은 얇은 먹선·파스텔 평면색·실제 투명 배경을 요청했다. 원본은 물건당 새 이미지이며 원본 영상에서 추출한 물건 이미지를 그대로 재생하지 않는다.

| 파일 | 대상 |
| --- | --- |
| glass.png / glass-v2.png | 빈 잔, 후속 단순화 버전 별도 보존 |
| ice.png / ice-v2.png | 얼음 한 개, 장면에서 3개 복제 |
| gin.png | 진 병 |
| campari.png | 캄파리 병 |
| vermouth.png | 스위트 베르무트 병 |
| spoon.png | 바 스푼 |
| peel.png | 오렌지 껍질 |
| liquid-clear.png | 맑은 진 액체 |
| liquid-red.png | 붉은 칵테일 액체 |

액체도 실제 이미지로 따로 생성했다. 수위는 위 물체 PNG를 잔 바닥에 고정한 채 높이를 바꾸어 표현한다. 따르는 가는 줄기·파문은 실시간 곡선이다.

PNG 파일의 알파는 보존한다. `asset-bounds.json`은 원화 알파를 읽어 만든 UV 경계 정보이며 파일을 다시 그리거나 배경 제거한 산출물이 아니다. 원본보다 상세한 병 디자인 등 시각적 차이는 남는다.
