# Instagram 릴스

Aside u5의 로그인된 Instagram에서 기존 브라우저 탭을 사용한다. 영상 업로드 → 릴스 안내 확인 → 9:16 자르기 → JPG/PNG 커버 → 캡션 → AI 레이블 → 공유 순서다. UI snapshot의 ref로 최종 공유 버튼을 선택한다.

```sh
python3 -m lib.com.jatu.aside.upload.instagram \
  --video project/jatu001/video/result/jatu001_clip_v5.mp4 \
  --cover project/jatu001/video/result/jatu001_thumbnail_v5.jpg \
  --caption project/jatu001/video/result/jatu001_clip_v5.instagram-caption.txt
```

기본 실행은 입력만 검증한다. `--execute`를 추가하면 공개 게시한다. 기본 계정은 u5 / jfktwo5이며 `--account`, `--username`으로 지정할 수 있다. 준비 파일 경로는 절대 경로로 변환한다.

영상 옆 `.instagram-upload.json`과 `instagram-work/실행시각/`에 결과 및 MCP 응답을 기록한다. 공개 성공 문구를 확인한 뒤 프로필 게시물 주소도 수집한다. 게시 시도 중 오류·시간 초과가 발생하면 `unknown`으로 기록하고 재실행을 차단한다. 먼저 브라우저와 프로필을 확인해서 성공 여부를 판정한 뒤 기록을 정리해야 한다. 처리 중 화면이 오래 표시되어도 공유 버튼을 다시 누르지 않는다.

실제 v5 업로드는 같은 MCP 화면 절차로 수행했다. 모듈 전체를 재실행해 중복 게시하지 않았으며 Python 구문 검사와 게시 없는 입력 검증을 수행했다.
