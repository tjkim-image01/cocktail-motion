#!/usr/bin/env python3
"""Scaffold, extract and serve the 2damin image-sequence animation workflow."""
import argparse
import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LIB = Path(__file__).resolve().parent

def init(args):
    root = args.project.resolve()
    names = ['index.html', 'player.js', 'face.js']
    conflicts = [root / n for n in names + ['2damin.json'] if (root / n).exists()]
    if conflicts:
        raise SystemExit('Existing files preserved: ' + ', '.join(map(str, conflicts)))
    for n in ['assets', 'video', 'frames', 'face', 'audio', 'qa']:
        (root / n).mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(LIB / 'web' / n, root / n)
    shutil.copy2(LIB / 'examples/default.json', root / '2damin.json')
    print(f'Scaffold saved: {root}. Add frames, face assets, audio and lipsync before playback.')

def extract(args):
    root = args.project.resolve()
    video = args.video.resolve()
    if not video.is_file():
        raise SystemExit(f'Missing video: {video}')
    frames = root / 'frames'
    if frames.exists() and any(frames.iterdir()):
        raise SystemExit('frames/ is not empty. Preserve the existing result before extracting again.')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)]))
    s = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    fps = Fraction(s['avg_frame_rate'])
    if fps <= 0:
        raise SystemExit('Video FPS could not be determined')
    frames.mkdir(parents=True, exist_ok=True)
    (root / 'video').mkdir(exist_ok=True)
    (root / 'qa').mkdir(exist_ok=True)
    dest = root / 'video/flow-original.mp4'
    if dest != video:
        if dest.exists():
            raise SystemExit(f'Existing video preserved: {dest}')
        shutil.copy2(video, dest)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(dest), '-map', '0:v:0', '-fps_mode', 'passthrough', '-q:v', '2', '-start_number', '0', str(frames / '%04d.jpg')], check=True)
    paths = sorted(frames.glob('*.jpg'))
    if len(paths) != int(s['nb_read_frames']):
        raise SystemExit('Decoded frame count does not match ffprobe')
    m = dict(title=args.title, method='Flow first/last frames → decoded images → independent facial performance', count=len(paths), fps=float(fps), fpsRational=str(fps), duration=len(paths)/float(fps), videoDuration=float(probe['format']['duration']), width=s['width'], height=s['height'], frames=[p.relative_to(root).as_posix() for p in paths], video='video/flow-original.mp4', videoSha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    (root / 'manifest.json').write_text(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
    (root / 'qa/probe.json').write_text(json.dumps(probe, indent=2)+'\n')
    print(json.dumps({k:m[k] for k in ['count','fps','duration','width','height']}, ensure_ascii=False))

def serve(args):
    root = args.project.resolve()
    print(f'2damin: http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), partial(SimpleHTTPRequestHandler, directory=str(root))).serve_forever()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    q = commands.add_parser('init'); q.add_argument('project', type=Path); q.set_defaults(run=init)
    q = commands.add_parser('extract'); q.add_argument('video', type=Path); q.add_argument('--project', type=Path, required=True); q.add_argument('--title', default='2damin'); q.set_defaults(run=extract)
    q = commands.add_parser('serve'); q.add_argument('project', type=Path); q.add_argument('--port', type=int, default=4345); q.set_defaults(run=serve)
    args = p.parse_args(); args.run(args)

if __name__ == '__main__':
    main()
