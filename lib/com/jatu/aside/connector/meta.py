"""Meta AI - Aside 브라우저 전용 커넥터 (AsideMetaConnector / MetaConnector).

주요 아키텍처:
1. Aside CLI & REPL (`aside repl` / `aside mcp`):
   - Aside 브라우저 내 jatu 프로필(u0)의 Meta AI 세션(https://meta.ai/prompt/...)에 연결합니다.
   - CDP `DOM.setFileInputFiles`로 시작 이미지/소재를 100% 무결점 첨부합니다.
   - React Native Setter 및 CDP `Input.insertText`를 통해 프롬프트를 전송합니다.
2. 자동화 파이프라인:
   - 클립별 프롬프트 자동 로드 (flow-object.md, meta.md, 대본.txt 지원)
   - 시작 프레임 이미지 자동 감지 및 첨부 (Tail-to-Head 연속성)
   - 전송 버튼 클릭 및 실시간 생성 완료 감지
   - 생성 완료된 고화질 비디오 MP4 URL 자동 추출 및 다운로드 (`result/{clip_id}.mp4`)
   - FFmpeg 기반 다음 클립용 테일 프레임 자동 추출 (`.frames/{clip_id}_last.png`)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, Union

ROOT_DIR = Path(__file__).resolve().parents[5]
ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"


class AsideMetaConnector:
    name = "aside-meta"

    def __init__(
        self,
        project_name: Optional[str] = None,
        prompt_file: Optional[Union[str, Path]] = None,
        account: Optional[str] = None
    ):
        self.project_name = project_name or self._resolve_current_project_name()
        self.project_dir = ROOT_DIR / "project" / self.project_name
        self.session_file = self.project_dir / "session.json"
        self.account = account or self._resolve_account() or "u0"

        if prompt_file:
            self.prompts_file = Path(prompt_file).resolve()
        else:
            meta_obj = self.project_dir / "meta-object.md"
            flow_obj = self.project_dir / "flow-object.md"
            meta_std = self.project_dir / "meta.md"
            script_txt = self.project_dir / "대본.txt"
            if meta_obj.exists():
                self.prompts_file = meta_obj
            elif flow_obj.exists():
                self.prompts_file = flow_obj
            elif meta_std.exists():
                self.prompts_file = meta_std
            elif script_txt.exists():
                self.prompts_file = script_txt
            else:
                self.prompts_file = meta_obj

        self.res_dir = self.project_dir / "res"
        self.result_dir = self.project_dir / "result"
        self.frames_dir = self.result_dir / ".frames"

        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)

        self.project_id, self.target_url = self._resolve_meta_project()

    def _resolve_account(self) -> Optional[str]:
        if not self.session_file.exists():
            return None
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            return data.get("account")
        except Exception:
            return None

    def _resolve_current_project_name(self) -> str:
        now_file = ROOT_DIR / "session" / "now"
        if now_file.exists():
            name = now_file.read_text(encoding="utf-8").strip()
            if name:
                return name
        return "s014"

    def _resolve_meta_project(self) -> tuple[Optional[str], str]:
        default_url = "https://meta.ai/prompt/07f031a0-59a2-4f00-85e3-58ac39f5157e"
        if not self.session_file.exists():
            return None, default_url
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            pid = data.get("projectId")
            url = data.get("projectUrl") or (f"https://meta.ai/prompt/{pid}" if pid else default_url)
            return pid, url
        except Exception:
            return None, default_url

    def run_aside_repl(self, script_code: str, timeout: int = 120) -> tuple[bool, str]:
        """Aside REPL을 통해 Playwright/CDP 코드를 실행합니다."""
        cmd = [ASIDE_BIN]
        if self.account:
            cmd.extend(["--account", self.account])
        cmd.extend(["repl", script_code])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
            return proc.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Aside REPL 실행 시간 초과"
        except Exception as e:
            return False, str(e)

    def is_logged_in(self) -> bool:
        """Aside 브라우저의 활성 세션을 확인합니다."""
        check_js = """
        const page = await attachActiveBrowserTab();
        const info = await page.evaluate(() => {
            return {
                title: document.title,
                url: window.location.href,
                hasInput: !!document.querySelector('textarea, [contenteditable="true"]')
            };
        });
        console.log(JSON.stringify(info));
        """
        ok, out = self.run_aside_repl(check_js, timeout=10)
        return ok and "Meta AI" in out

    def get_clip_info(self, clip_id: str) -> Dict[str, Any]:
        """지정된 클립(S01, S02 등)의 프롬프트와 시작 프레임 이미지를 계산합니다."""
        if not self.prompts_file.exists():
            # 만약 아직 프롬프트 파일이 없으면 10초 대본 또는 기본값 생성
            return {
                "clip_id": clip_id,
                "project_name": self.project_name,
                "prompt": f"{clip_id} 영상 생성",
                "start_frame_path": str(self.res_dir / "basic.png") if clip_id == "S01" else str(self.frames_dir / f"{clip_id[0]}{int(clip_id[1:])-1:02d}_last.png"),
                "duration": "10초"
            }

        content = self.prompts_file.read_text(encoding="utf-8")

        # 1. 코드 블록 형태 탐색: S01 : ...
        pattern = rf"({re.escape(clip_id)}\s*[:.]\s*Duration\s+[0-9]+\s+seconds.*?)(?=```|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            prompt = match.group(1).strip()
        else:
            # 2. 섹션 형태 탐색: ### S01 ...
            sec_pattern = rf"###\s+{re.escape(clip_id)}.*?(?=(?:###|\Z))"
            sec_match = re.search(sec_pattern, content, re.DOTALL)
            if sec_match:
                prompt = sec_match.group(0).strip()
            else:
                prompt = f"{clip_id} 장면을 고화질 영상으로 생성해줘"

        # 시작 파일 경로 탐색
        start_frame = None
        section_pattern = rf"###\s+{re.escape(clip_id)}.*?(?=(?:###|\Z))"
        sec_match = re.search(section_pattern, content, re.DOTALL)
        if sec_match:
            sec_text = sec_match.group(0)
            file_match = re.search(r"-\s*\*\*시작\s*파일\*\*:\s*`?([^`\r\n\(\)]+)`?", sec_text)
            if file_match:
                raw_path = file_match.group(1).strip()
                cand_path = Path(raw_path)
                if not cand_path.is_absolute():
                    cand_path = ROOT_DIR / cand_path
                if cand_path.exists():
                    start_frame = cand_path

        if not start_frame:
            if clip_id in ("C00", "S01"):
                for ext in (".png", ".jpeg", ".jpg", ".webp"):
                    candidate = self.res_dir / f"basic{ext}"
                    if candidate.exists():
                        start_frame = candidate
                        break
                else:
                    start_frame = self.res_dir / "basic.png"
            else:
                prev_num = int(clip_id[1:]) - 1
                prev_id = f"{clip_id[0]}{prev_num:02d}"
                c1 = self.frames_dir / f"{prev_id}_last.png"
                if c1.exists():
                    start_frame = c1
                else:
                    prev_video = self.result_dir / f"{prev_id}.mp4"
                    if prev_video.exists():
                        self.extract_last_frame(prev_id, str(prev_video))
                        start_frame = c1
                    else:
                        start_frame = c1

        dur_match = re.search(r"Duration\s+([0-9]+)\s+seconds", prompt)
        duration = f"{dur_match.group(1)}초" if dur_match else "10초"

        return {
            "clip_id": clip_id,
            "project_name": self.project_name,
            "project_id": self.project_id,
            "prompt": prompt,
            "start_frame_path": str(start_frame),
            "duration": duration
        }

    def extract_last_frame(self, clip_id: str, video_path: Optional[str] = None) -> str:
        """생성 완료된 비디오의 마지막 프레임을 추출하여 저장합니다."""
        if not video_path:
            video_path = str(self.result_dir / f"{clip_id}.mp4")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"추출 대상 비디오 파일이 없습니다: {video_path}")

        out_path = self.frames_dir / f"{clip_id}_last.png"
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                ffmpeg = "ffmpeg"
        cmd = [
            ffmpeg, "-y",
            "-sseof", "-0.1",
            "-i", video_path,
            "-update", "1",
            "-q:v", "1",
            str(out_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg 마지막 프레임 추출 실패: {res.stderr}")

        return str(out_path)

    def generate_clip(self, clip_id: str, wait_completion: bool = True) -> Dict[str, Any]:
        """Meta AI를 통해 영상을 생성하고 다운로드하여 테일 프레임까지 추출합니다."""
        info = self.get_clip_info(clip_id)
        start_frame_path = info["start_frame_path"]
        prompt_text = info["prompt"]

        print(f"\n🚀 [AsideMeta] {clip_id} 생성 파이프라인 가동")
        print(f"  • 대상 URL: {self.target_url}")
        print(f"  • 프로필/계정: {self.account}")
        print(f"  • 시작 프레임: {start_frame_path}")

        has_start_frame = os.path.exists(start_frame_path)

        # Meta AI 자동화 스크립트 작성
        automation_script = f"""
        await (async () => {{
            const page = await attachActiveBrowserTab();

            // 1) 페이지 확인 및 이동 (현재 대화가 아니면 이동)
            if (!page.url().includes('{self.project_id or "meta.ai"}')) {{
                await page.goto('{self.target_url}');
                await new Promise(r => setTimeout(r, 2500));
            }}

            // 2) 현재 페이지 내 기존 동영상 URL 저장
            const initialVideoData = await page.evaluate(() => {{
                const urls = Array.from(document.querySelectorAll('video'))
                    .map(v => v.currentSrc || v.src)
                    .filter(s => s && s.includes('http'));
                return {{ count: urls.length, urls }};
            }});
            console.log('INITIAL_VIDEO_COUNT:' + initialVideoData.count);
            console.log('INITIAL_URLS:' + JSON.stringify(initialVideoData.urls));

            // 3) 시작 프레임 이미지 첨부 (존재하는 경우)
            if ({json.dumps(has_start_frame)}) {{
                console.log('ATTACHING_START_FRAME...');
                const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1 }});
                const {{ nodeIds }} = await page._sendToTarget('DOM.querySelectorAll', {{
                    nodeId: root.nodeId,
                    selector: 'input[type=file]'
                }});
                if (nodeIds && nodeIds.length > 0) {{
                    await page._sendToTarget('DOM.setFileInputFiles', {{
                        files: ['{start_frame_path}'],
                        nodeId: nodeIds[0]
                    }});
                    console.log('FILE_INPUT_SET_SUCCESS');
                }}

                // 첨부 썸네일 노출 대기 (최대 10초)
                let attached = false;
                for (let i = 0; i < 20; i++) {{
                    await new Promise(r => setTimeout(r, 500));
                    attached = await page.evaluate(() => {{
                        const delBtn = document.querySelector('[aria-label*="Remove"], [aria-label*="삭제"], [aria-label*="제거"]');
                        return !!delBtn;
                    }});
                    if (attached) break;
                }}
                console.log('IMAGE_ATTACHED_VERIFIED:' + attached);
            }}

            // 4) 프롬프트 텍스트 입력
            await page.evaluate((text) => {{
                const ta = document.querySelector('textarea, [contenteditable="true"]');
                if (ta) {{
                    ta.focus();
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                    if (setter) {{
                        setter.call(ta, text);
                        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }} else {{
                        ta.value = text;
                        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }}
            }}, {json.dumps(prompt_text)});
            await new Promise(r => setTimeout(r, 600));

            // 5) 전송 버튼 클릭
            const sent = await page.evaluate(() => {{
                const sendBtns = Array.from(document.querySelectorAll('button[aria-label="보내기"], button[aria-label*="전송"]'));
                const activeBtn = sendBtns.find(b => !b.disabled);
                if (activeBtn) {{
                    activeBtn.click();
                    return 'CLICKED';
                }}
                return 'NOT_CLICKABLE';
            }});
            console.log('SEND_STATUS:' + sent);

            if (sent !== 'CLICKED') {{
                // Enter 키 시도
                await page.keyboard.press('Enter');
                console.log('SENT_VIA_ENTER');
            }}
        }})();
        """

        print("  ⏳ Aside 브라우저(u0)를 통해 Meta AI에 프롬프트 전송 중...")
        ok, out = self.run_aside_repl(automation_script, timeout=60)
        if not ok:
            raise RuntimeError(f"Meta AI 전송 실패: {out}")

        initial_urls = []
        for line in out.splitlines():
            if line.startswith("INITIAL_URLS:"):
                try:
                    initial_urls = json.loads(line.replace("INITIAL_URLS:", "").strip())
                except Exception:
                    pass

        print(f"  ✅ Meta AI에 프롬프트 전송 완료! (기존 영상 {len(initial_urls)}개 감지됨, 신규 비디오 생성 완료 대기 중...)")

        if not wait_completion:
            return {"status": "started", "clip_id": clip_id}

        # 6) 비디오 생성 완료 모니터링 및 URL 추출
        video_url = None
        poll_script = f"""
        await (async () => {{
            const page = await attachActiveBrowserTab();
            const res = await page.evaluate((prevUrls) => {{
                const videos = Array.from(document.querySelectorAll('video'));
                const newVideo = videos.slice().reverse().find(v => {{
                    const src = v.currentSrc || v.src;
                    return src && src.includes('.mp4') && !prevUrls.includes(src);
                }});
                const isGenerating = !!document.querySelector('[aria-label*="생성 중"], .animate-spin, [role="progressbar"], button[aria-label*="중지"], button[aria-label*="Stop"]');
                return {{
                    videoCount: videos.length,
                    prevCount: prevUrls.length,
                    videoUrl: newVideo ? (newVideo.currentSrc || newVideo.src) : null,
                    isGenerating
                }};
            }}, {json.dumps(initial_urls)});
            console.log(JSON.stringify(res));
        }})();
        """

        out_video_path = self.result_dir / f"{clip_id}.mp4"
        max_wait = 180  # 3분 대기
        start_time = time.time()

        while time.time() - start_time < max_wait:
            time.sleep(4)
            ok, out = self.run_aside_repl(poll_script, timeout=15)
            if ok and "videoUrl" in out:
                try:
                    for line in out.split("\n"):
                        if line.startswith("{") and "videoUrl" in line:
                            data = json.loads(line)
                            url = data.get("videoUrl")
                            if url and "http" in url:
                                video_url = url
                                break
                except Exception:
                    pass

            if video_url:
                print(f"  🎬 Meta AI 비디오 생성 완료 감지! 다운로드 시작...")
                break
            else:
                elapsed = int(time.time() - start_time)
                print(f"     대기 중... ({elapsed}s)")

        if not video_url:
            raise TimeoutError(f"Meta AI 영상 생성 시간 초과 ({max_wait}초)")

        # 7) 비디오 다운로드
        req = urllib.request.Request(video_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(out_video_path, "wb") as f:
            shutil.copyfileobj(resp, f)

        print(f"  💾 비디오 저장 완료: {out_video_path} ({os.path.getsize(out_video_path):,} bytes)")

        # 8) 테일 프레임 추출
        print(f"  📸 {clip_id} 테일 프레임 추출 중 (다음 클립 체이닝용)...")
        tail_frame = self.extract_last_frame(clip_id, str(out_video_path))
        print(f"  ✨ 완료: {out_video_path} (다음 프레임: {tail_frame})")

        return {
            "clip_id": clip_id,
            "video_path": str(out_video_path),
            "tail_frame": tail_frame,
            "video_url": video_url
        }


MetaConnector = AsideMetaConnector


def main():
    parser = argparse.ArgumentParser(description="Aside Meta AI Video Connector")
    parser.add_argument("clip_id", help="생성할 클립 ID (예: S01, S02)")
    parser.add_argument("--project", default=None, help="프로젝트 디렉토리명 (기본값: session/now)")
    parser.add_argument("--account", default="u0", help="Aside 브라우저 계정/프로필 (기본값: u0 jatu)")
    args = parser.parse_args()

    connector = AsideMetaConnector(project_name=args.project, account=args.account)
    connector.generate_clip(args.clip_id)


if __name__ == "__main__":
    main()

