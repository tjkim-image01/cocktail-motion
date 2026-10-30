"""Google Flow Music connector for Aside Browser sessions.

Creates an instrumental song through www.flowmusic.app and downloads the
result as WAV. The browser account is selected with Aside's ``--account``
option, matching the account handling used by connector/flow.py.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Union


ROOT_DIR = Path(__file__).resolve().parents[5]
ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"

FLOW_MUSIC_URL = "https://www.flowmusic.app"


class AsideFlowMusicConnector:
    name = "aside-flow-music"

    def __init__(
        self,
        project_name: Optional[str] = None,
        prompt_file: Optional[Union[str, Path]] = None,
        account: Optional[str] = None,
        output_file: Optional[Union[str, Path]] = None,
    ):
        self.project_name = project_name or self._resolve_current_project_name()
        self.project_dir = ROOT_DIR / "project" / self.project_name
        self.session_file = self.project_dir / "session.json"
        self.account = account or self._resolve_account() or "u1"
        self.prompt_file = (
            Path(prompt_file).resolve()
            if prompt_file
            else self.project_dir / "flow-music.md"
        )
        self.output_file = (
            Path(output_file).resolve()
            if output_file
            else self.project_dir / "res" / "bgm-flow-music.wav"
        )
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def _resolve_current_project_name(self) -> str:
        now_file = ROOT_DIR / "session" / "now"
        if now_file.exists():
            name = now_file.read_text(encoding="utf-8").strip()
            if name:
                return name
        return "jatu002"

    def _resolve_account(self) -> Optional[str]:
        if not self.session_file.exists():
            return None
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            return data.get("account")
        except Exception:
            return None

    def get_prompt(self) -> str:
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Flow Music 프롬프트 파일이 없습니다: {self.prompt_file}")
        text = self.prompt_file.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        prompt = "\n".join(lines).strip()
        if not prompt:
            raise ValueError(f"Flow Music 프롬프트가 비어 있습니다: {self.prompt_file}")
        return prompt

    def run_aside_repl(self, script_code: str, timeout: int = 180) -> tuple[bool, str]:
        cmd = [ASIDE_BIN, "--account", self.account, "repl", script_code]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
            return proc.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Aside Flow Music 실행 시간 초과"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _extract_marker(output: str, marker: str) -> Optional[str]:
        if marker not in output:
            return None
        return output.split(marker, 1)[1].strip().splitlines()[0]

    def _save_audio_resource(self, url: str) -> None:
        source_file = self.output_file.with_suffix(".m4a")
        subprocess.run(["curl", "-fL", "-o", str(source_file), url], check=True)
        if self.output_file.suffix.lower() == ".m4a":
            if source_file != self.output_file:
                shutil.copy2(source_file, self.output_file)
            return
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(source_file), "-c:a", "pcm_s16le", str(self.output_file),
            ],
            check=True,
        )

    def generate(self, max_wait_sec: int = 600) -> dict[str, Any]:
        prompt = self.get_prompt()
        destination = str(self.output_file)
        script = f"""
        await (async () => {{
            const page = await openTab('{FLOW_MUSIC_URL}');
            await sleep(2500);

            const agreeBtn = page.getByRole('button', {{ name: '동의함' }});
            if (await agreeBtn.count()) {{
                try {{ await agreeBtn.first().click(); await sleep(500); }} catch (_) {{}}
            }}

            let chat = page.locator('textarea[aria-label="Chat message"]');
            for (let attempt = 0; attempt < 20 && !(await chat.count()); attempt++) {{
                await sleep(1000);
                chat = page.locator('textarea[aria-label="Chat message"]');
            }}
            if (!(await chat.count())) throw new Error('Flow Music 채팅 입력창을 찾지 못했습니다: ' + page.url());
            const existingTracks = await page.locator('button[aria-label^="More options for"]').count();
            const initialAudioResources = await page.evaluate(() =>
                performance.getEntriesByType('resource')
                    .map(entry => entry.name)
                    .filter(url => /producer-app-public\\/clips\\/.*\\.m4a(?:$|\\?)/.test(url))
            );
            await chat.fill({json.dumps(prompt)});
            await sleep(500);
            const send = page.locator('button[aria-label="Send message"]');
            await send.click();
            console.log('FLOW_MUSIC_SENT');

            const deadline = Date.now() + {int(max_wait_sec) * 1000};
            let more = null;
            while (Date.now() < deadline) {{
                await sleep(3000);
                const candidates = page.locator('button[aria-label^="More options for"]');
                const candidateCount = await candidates.count();
                if (candidateCount > existingTracks) {{
                    more = candidates.nth(candidateCount - 1);
                    break;
                }}
            }}
            if (!more) throw new Error('Flow Music 생성 완료를 제한 시간 안에 감지하지 못했습니다.');

            const label = await more.getAttribute('aria-label');
            const title = (label || '').replace(/^More options for\\s*/, '') || 'flow-music';
            console.log('FLOW_MUSIC_SESSION:' + page.url());
            console.log('FLOW_MUSIC_TITLE:' + title);

            let audioResource = null;
            for (let attempt = 0; attempt < 60 && !audioResource; attempt++) {{
                audioResource = await page.evaluate((known) => {{
                    const resources = performance.getEntriesByType('resource').map(entry => entry.name);
                    return resources.reverse().find(url =>
                        /producer-app-public\\/clips\\/.*\\.m4a(?:$|\\?)/.test(url) && !known.includes(url)
                    ) || null;
                }}, initialAudioResources);
                if (!audioResource) await sleep(1000);
            }}
            if (audioResource) {{
                console.log('FLOW_MUSIC_RESOURCE:' + audioResource);
                return;
            }}

            await more.click();
            const downloadMenu = page.getByRole('menuitem', {{ name: 'Download', exact: true }});
            await downloadMenu.hover();
            await sleep(500);

            const wav = page.getByRole('menuitem', {{ name: 'WAV', exact: true }});
            const downloadPromise = page.waitForEvent('download', {{ timeout: 90000 }});
            await wav.click();
            const download = await downloadPromise;
            await download.saveAs({json.dumps(destination)});
            console.log('FLOW_MUSIC_SAVED:' + {json.dumps(destination)});
        }})();
        """
        ok, output = self.run_aside_repl(script, timeout=max_wait_sec + 120)
        resource_url = self._extract_marker(output, "FLOW_MUSIC_RESOURCE:")
        if ok and resource_url:
            self._save_audio_resource(resource_url)
        if not ok or ("FLOW_MUSIC_SAVED:" not in output and not resource_url):
            raise RuntimeError(f"Flow Music 생성/다운로드 실패:\n{output}")
        return {
            "project": self.project_name,
            "account": self.account,
            "session_url": self._extract_marker(output, "FLOW_MUSIC_SESSION:"),
            "title": self._extract_marker(output, "FLOW_MUSIC_TITLE:"),
            "output_file": str(self.output_file),
            "prompt": prompt,
        }

    def download_existing(self, session_url: str, title: Optional[str] = None) -> dict[str, Any]:
        destination = str(self.output_file)
        title_selector = json.dumps(f"More options for {title}") if title else "null"
        script = f"""
        await (async () => {{
            const page = await openTab({json.dumps(session_url)});
            await sleep(2500);
            let directResource = null;
            for (let attempt = 0; attempt < 15; attempt++) {{
                directResource = await page.evaluate(() => {{
                    const resources = performance.getEntriesByType('resource').map(entry => entry.name);
                    return resources.reverse().find(url => /producer-app-public\\/clips\\/.*\\.m4a(?:$|\\?)/.test(url)) || null;
                }});
                if (directResource) break;
                await sleep(1000);
            }}
            if (directResource) {{
                console.log('FLOW_MUSIC_TITLE:' + ({json.dumps(title or 'flow-music')}));
                console.log('FLOW_MUSIC_RESOURCE:' + directResource);
                return;
            }}
            let more;
            const exactLabel = {title_selector};
            if (exactLabel) more = page.locator(`button[aria-label="${{exactLabel}}"]`).first();
            else more = page.locator('button[aria-label^="More options for"]').first();
            if (!(await more.count())) throw new Error('다운로드할 Flow Music 곡을 찾지 못했습니다.');
            const label = await more.getAttribute('aria-label');
            const trackTitle = (label || '').replace(/^More options for\\s*/, '') || 'flow-music';
            const audioResource = await page.evaluate(() => {{
                const resources = performance.getEntriesByType('resource').map(entry => entry.name);
                return resources.reverse().find(url => /producer-app-public\\/clips\\/.*\\.m4a(?:$|\\?)/.test(url)) || null;
            }});
            if (audioResource) {{
                console.log('FLOW_MUSIC_TITLE:' + trackTitle);
                console.log('FLOW_MUSIC_RESOURCE:' + audioResource);
                return;
            }}
            await more.click();
            const downloadMenu = page.getByRole('menuitem', {{ name: 'Download', exact: true }});
            await downloadMenu.hover();
            await sleep(500);
            const wav = page.getByRole('menuitem', {{ name: 'WAV', exact: true }});
            const downloadPromise = page.waitForEvent('download', {{ timeout: 90000 }});
            await wav.click();
            const download = await downloadPromise;
            await download.saveAs({json.dumps(destination)});
            console.log('FLOW_MUSIC_TITLE:' + trackTitle);
            console.log('FLOW_MUSIC_SAVED:' + {json.dumps(destination)});
        }})();
        """
        ok, output = self.run_aside_repl(script, timeout=150)
        resource_url = self._extract_marker(output, "FLOW_MUSIC_RESOURCE:")
        if ok and resource_url:
            self._save_audio_resource(resource_url)
        if not ok or ("FLOW_MUSIC_SAVED:" not in output and not resource_url):
            raise RuntimeError(f"기존 Flow Music 다운로드 실패:\n{output}")
        return {
            "project": self.project_name,
            "account": self.account,
            "session_url": session_url,
            "title": self._extract_marker(output, "FLOW_MUSIC_TITLE:"),
            "output_file": str(self.output_file),
        }


FlowMusicConnector = AsideFlowMusicConnector


def main() -> None:
    parser = argparse.ArgumentParser(description="Aside Google Flow Music Connector")
    parser.add_argument("--project", "-p", default=None, help="Project name")
    parser.add_argument("--file", "-f", default=None, help="Music prompt Markdown file")
    parser.add_argument("--account", "-a", default=None, help="Aside account id, e.g. u1")
    parser.add_argument("--output", "-o", default=None, help="Destination WAV path")
    parser.add_argument("--session-url", default=None, help="Download an existing generated song")
    parser.add_argument("--title", default=None, help="Existing song title")
    args = parser.parse_args()

    connector = AsideFlowMusicConnector(
        project_name=args.project,
        prompt_file=args.file,
        account=args.account,
        output_file=args.output,
    )
    if args.session_url:
        result = connector.download_existing(args.session_url, args.title)
    else:
        result = connector.generate()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
