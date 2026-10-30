# 04 — 장면 조립

`web/index.html`: 제작본 단독. `web/compare.html`: 원본과 Three.js를 나란히 보는 기본 진입점.

생성 물건은 `MeshBasicMaterial + PlaneGeometry`, 정사영 카메라로 1080 화면에 놓는다. 알파 PNG의 유효 영역은 UV로 잡고 원본 파일은 보존한다. 설명 글자와 도식은 CanvasTexture로 그린다. Three.js와 OFL 서체는 `vendor/`에 있어 실행 중 외부 CDN이 필요 없다. Three.js는 기존 three001 vendor에서 복사했으며 라이선스를 함께 보존했다. Lilita One, Barlow Condensed는 Google Fonts 공식 저장소에서 가져왔고 OFL을 함께 둔다.

조작: 공통 재생/정지, 처음으로, ±1프레임, 0.25~2배속, 반복, 현재 PNG, 타임라인, 구간 바로가기. 키보드 Space, 좌/우 1초 이동. 하단에는 30쌍의 정수초 사진과 물건 9종 원형 보드를 둔다.

비교 재생은 원본 HTML video 시간을 기준 시계로 사용한다. 일시정지와 seek에서는 같은 숫자의 시간을 양쪽에 명시적으로 전달한다. 브라우저 디코더 지연 때문에 명령 직후 원본 화면 전환은 비동기이며 seek 완료 후 검수한다.

감상 결과는 Three.js 실시간 장면이며 MP4 텍스처가 아니다. 원본 MP4는 왼쪽 비교 화면에서만 사용한다.

V2: ±0.1초 이동·제목/얼음 구간 반복·0.1초 사진 300쌍·특징 정리 및 MP4 링크를 추가했다. 제목은 Luckiest Guy(Apache 라이선스), 보조 글자는 Patrick Hand(OFL)를 추가해 로컬에 보관한다. 원본 서체를 확인한 것은 아니다.
