"""Apply blog/jatu002's directory layout and copy requested shared resources."""
from pathlib import Path
import shutil
import hashlib

root = Path(__file__).resolve().parents[1]
blog = root.parent / 'blog'
template = blog / 'project/jatu002'
project = root / 'project/j001'
created = []
for directory in template.rglob('*'):
    if directory.is_dir() and len(directory.relative_to(template).parts) <= 2:
        target = project / directory.relative_to(template)
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)

def copy_verified(source, destination):
    count = 0
    for item in source.rglob('*'):
        if item.is_file():
            target = destination / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != item.read_bytes():
                raise RuntimeError(f'Conflicting existing file: {target}')
            shutil.copy2(item, target)
            assert hashlib.sha256(item.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
            count += 1
    return count

lib_count = copy_verified(blog / 'lib', root / 'lib')
sources = {
    'jatu002': template / '06_편집검수/01_스크립트',
    'jatu001_motion': blog / 'project/jatu001/youtube/motion/scripts',
}
script_counts = {name: copy_verified(source, root / 'scripts' / name) for name, source in sources.items()}

moves = {
    '해외_탁구영상_소스_조사.md': '02_조사/02_근거정리/해외_탁구영상_소스_조사.md',
    'channel_frame.png': '02_조사/01_원본자료/channel_frame.png',
    'aside_evidence.jsonl': '09_작업기록/03_로그/aside_evidence.jsonl',
}
for old, new in moves.items():
    source, target = project / old, project / new
    if source.exists():
        if target.exists():
            raise RuntimeError(f'Move destination exists: {target}')
        assert target.resolve().is_relative_to(root.resolve())
        shutil.move(str(source), str(target))

for directory in created:
    if not any(directory.iterdir()):
        (directory / '.gitkeep').touch()
for name in ['06_편집검수/02_중간렌더', '09_작업기록/03_로그']:
    (project / name / '.gitignore').write_text('*\n!.gitignore\n!.gitkeep\n', encoding='utf-8')
print({'layout_directories': len(created), 'lib_files_copied_verified': lib_count, 'scripts_copied_verified': script_counts})
