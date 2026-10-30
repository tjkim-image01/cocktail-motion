# 네이버 클립 반영 코드

`clip.py`는 Aside stdio MCP 연결·스냅샷·작업 기록을 제공한다. `clip_flow.py`는 2026-10-09 실제 UI에서 사용한 클립 크리에이터 업로드와 기존 블로그 글에 링크 카드 추가 절차를 구현한다.

## 이번 반영

- 계정 u3, 클립 프로필 `@health_factnote`, 별명 건강 팩트노트.
- 영상 v5 / 썸네일 JPG, 공개, 건강·의학 → 생활건강, AI 활용 ON.
- 기존 글 `224436178922`에 도입부 뒤 클립 OG 썸네일 카드 추가. 기존 비공개 유지.
- 게시 주소·검증 기록: `project/jatu001/video/result/jatu001_clip_v5.naver-upload.json`.
- PC 블로그 ‘내 클립’은 Creator에서 만든 클립을 표시하지 않았다. 링크 카드를 네이티브 블로그 클립 플레이어로 표기하지 않는다.

## 코드 사용

루트에서 `python3 -m lib.com.jatu.aside.naverblog.clip --video project/jatu001/video/result/jatu001_clip_v5.mp4 --inspect`로 탭 목록을 확인할 수 있다. 같은 제목의 이전 글이 있으므로 수정할 글 번호는 명시한다.

라이브 MCP를 유지한 채 `NaverClipFlow(client).upload(video, cover, description)`으로 클립을 등록하고, 반환된 URL을 즉시 기록한다. 이후 `attach_card(post_url, clip_url)`로 기존 글에 연결한다. URL이 이미 있으면 카드 추가는 건너뛴다.

재실행 시 이번 영상은 다시 업로드하지 않는다. 저장된 naver-upload.json의 클립 URL을 사용한다. 중간 실패 시 Creator 콘텐츠 목록과 원문을 먼저 확인한다. 프로필 개설과 이름 변경은 자동화하지 않았다.

기존 탭 일부는 Page.enable 시간 초과가 났으나 같은 주소를 새 탭으로 열면 정상 동작했다. 새 탭은 MCP 종료 시 닫히므로 업로드·편집·저장·검증까지 한 연결을 유지한다. UI 변화에 따라 단계별 스냅샷을 확인한다.

검증: 파이썬 문법 검사, 실제 v5 업로드·공개 상태 확인, 실제 포스트 저장 뒤 Clip 링크와 썸네일 카드 확인. 재사용 클래스 전체를 별도 영상으로 다시 실행한 것은 아니다.

공식 안내: https://help.naver.com/service/30048/contents/24422?lang=ko&osType=COMMONOS
