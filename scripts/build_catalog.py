"""Generate the complete static file catalog for GitHub Pages (standard library only)."""
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
import html
import json

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/tjkim-image01/cocktail-motion'
EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', 'node_modules'}
EXCLUDED_NAMES = {'.DS_Store', 'files.html', 'catalog.json'}


def build():
    entries = []
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if not path.is_file() or EXCLUDED_DIRS.intersection(relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in {'.pyc', '.log'}:
            continue
        entries.append({'path': relative.as_posix(), 'bytes': path.stat().st_size})
    groups = defaultdict(list)
    for entry in entries:
        parts = entry['path'].split('/')
        group = '/'.join(parts[:3]) if parts[:2] == ['project', 'sample'] and len(parts) > 3 else parts[0] if len(parts) > 1 else '루트'
        url = quote(entry['path'], safe='/')
        name = html.escape(entry['path'])
        size = entry['bytes']
        size_label = f'{size / 1_000_000:.2f} MB' if size >= 1_000_000 else f'{size / 1000:.1f} KB'
        groups[group].append(f'<li><a href="{url}">{name}</a><span>{size_label}</span><a class="source" href="{REPOSITORY}/blob/main/{url}">GitHub</a></li>')
    sections = []
    for group, rows in groups.items():
        sections.append(f'<details open><summary>{html.escape(group)} · {len(rows)}개</summary><ul>{"".join(rows)}</ul></details>')
    total = sum(entry['bytes'] for entry in entries)
    page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cocktail · 전체 자료</title><style>
    :root{font:16px/1.6 system-ui,sans-serif;color:#302d2d;background:#faf9f5}body{max-width:1100px;margin:48px auto;padding:0 24px}h1{font-size:32px;margin-bottom:4px}nav{display:flex;gap:20px;flex-wrap:wrap;margin:20px 0}a{color:#873d4f;text-underline-offset:3px}input{box-sizing:border-box;width:100%;padding:14px;font:inherit;border:1px solid #c9beb5;background:#fff;margin:12px 0 24px}details{border-top:1px solid #d8d0c6;padding:14px 0}summary{cursor:pointer;font-weight:650}ul{list-style:none;padding:0}li{display:grid;grid-template-columns:minmax(0,1fr) 90px 65px;gap:12px;padding:7px 0;font-size:14px}li>a:first-child{overflow-wrap:anywhere}li span{text-align:right;color:#6e6763}.source{font-size:12px;text-align:right}[hidden]{display:none!important}@media(max-width:600px){body{padding:0 16px;margin:24px auto}li{grid-template-columns:minmax(0,1fr) 70px}.source{display:none}}</style></head><body>
    <h1>Cocktail · 전체 자료</h1><p>원본 영상, 개별 원화와 프롬프트, V1~V4, 프레임 측정값, 검수 사진, 효과음, 제작 위키, 공용 lib.</p>
    <nav><a href="project/sample/04_장면조립/web/compare.html">원본 / 제작본 비교</a><a href="REPO/tree/main/project/wiki">제작 위키</a><a href="REPO">GitHub 저장소</a><a href="REPO/archive/refs/heads/main.zip">전체 ZIP 다운로드</a></nav>
    <p>COUNT개 파일 · 약 TOTAL MB. Python 가상환경과 실행 캐시는 제외했습니다. 자료 파일은 열거나 다운로드할 수 있고, 문서는 GitHub 링크에서 읽을 수 있습니다.</p>
    <label for="search">파일명 검색</label><input id="search" type="search" placeholder="예: v4, 얼음, intro, mp4" autocomplete="off"><main>SECTIONS</main>
    <script>document.querySelector('#search').addEventListener('input',event=>{const query=event.target.value.trim().toLocaleLowerCase();document.querySelectorAll('details').forEach(section=>{let visible=0;section.querySelectorAll('li').forEach(row=>{row.hidden=!row.querySelector('a').textContent.toLocaleLowerCase().includes(query);if(!row.hidden)visible++;});section.hidden=visible===0;if(query)section.open=true;});});</script></body></html>'''
    page = page.replace('REPO', REPOSITORY).replace('COUNT', str(len(entries))).replace('TOTAL', f'{total / 1_000_000:.1f}').replace('SECTIONS', ''.join(sections))
    (ROOT / 'files.html').write_text(page)
    (ROOT / 'catalog.json').write_text(json.dumps({'files': entries, 'count': len(entries), 'bytes': total}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'count': len(entries), 'bytes': total}))


if __name__ == '__main__':
    build()
