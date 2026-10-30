"""TJ KIM 수묵 드로잉 공통 제작법 v31 (2026-10-27 사용자 지시).

기준 본문: EP03 「옷을 두드리던 시간」 한국어 플레이어. EP06은 팔 옆 배경선의
잘못된 인물 누끼를 수정했다. 현재와 다음 제작 모두 표지 직후 붓이 바로 나온다.

1. 빈 종이에서 한 사람씩 머리·얼굴/머리카락·모자 밑색 → 몸 채색 → 머릿결·표정·옷선.
   그 사람을 마친 뒤 다음 인물, 이후 물건, 마지막 색별 배경과 배경 세선이다.
2. 한 획은 상수 RGB 하나, 질감·농담은 alpha만 변한다. 안료 변경 때 .13초,
   배경색 변경 때 .2초 이상 붓을 든다. 서로 떨어진 경로에도 붓을 든다.
3. 인물 외곽 다각형 안에 있다는 이유로 배경을 인물로 분류하지 않는다. 팔 바깥/팔 사이/
   다리 사이와 옷 가장자리의 창살·벽·바닥 선을 반드시 배경 제외 마스크로 분리한다.
   scene.background_exclusions(1000×652 논리좌표 다각형) 또는 background_exclusion_mask
   (흰색=배경으로 남길 영역)를 지정한다. 이 마스크는 인물·물건 채색/세선보다 우선한다.
   사람이 끝나도 배경선은 보이지 않고, 마지막 배경 단계에서 나타나야 한다.
4. 각 그림 자신의 원본·팔레트·인물/물건 마스크와 방향성 경로를 사용한다. EP03/EP06의
   인물 형상을 다른 그림에 복사하지 않는다. 머리는 좁은 방향성 획으로 채운다.
5. 4000×2608 작업화판의 안료를 실제 붓 경로 마스크로 드러낸다. SVG 재추적 선,
   획 끝 전체 면 채우기, 가로 스캔/DFS 왕복을 쓰지 않는다. 확대를 native4K라 하지 않는다.
6. 3D 붓은 실제 경로·방향·속도·추정 필압에 연동한다. 접촉점을 고정하고 카메라 확대에
   물리 비율을 맞춘다. 채색은 인물 전체, 세부 때 확대한다. 원작가 필압 복원이라 하지 않는다.
7. 1080×1920,30fps. 본문 그림은 위75%, 한 줄 명조 자막 y1374/저장한54px.
   자막은 공백·문장부호 포함18자 이내. 타이핑·바운스를 넣지 않는다.
8. 도입6초, 본편66초, 언어별1.5초 무음 표지 포함67.5초/2025프레임.
   표지 다음 첫 프레임부터 붓/첫 획: 0~3.5초 쓰기,4.15초 전체,6초 본문.
   승인 Tj 비트맵/사선 붓 v29를 유지하고 S자 꺾임·둥근 퍼짐 대신 단일 곡률/좁은 타원.
   본문·해설·자막·음악 시각은 바꾸지 않는다. 첫1초 빈 종이 대기는 금지한다.
9. 저장한 곡/음량/offset/musicStart를 따른다(현재0초). 재생 동작에서 음성을 준비한다.
   본문 별도 효과음은 없다. 기존 Typecast KO/EN/JA 해설을 보존한다.
10. Aside u2 실제 canvas를 고정 시각으로 WebCodecs AVC 인코딩한다. dequeue로 대기하고
    마지막에만 flush한다. 언어별로 같은 그림 프레임과 원래 자막 함수를 공유한다.
    검증된 카메라 영역만 임시 합성하되 전체 안료 캐시는 보존한다. 기존 MP4의 도입만
    바꿀 때는 본문 H264 슬라이스와 AAC를 복사해 그림과 소리를 보존할 수 있다.
11. 실제 모든 안료 PNG의 RGB·머리→몸→세선·붓 들기·배경 제외를 검사한다. 누끼는
    원본과 비교해 시각 검수하고, 배경 직전/배경 완성 프레임으로 섞임을 확인한다.
    완전 디코드/프레임 수/소리/첫 붓 프레임을 검사한 영상만 연결한다. 기존 파일은 보존한다.

prepare_scene(project,episode,source,scene), validate_episode(episode_path).
--describe / --verify path/to/episode / --project path/to/series --episode ep07 --language ko en ja.
구현은 sumuk_v30/ (호환 경로), 현재 규칙은 quality.json, 과거 기록은 HISTORY.md.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess
from datetime import datetime
from pathlib import Path

# Latest approved recipe takes precedence over the historical production notes above.
RECIPE = json.loads((Path(__file__).with_name('sumuk_v30')/'quality.json').read_text())

def prepare_scene(project:Path, episode:str, source:Path, scene:dict):
    """Prepare another artwork using its own source and hand-authored scene masks.

    Project must contain episodes/<id>/{art,config,episode.json}. Scene coordinates
    are logical 1000x652: people=[{key,poly,head}], objects=[polygon,...]. Head=None
    means a covered rear head; optional ownership_order resolves overlaps. Review
    masks and camera framing for each new image; never transplant EP03 geometry.
    Existing sources/settings are preserved. Output is a review, not auto approval.
    """
    try:from .sumuk_v30.build_series_raster_v24 import build
    except ImportError:from sumuk_v30.build_series_raster_v24 import build
    report=build(episode,project=project,source_path=source,scene=scene)
    # New artwork starts the brush at first contact; existing delivery files are preserved.
    info_path=Path(project)/'episodes'/episode/'episode.json'
    info=json.loads(info_path.read_text());info['player_director'].update(intro_brush_visible_from=0,intro_duration=6,signature_duration=3.5,signature_revision=31)
    info_path.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    return report

def validate_episode(episode:Path):
    try:from .sumuk_v30.quality import validate
    except ImportError:from sumuk_v30.quality import validate
    return validate(episode)


def run(args: list[str], **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def sha256(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def export(project:Path, language:str, settings_path:Path|None=None, destination:Path|None=None, episode:str='ep02'):
    """Export the prepared edition through Aside u2; never rewrite live settings."""
    project=project.resolve()
    info=json.loads((project/'episodes'/episode/'episode.json').read_text())
    if info.get('player_only') and info.get('review_status')=='awaiting-user':
        raise RuntimeError('Review and approve this artwork before making its MP4.')
    engine=project/'scripts/render_v30_cli.py'
    if not engine.is_file():raise FileNotFoundError('Install the approved render_v30_cli.py/server and render-v30 page into the project first.')
    args=[os.sys.executable,str(engine),episode,language]
    if settings_path:args+=['--settings',str(settings_path.resolve())]
    run(args,env={**os.environ,'SUMUK_REVISION':'31','SUMUK_RENDER_PORT':'5187'})
    mp4=project/'episodes'/episode/'output'/f'{episode}-short-{language}-v31-cover.mp4'
    if destination:
        import shutil
        destination.mkdir(parents=True,exist_ok=True)
        target=destination/mp4.name;shutil.copy2(mp4,target);return target
    return mp4


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--verify',type=Path);parser.add_argument('--describe',action='store_true');parser.add_argument('--project',type=Path)
    parser.add_argument('--language',choices=['ko','en','ja'],nargs='+',default=['ko'])
    parser.add_argument('--episode',nargs='+',default=['ep02']);parser.add_argument('--settings',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.verify:print(json.dumps(validate_episode(args.verify),ensure_ascii=False,indent=2));return
    if args.describe:print('최신 기준: v31 / EP03 본문 / EP06 배경 누끼 교정 / 첫 프레임 붓.');print(__doc__);print(json.dumps(RECIPE,ensure_ascii=False,indent=2));return
    if not args.project:parser.error('--project is required for export')
    for episode in args.episode:
        for lang in args.language:export(args.project,lang,args.settings,args.output/episode/lang if args.output else None,episode)

if __name__=='__main__':main()
