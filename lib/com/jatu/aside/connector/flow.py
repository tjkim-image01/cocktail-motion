"""Google Labs Flow - Aside 브라우저 전용 커넥터 (AsideFlowConnector).

주요 아키텍처:
1. Aside CLI & REPL (`aside repl` / `aside mcp`):
   - Aside 브라우저 내 활성 세션(Google 로그인 상태)에 직접 연결하여 CDP 및 DOM 제어를 수행합니다.
   - 캡처, OCR, 가상 키보드 지연 대신 CDP `DOM.setFileInputFiles`와 `Input.insertText`를 통해 100% 신뢰성 있게 동작합니다.
2. 자동화 파이프라인:
   - 클립별 프롬프트 자동 로드 (flow-object.md, flow.md 지원)
   - 규격 설정 검증: 동영상 · 프레임/소재 · 9:16/16:9 · 720p/360p · 10초 · x1
   - 시작 프레임 이미지 자동 감지 및 업로드/부착
   - 프롬프트 입력 및 [생성 시작] 클릭
   - 실시간 생성 진행률(0% ~ 100%) 모니터링
   - 완료 후 CDN 비디오 파일 자동 다운로드 (`result/{clip_id}.mp4`)
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
from pathlib import Path
from typing import Dict, Any, Optional, Union

ROOT_DIR = Path(__file__).resolve().parents[5]
ASIDE_BIN = os.path.expanduser("~/.local/bin/aside")
if not os.path.exists(ASIDE_BIN):
    ASIDE_BIN = shutil.which("aside") or "aside"


class AsideFlowConnector:
    name = "aside-flow"

    def __init__(self, project_name: Optional[str] = None, prompt_file: Optional[Union[str, Path]] = None, account: Optional[str] = None):
        self.project_name = project_name or self._resolve_current_project_name()
        self.project_dir = ROOT_DIR / "project" / self.project_name
        self.session_file = self.project_dir / "session.json"
        self.account = account or self._resolve_account()

        if prompt_file:
            self.prompts_file = Path(prompt_file).resolve()
        else:
            flow_obj = self.project_dir / "flow-object.md"
            flow_std = self.project_dir / "flow.md"
            if flow_obj.exists():
                self.prompts_file = flow_obj
            elif flow_std.exists():
                self.prompts_file = flow_std
            else:
                self.prompts_file = self.project_dir / "prompts" / "flow-prompts-basic.md"

        self.res_dir = self.project_dir / "res"
        self.result_dir = self.project_dir / "result"
        self.frames_dir = self.result_dir / ".frames"

        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)

        self.project_id, self.target_url = self._resolve_flow_project()

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
        return "s012"

    def _resolve_flow_project(self) -> tuple[Optional[str], str]:
        if not self.session_file.exists():
            return None, "https://flow.google.com"
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            projects = data.get("projects", {})
            pid = projects.get("flow") or data.get("projectId")
            url = data.get("projectUrl") or (f"https://flow.google.com/project/{pid}" if pid else "https://flow.google.com")
            return pid, url
        except Exception:
            return None, "https://flow.google.com"

    def run_aside_repl(self, script_code: str, timeout: int = 120) -> tuple[bool, str]:
        """Aside REPL을 통해 Playwright/CDP 코드를 실행합니다."""
        # 활성 상태인 이 프로젝트 Flow 탭에만 붙고, 없으면 새 탭을 연다.
        # 백그라운드 탭은 크롬이 얼려서 Page.enable 이 타임아웃나고, 활성 탭 폴백은 사용자가 보던 탭을 빼앗는다.
        pid = self.project_id or ""
        attach_flow_tab = (
            "(await (async () => { const _l = await listBrowserTabs(); "
            f"const _t = _l.find(t => t.active && '{pid}' && t.url.includes('{pid}')); "
            f"return _t ? attachBrowserTab(_t.targetId) : openTab({json.dumps(self.target_url)}); }})())"
        )
        script_code = script_code.replace("attachActiveBrowserTab()", attach_flow_tab)
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
                hasAccount: !!document.querySelector('[aria-label*="Google 계정"]')
            };
        });
        console.log(JSON.stringify(info));
        """
        ok, out = self.run_aside_repl(check_js, timeout=10)
        return ok and "Google 계정" in out

    def get_clip_info(self, clip_id: str) -> Dict[str, Any]:
        """지정된 클립(S01, S02, C01 등)의 프롬프트와 시작 프레임 이미지를 계산합니다."""
        if not self.prompts_file.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {self.prompts_file}")

        content = self.prompts_file.read_text(encoding="utf-8")
        pattern = rf"({re.escape(clip_id)}\s*[:.]\s*Duration\s+[0-9]+\s+seconds.*?)(?=```|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            raise ValueError(f"클립 '{clip_id}'의 프롬프트 블록을 찾지 못했습니다.")

        prompt = match.group(1).strip()

        # 1. flow-object.md 섹션 헤더/메타데이터에서 명시된 시작 파일 우선 확인
        section_pattern = rf"###\s+{re.escape(clip_id)}.*?(?=(?:###|\Z))"
        sec_match = re.search(section_pattern, content, re.DOTALL)
        explicit_file = None
        if sec_match:
            sec_text = sec_match.group(0)
            file_match = re.search(r"-\s*\*\*시작\s*파일\*\*:\s*`?([^`\r\n\(\)]+)`?", sec_text)
            if file_match:
                raw_path = file_match.group(1).strip()
                cand_path = Path(raw_path)
                if not cand_path.is_absolute():
                    cand_path = ROOT_DIR / cand_path
                if cand_path.exists():
                    explicit_file = cand_path

        if explicit_file:
            start_frame = explicit_file
        elif clip_id in ("C00", "S01"):
            for ext in (".png", ".jpeg", ".jpg"):
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
                if not prev_video.exists():
                    candidates = glob.glob(str(Path.home() / "Downloads" / f"*{prev_id}*.mp4"))
                    if candidates:
                        candidates.sort(key=os.path.getmtime, reverse=True)
                        shutil.copy2(candidates[0], str(prev_video))

                if prev_video.exists():
                    self.extract_last_frame(prev_id, str(prev_video))
                    start_frame = c1
                else:
                    start_frame = c1

        # 모드 판별 (소재 vs 프레임)
        is_ingredients = "Ingredients:" in prompt or "@char" in prompt or "@speaker" in prompt or "소재" in prompt
        mode = "소재" if is_ingredients else "프레임"

        # 해상도 판별
        # 생성 해상도: u1(hwangjiyoung1977)만 360p, 그 외 계정은 720p (다운로드는 항상 720p)
        resolution = "360p" if (self.account or "") == "u1" else "720p"
        if getattr(self, "gen_resolution", None):  # 실행 시 지정한 생성 해상도가 우선
            resolution = self.gen_resolution

        # 화면비 판별
        aspect_ratio = "9:16" if ("9:16" in prompt or "9:16" in content) else "16:9"

        # 재생시간 판별
        dur_match = re.search(r"Duration\s+([0-9]+)\s+seconds", prompt)
        duration = f"{dur_match.group(1)}초" if dur_match else "10초"

        # 소재 모드 레퍼런스 이미지 목록 결정
        ingredients = []
        if mode == "소재":
            # 1. 이전 클립의 테일 프레임 (예: S01_last.png) 최우선 등록 (Tail-to-Ingredient)
            if start_frame and os.path.exists(str(start_frame)):
                ingredients.append(str(start_frame))

            # 2. res 디렉토리 내 전용 소재 후보
            for cand_name in ["speaker.png", "char.png", "character.png", "background2.png", "background.png"]:
                cand_path = self.res_dir / cand_name
                if cand_path.exists() and str(cand_path) not in ingredients:
                    ingredients.append(str(cand_path))

            # 3. 프롬프트 내에 직접 언급된 이미지 파일명 확인 (예: basic.png 등)
            for m in re.findall(r"[\w\-]+\.(?:png|jpe?g)", prompt):
                for search_dir in [self.frames_dir, self.res_dir]:
                    cand = search_dir / m
                    if cand.exists() and str(cand) not in ingredients:
                        ingredients.append(str(cand))
                        break

            # 4. 아무것도 없으면 start_frame 추가
            if not ingredients and start_frame:
                ingredients.append(str(start_frame))

        return {
            "clip_id": clip_id,
            "project_name": self.project_name,
            "project_id": self.project_id,
            "prompt": prompt,
            "start_frame_path": str(start_frame),
            "ingredients": ingredients,
            "model": "Omni 1.1 Flash",
            "mode": mode,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "quantity": "x1",
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
        """Aside REPL/CDP를 사용하여 클립을 생성하고 다운로드까지 자동 완료합니다."""
        info = self.get_clip_info(clip_id)
        start_frame_path = info["start_frame_path"]
        prompt_text = info["prompt"]
        target_mode = info["mode"]
        target_res = info["resolution"]
        target_ratio = info["aspect_ratio"]
        ingredients = info.get("ingredients", [])

        print(f"\n🚀 [AsideFlow] {clip_id} 생성 파이프라인 가동")
        print(f"  • 대상 URL: {self.target_url}")
        print(f"  • 프롬프트 파일: {self.prompts_file.name}")
        print(f"  • 모드: 동영상 · {target_mode} · {target_ratio} · {target_res} · {info['duration']} · {info['model']}")
        if target_mode == "프레임":
            print(f"  • 시작 프레임: {start_frame_path}")
        elif target_mode == "소재":
            print(f"  • 레퍼런스 소재: {[os.path.basename(p) for p in ingredients]}")

        # 1. 파일 존재 여부 확인 (프레임 모드인 경우)
        if target_mode == "프레임" and not os.path.exists(start_frame_path):
            raise FileNotFoundError(f"시작 프레임 파일을 찾을 수 없습니다: {start_frame_path}")

        frame_filename = os.path.basename(start_frame_path) if target_mode == "프레임" else ""

        # 2. Aside REPL 자동화 스크립트 작성
        automation_script = f"""
        await (async () => {{
            const page = await attachActiveBrowserTab();

            // 0-1) 프로젝트 메인 캔버스 무조건 클린 리셋 (이전 컷 잔여 슬롯/칩 완전 초기화)
            await page.goto('{self.target_url}');
            await new Promise(r => setTimeout(r, 2500));

            // 0-2) 사전 크레딧 부족 상태 확인
            const preWarn = await page.evaluate(() => {{
                const warnBtn = document.querySelector('.prompt-warning-button, button[aria-label*="크레딧"], button[aria-label*="부족"]');
                return !!warnBtn;
            }});
            // 이 경고는 기본 설정(Veo 3.1 Lite 720p 등) 기준이라, 360p·Omni 로 바꾸면 사라질 수 있다 (2026-10-09 jatu015 u2·u4 오판).
            // 여기서는 기록만 하고, 실제 판정은 설정을 맞춘 뒤 생성 버튼 직전(6단계)에서 한다.
            if (preWarn) {{
                console.log('PRE_WARN:기본설정 기준 크레딧 경고 (설정 변경 후 재확인)');
            }}

            // 1) 팝업 및 쿠키 정리
            await page.evaluate(() => {{
                const cookieBtn = document.querySelector('.glue-cookie-notification-bar__accept');
                if (cookieBtn) cookieBtn.click();
                const backdrop = document.querySelector('.cdk-overlay-backdrop');
                if (backdrop) backdrop.click();
            }});
            await new Promise(r => setTimeout(r, 400));

            // 2) 항상 설정 패널을 열어 동영상/모드/비율/해상도/길이/개수 완벽 동기화
            await page.evaluate(async () => {{
                const settingsBtn = document.querySelector('.settings-trigger-button') || 
                                    document.querySelector('button[aria-label="설정 트리거"]') || 
                                    document.querySelector('button[aria-label*="Settings trigger"]');
                if (settingsBtn) {{
                    settingsBtn.click();
                    await new Promise(r => setTimeout(r, 600));
                }}
            }});

            // 2-0) 모델을 Omni 1.1 Flash로 명시 선택 (계정/새로고침에 따라 Veo 3.1 - Lite로 초기화되는 경우가 있음)
            {{
                // 동영상 탭이어야 모델 버튼이 보임
                await page.evaluate(() => {{
                    const pane = document.querySelector('.cdk-overlay-pane');
                    const v = pane && [...pane.querySelectorAll('mat-button-toggle')].find(t => t.innerText.includes('동영상') || t.innerText.includes('Video'));
                    if (v && !v.classList.contains('mat-button-toggle-checked')) (v.querySelector('button') || v).click();
                }});
                await new Promise(r => setTimeout(r, 600));
                const mbtn = page.locator('.cdk-overlay-pane button[aria-label="모델 제품군 선택"], .cdk-overlay-pane button[aria-label*="Select model"], .cdk-overlay-pane button[aria-label*="model"]');
                const curModel = async () => ((await mbtn.first().innerText().catch(() => '')) || '');
                // 선택 후 실제로 Omni가 됐는지 확인하고, 아니면 최대 3번까지 다시 시도 (메뉴가 늦게 뜨면 항목 클릭이 빗나감)
                for (let tries = 0; tries < 3 && (await mbtn.count()) && !(await curModel()).includes('Omni 1.1 Flash'); tries++) {{
                    const bb = await mbtn.first().boundingBox();
                    await page.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2);
                    // 메뉴 항목은 설정 창과 다른 오버레이에 뜨므로 페이지 전체에서 찾는다
                    const opt = page.locator('[role=menuitem]').filter({{ hasText: 'Omni 1.1 Flash' }}).first();
                    for (let w = 0; w < 10 && !(await opt.count()); w++) await new Promise(r => setTimeout(r, 300));
                    if (await opt.count()) {{
                        await opt.click();
                        await new Promise(r => setTimeout(r, 1000));
                    }} else {{
                        await page.keyboard.press('Escape');
                        await new Promise(r => setTimeout(r, 500));
                    }}
                }}
                console.log('MODEL_SELECTED:' + (await curModel()).replace(/\\s+/g, ' '));
            }}

            await page.evaluate(async ({{ mode, res, ratio, dur }}) => {{
                const pane = document.querySelector('.cdk-overlay-pane');
                if (!pane) return;

                const clickToggle = (label) => {{
                    const toggles = Array.from(pane.querySelectorAll('mat-button-toggle'));
                    const engMap = {{ '동영상': 'Video', '이미지': 'Image', '프레임': 'Frames', '소재': 'Ingredients', '10초': '10s', '8초': '8s', '6초': '6s', '4초': '4s' }};
                    const altLabel = engMap[label] || label;
                    const target = toggles.find(t => t.innerText.includes(label) || t.innerText.includes(altLabel));
                    if (target && !target.classList.contains('mat-button-toggle-checked')) {{
                        const btn = target.querySelector('button') || target;
                        btn.click();
                        return true;
                    }}
                    return false;
                }};

                // 동영상 전환
                if (clickToggle('동영상')) {{
                    await new Promise(r => setTimeout(r, 600));
                }}
                // 프레임 또는 소재
                clickToggle(mode);
                await new Promise(r => setTimeout(r, 300));

                // 비율
                clickToggle(ratio);
                await new Promise(r => setTimeout(r, 200));

                // 해상도
                clickToggle(res);
                await new Promise(r => setTimeout(r, 200));

                // 길이 (명세의 Duration: 4/6/8/10초)
                clickToggle(dur);
                await new Promise(r => setTimeout(r, 200));

                // 개수 (x1)
                const x1Toggle = Array.from(pane.querySelectorAll('mat-button-toggle')).find(t => t.innerText.trim() === 'x1');
                if (x1Toggle && !x1Toggle.classList.contains('mat-button-toggle-checked')) {{
                    (x1Toggle.querySelector('button') || x1Toggle).click();
                }}
                await new Promise(r => setTimeout(r, 200));

                // 모델 확인용 기록 (한국어 및 영어 UI 모두 대응)
                const modelBtn = pane.querySelector('button[aria-label="모델 제품군 선택"]') || 
                                 pane.querySelector('button[aria-label*="Select model"]') || 
                                 Array.from(pane.querySelectorAll('button')).find(b => b.innerText.includes('Omni') || b.innerText.includes('Flash') || b.innerText.includes('Veo'));
                window.__flowModel = (modelBtn ? modelBtn.innerText : (pane.innerText.includes('Omni 1.1 Flash') ? 'Omni 1.1 Flash' : '')).trim();

                // 닫기
                const settingsBtn = document.querySelector('.settings-trigger-button');
                if (settingsBtn && document.querySelector('.cdk-overlay-pane')) {{
                    settingsBtn.click();
                }}
                const backdrop = document.querySelector('.cdk-overlay-backdrop');
                if (backdrop) backdrop.click();
            }}, {{ mode: '{target_mode}', res: '{target_res}', ratio: '{target_ratio}', dur: '{info['duration']}' }});
            await new Promise(r => setTimeout(r, 600));

            // 2-1) 모델이 Omni 1.1 Flash가 아니면 생성 중단
            const flowModel = await page.evaluate(() => window.__flowModel || '');
            if (!flowModel.includes('Omni 1.1 Flash')) {{
                throw new Error('모델이 Omni 1.1 Flash가 아닙니다 (현재: ' + flowModel + '). Flow 설정에서 모델을 바꿔 주세요.');
            }}

            // 2-2) 프롬프트 텍스트 먼저 초기화 (반드시 이미지 부착 전에 수행하여 칩이 지워지는 것 방지!)
            await page.evaluate(() => {{
                const clearBtn = Array.from(document.querySelectorAll('button')).find(b => 
                    b.innerText.includes('프롬프트 지우기') || b.getAttribute('aria-label') === '프롬프트 지우기' ||
                    b.innerText.includes('Clear prompt') || b.getAttribute('aria-label')?.includes('Clear')
                );
                if (clearBtn) clearBtn.click();
                const el = document.querySelector('div.ProseMirror');
                if (el) {{
                    el.focus();
                    el.innerText = '';
                }}
            }});
            await new Promise(r => setTimeout(r, 400));

            // 3) 시작 프레임 이미지 확인 및 부착 (프레임 모드인 경우)
            if ('{target_mode}' === '프레임') {{
                const fname = '{frame_filename}';
                const pane = () => page.locator('.cdk-overlay-pane');
                // 업로드가 끝난 항목은 글자가 파일명과 정확히 같음 ('업로드 중' 표시가 없음)
                const readyIndex = () => page.evaluate((fn) => [...document.querySelectorAll('.cdk-overlay-pane .asset-item')].findIndex(e => e.innerText.trim() === fn), fname);
                const itemReady = () => ({{ count: async () => ((await readyIndex()) >= 0 ? 1 : 0) }});

                // 3-1) 시작 슬롯에 남은 이전 이미지를 지우고 '프레임 이미지 선택' 창 열기
                await page.evaluate(() => document.querySelector('.cdk-overlay-backdrop')?.click());
                await new Promise(r => setTimeout(r, 300));
                for (let c = 0; c < 3; c++) {{
                    const hasChip = await page.evaluate(() => !!document.querySelector('flow-prompt-box .frame-trigger img'));
                    if (!hasChip) break;
                    await page.locator('flow-prompt-box .frame-trigger').first().hover();
                    await new Promise(r => setTimeout(r, 300));
                    await page.evaluate(() => {{
                        const f = document.querySelector('flow-prompt-box .frame-trigger');
                        const x = f && [...f.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'cancel');
                        if (x) (x.closest('button') || x).click();
                    }});
                    await new Promise(r => setTimeout(r, 800));
                }}
                // 설정 창이 덜 닫힌 상태에서 누르면 선택 창이 안 열릴 수 있어 Esc 후 최대 3번 재시도
                for (let tries = 0; tries < 3 && !(await page.locator('.cdk-overlay-pane .asset-item').count()); tries++) {{
                    await page.keyboard.press('Escape');
                    await page.evaluate(() => document.querySelector('.cdk-overlay-backdrop')?.click());
                    await new Promise(r => setTimeout(r, 500));
                    const startChip = page.locator('button.empty-chip', {{ hasText: 'Start' }}).first();
                    if (await startChip.count()) {{
                        await startChip.click();
                    }} else {{
                        await page.locator('flow-prompt-box .frame-trigger').first().click();
                    }}
                    await new Promise(r => setTimeout(r, 1500));
                }}
                if (!(await page.locator('.cdk-overlay-pane').count())) throw new Error('프레임 이미지 선택 창이 열리지 않았습니다.');

                // 3-2) 창에 이미지가 없으면 창 안의 '미디어 업로드'로 업로드 (파일 input은 버튼 클릭 후 생김)
                if (!(await itemReady().count())) {{
                    await page._sendToTarget('Page.setInterceptFileChooserDialog', {{ enabled: true }});
                    const upBtn = page.locator('.cdk-overlay-pane button', {{ hasText: /미디어 업로드|Upload media|Upload/i }}).first();
                    if (await upBtn.count()) await upBtn.click();
                    await new Promise(r => setTimeout(r, 1000));
                    const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1 }});
                    const {{ nodeIds }} = await page._sendToTarget('DOM.querySelectorAll', {{ nodeId: root.nodeId, selector: 'input[type=file]' }});
                    let uploaded = false;
                    for (const nid of (nodeIds || [])) {{
                        await page._sendToTarget('DOM.setFileInputFiles', {{ files: ['{start_frame_path}'], nodeId: nid }});
                        console.log('UPLOAD_TRIGGERED');
                        for (let i = 0; i < 180; i++) {{
                            await new Promise(r => setTimeout(r, 1000));
                            if (await itemReady().count()) {{ uploaded = true; break; }}
                            if (i === 10 && !(await page.locator('.cdk-overlay-pane .asset-item', {{ hasText: fname }}).count())) break;
                        }}
                        if (uploaded) break;
                    }}
                    if (!uploaded) throw new Error('업로드 실패: ' + fname + '이 프레임 이미지 목록에 나타나지 않았습니다.');
                }}

                // 3-3) 파일명이 정확히 일치하는 항목 클릭 → Flow가 즉시 시작 슬롯에 붙이고 창을 닫음
                const idx = await readyIndex();
                await page.locator('.cdk-overlay-pane .asset-item').nth(idx).click();
                let attached = false;
                for (let k = 0; k < 10; k++) {{
                    await new Promise(r => setTimeout(r, 500));
                    attached = await page.evaluate(() => !!document.querySelector('flow-prompt-box .frame-trigger img'));
                    if (attached) break;
                }}
                if (!attached && await pane().count()) {{
                    // 구버전 UI: 창이 남아 있으면 '프롬프트에 추가'
                    await page.locator('.cdk-overlay-pane button', {{ hasText: '프롬프트에 추가' }}).first().click();
                    await new Promise(r => setTimeout(r, 1000));
                }}
                console.log('ATTACHED_ASSET:' + fname);
                await page.evaluate(() => document.querySelector('.cdk-overlay-backdrop')?.click());
                await new Promise(r => setTimeout(r, 400));

                // 부착 검증 (최대 5초 대기: 빈 시작 버튼이 없고 이미지가 부착되었는지 엄격 확인)
                let verified = false;
                for (let k = 0; k < 10; k++) {{
                    await new Promise(r => setTimeout(r, 500));
                    verified = await page.evaluate(() => {{
                        const box = document.querySelector('flow-prompt-box');
                        if (!box) return false;
                        const emptyStart = Array.from(box.querySelectorAll('button.empty-chip')).some(b => b.innerText.trim() === '시작');
                        const chip = box.querySelector('.frame-trigger img, .chip-container img, flow-image-ingredient-chip img');
                        return !emptyStart && !!chip;
                    }});
                    if (verified) break;
                }}
                if (!verified) {{
                    throw new Error('검증 실패: 시작 프레임 이미지가 Flow 에디터에 첨부되지 않았습니다 (빈 시작 슬롯 감지).');
                }}
            }}

            // 3-2) 소재 모드인 경우: 소재 칩 부착
            if ('{target_mode}' === '소재') {{
                const targetFiles = {json.dumps(ingredients)};
                for (let idx = 0; idx < targetFiles.length; idx++) {{
                    const filePath = targetFiles[idx];
                    const fname = filePath.split('/').pop();

                    const currentChips = await page.evaluate(() => {{
                        return document.querySelectorAll('flow-prompt-box .chip-container, flow-prompt-box .chip').length;
                    }});

                    if (currentChips <= idx) {{
                        // 소재 추가 버튼 클릭
                        await page.evaluate(() => {{
                            const addBtn = document.querySelector('button[aria-label="프롬프트 상자에 소재 추가"]');
                            if (addBtn) addBtn.click();
                        }});
                        await new Promise(r => setTimeout(r, 800));

                        // 갤러리에 있는지 확인
                        let foundInGallery = await page.evaluate((fn) => {{
                            const items = Array.from(document.querySelectorAll('.asset-item, .cdk-overlay-pane button, [role=option]'));
                            const opt = items.find(o => o.innerText.includes(fn));
                            if (opt) {{
                                opt.click();
                                return true;
                            }}
                            return false;
                        }}, fname);

                        // 갤러리에 없으면 업로드
                        if (!foundInGallery) {{
                            await page._sendToTarget('Page.setInterceptFileChooserDialog', {{ enabled: true }});
                            await page.evaluate(() => {{
                                const upBtn = document.querySelector('.sidebar-upload-btn, button[aria-label="미디어 업로드"]');
                                if (upBtn) upBtn.click();
                            }});
                            await new Promise(r => setTimeout(r, 500));

                            let fileInputNodeId = null;
                            for (let attempt = 0; attempt < 10; attempt++) {{
                                const {{ root }} = await page._sendToTarget('DOM.getDocument', {{ depth: -1 }});
                                const {{ nodeIds }} = await page._sendToTarget('DOM.querySelectorAll', {{
                                    nodeId: root.nodeId,
                                    selector: 'input[type=file]'
                                }});
                                if (nodeIds && nodeIds.length > 0) {{
                                    fileInputNodeId = nodeIds[0];  // 첫 번째 input만 실제 업로드가 동작함
                                    break;
                                }}
                                await new Promise(r => setTimeout(r, 300));
                            }}

                            if (fileInputNodeId) {{
                                await page._sendToTarget('DOM.setFileInputFiles', {{
                                    files: [filePath],
                                    nodeId: fileInputNodeId
                                }});
                                console.log('UPLOAD_TRIGGERED_INGREDIENT:' + fname);
                            }}

                            for (let i = 0; i < 60; i++) {{
                                await new Promise(r => setTimeout(r, 1000));
                                const clicked = await page.evaluate((fn) => {{
                                    const items = Array.from(document.querySelectorAll('.asset-item, .cdk-overlay-pane button, [role=option]'));
                                    const opt = items.find(o => o.innerText.includes(fn) && !o.innerText.includes('업로드 중'));
                                    if (opt) {{
                                        opt.click();
                                        return true;
                                    }}
                                    return false;
                                }}, fname);
                                if (clicked) {{
                                    foundInGallery = true;
                                    break;
                                }}
                            }}
                        }}
                        await new Promise(r => setTimeout(r, 600));

                        // 선택 후 '프롬프트에 추가' 버튼 클릭
                        await page.evaluate(() => {{
                            const btns = Array.from(document.querySelectorAll('.detail-add-to-prompt-btn, .cdk-overlay-pane button'));
                            const addBtn = btns.find(b => b.innerText.includes('프롬프트에 추가'));
                            if (addBtn) addBtn.click();
                        }});
                        await new Promise(r => setTimeout(r, 800));

                        // 혹시 오버레이가 아직 열려있으면 닫기
                        await page.evaluate(() => {{
                            const backdrop = document.querySelector('.cdk-overlay-backdrop');
                            if (backdrop) backdrop.click();
                        }});
                        await new Promise(r => setTimeout(r, 400));
                    }}
                }}

                // 소재 칩 첨부 검증
                let ingVerified = false;
                for (let k = 0; k < 10; k++) {{
                    await new Promise(r => setTimeout(r, 500));
                    ingVerified = await page.evaluate(() => {{
                        const box = document.querySelector('flow-prompt-box');
                        return box ? box.querySelectorAll('.chip-container, .chip').length > 0 : false;
                    }});
                    if (ingVerified) break;
                }}
                if (!ingVerified) {{
                    throw new Error('검증 실패: 소재 모드 레퍼런스 이미지가 Flow 에디터에 첨부되지 않았습니다.');
                }}
            }}

            // 4) 프롬프트 텍스트 입력 (주의: clearBtn을 누르면 기부착된 시작 프레임/소재 칩이 날아가므로 절대 누르지 않음)
            // 편집기에 이전 프롬프트가 남아 있으면 이어 붙여지므로(2026-10-08 jatu005: K13 문장 뒤에 TS01 이 붙음),
            // 편집기 안의 글자만 전부 선택해 두고 insertText 로 덮어쓴다 (시작 프레임 칩은 편집기 밖이라 안전)
            await page.evaluate(() => {{
                const el = document.querySelector('div.ProseMirror');
                if (!el) return;
                el.focus();
                const range = document.createRange();
                range.selectNodeContents(el);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }});
            await new Promise(r => setTimeout(r, 300));

            const promptText = {json.dumps(prompt_text)};
            await page._sendToTarget('Input.insertText', {{ text: promptText }});
            await new Promise(r => setTimeout(r, 800));
            const typed = await page.evaluate(() => (document.querySelector('div.ProseMirror')?.innerText || '').trim());
            if (!typed.startsWith(promptText.slice(0, 40))) {{
                throw new Error('검증 실패: 프롬프트 편집기 내용이 이번 클립 프롬프트로 시작하지 않습니다: ' + typed.slice(0, 80));
            }}

            // 5) 프레임 모드 최종 부착 상태 엄격 검증 (생성 시작 버튼 누르기 직전 재확인)
            if ('{target_mode}' === '프레임') {{
                const finalCheck = await page.evaluate(() => {{
                    const box = document.querySelector('flow-prompt-box');
                    if (!box) return false;
                    const emptyStart = Array.from(box.querySelectorAll('button.empty-chip')).some(b => b.innerText.trim() === '시작');
                    const chip = box.querySelector('.frame-trigger img, .chip-container img, flow-image-ingredient-chip img');
                    return !emptyStart && !!chip;
                }});
                if (!finalCheck) {{
                    throw new Error('최종 검증 실패: 생성 시작 직전 시작 프레임 이미지가 Flow 슬롯에서 누락되었습니다.');
                }}
            }}

            // 6) 생성 시작 버튼 또는 크레딧 소진 경고 확인
            const clickResult = await page.evaluate(() => {{
                const warnBtn = document.querySelector('.prompt-warning-button, button[aria-label*="크레딧"], button[aria-label*="부족"]');
                if (warnBtn) return 'OUT_OF_CREDITS';

                const b = Array.from(document.querySelectorAll('button')).find(el => el.innerText.includes('생성 시작') || el.getAttribute('aria-label') === '생성 시작' || el.innerText.includes('arrow_forward'));
                if (b && !b.disabled) {{
                    b.click();
                    return 'CLICKED';
                }}
                return b ? (b.disabled ? 'DISABLED' : 'FOUND') : 'NOT_FOUND';
            }});

            console.log('GENERATE_RESULT:' + clickResult);
        }})();
        """

        print("  ⏳ Aside 브라우저를 통해 프롬프트 입력 및 생성 트리거 중...")
        ok, out = self.run_aside_repl(automation_script, timeout=180)
        if "OUT_OF_CREDITS" in out:
            print("\n🚨 [Flow 경고] 크레딧(포인트)이 모두 소진되었습니다! (빨간 경고 버튼 감지)")
            raise RuntimeError("🚨 [포인트 소진] Google Flow 계정의 포인트가 모두 소진되어 생성을 진행할 수 없습니다. 포인트를 충전하거나 계정을 전환해주세요.")

        if not ok or "GENERATE_RESULT:CLICKED" not in out:
            raise RuntimeError(f"클립 생성 트리거 실패: {out}")

        print(f"  ✅ {clip_id} 영상 생성이 시작되었습니다!")

        if not wait_completion:
            return info

        # 3. 비디오 렌더링 완료 대기 및 다운로드
        print("  ⏳ 비디오 렌더링 진행률 모니터링 중...")
        video_url = self._wait_and_fetch_video_url(clip_id)
        if not video_url:
            raise RuntimeError("비디오 생성 완료 감지 실패 또는 URL 수집 실패")

        # 4. 비디오 다운로드
        dest_video = self.result_dir / f"{clip_id}.mp4"
        if not video_url.startswith("file://"):
            print(f"  📥 생성된 영상 다운로드 중 -> {dest_video}")
            curl_cmd = ["curl", "-sSL", "-o", str(dest_video), video_url]
            subprocess.run(curl_cmd, check=True)

        # 5. 테일 프레임 추출
        print(f"  📸 {clip_id} 테일 프레임 추출 중 (다음 클립 체이닝용)...")
        last_frame = self.extract_last_frame(clip_id, str(dest_video))
        print(f"  ✨ 완료: {dest_video} (다음 프레임: {last_frame})")

        # 6. 다음 클립 생성을 위해 에디터 초기화
        print("  🧹 다음 클립 생성을 위해 에디터 리셋 중...")
        reset_script = f"""
        const page = await attachActiveBrowserTab();
        await page.goto('{self.target_url}');
        await new Promise(r => setTimeout(r, 3000));
        """
        self.run_aside_repl(reset_script, timeout=15)

        return info

    @staticmethod
    def _frame_diff(image_path: str, video_path: str) -> float:
        """시작 이미지와 영상 첫 프레임의 평균 픽셀 차이(0~255). 같은 컷이면 약 10, 다른 그림이면 40 이상."""
        def px(src, video):
            cmd = ["ffmpeg", "-v", "error"] + (["-ss", "0.05"] if video else []) + [
                "-i", src, "-frames:v", "1", "-vf", "scale=18:32", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            return subprocess.run(cmd, capture_output=True, check=True).stdout
        a, b = px(image_path, False), px(video_path, True)
        return sum(abs(x - y) for x, y in zip(a, b)) / max(1, min(len(a), len(b)))

    def _wait_and_fetch_video_url(self, clip_id: str, max_wait_sec: int = 900) -> Optional[str]:
        """이 클립의 진행 타일이 끝날 때까지 기다린 뒤, 첫 프레임이 시작 이미지와 같은 영상만 받아 저장한다.

        이전에는 완료 후 맨 앞 영상 타일을 받았는데, 프로젝트에 남아 있던 옛 영상을 받는 일이 있었다.
        그래서 (1) 프롬프트 글자로 이 클립의 진행 타일을 추적하고 (2) 받은 영상의 첫 프레임을 시작 이미지와 비교한다.
        """
        start_image = self.get_clip_info(clip_id)["start_frame_path"]
        tag = f"{clip_id} :"
        poll_script = """
        const page = await attachActiveBrowserTab();
        const res = await page.evaluate((tag) => {
            const tiles = Array.from(document.querySelectorAll('flow-tile-container'));
            return tiles.slice(0, 12).map((t, i) => {
                const text = t.innerText.replace(/\\s+/g, ' ');
                const m = text.match(/(\\d+)%/);
                return { i, mine: text.includes(tag), pct: m ? m[1] : null,
                         failed: /실패|오류|failed|error|정책|policy/i.test(text) && text.includes(tag),
                         video: !!t.querySelector('flow-video-tile') };
            });
        }, '__TAG__');
        console.log('TILES_JSON:' + JSON.stringify(res));
        """.replace("__TAG__", tag)
        dl_template = """
        const p = await attachActiveBrowserTab();
        await p.evaluate(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('완료') || b.getAttribute('aria-label')?.includes('뒤로')); if (b) b.click(); });
        await sleep(800);
        const tiles = p.locator('flow-tile-container');
        const tile = tiles.nth(__IDX__).locator('flow-video-tile').first();
        if (!(await tile.count())) { console.log('NO_VIDEO_TILE'); }
        else {
          await tile.click(); await sleep(1800);
          const dlPromise = p.waitForEvent('download', { timeout: 100000 }).catch(() => null);  // 720p 업스케일은 준비에 1분 이상 걸림
          await p.evaluate(() => { const btn = document.querySelector('button[aria-label="미디어 다운로드"]'); if (btn) btn.click(); });
          await sleep(700);
          await p.evaluate(() => {
            const items = Array.from(document.querySelectorAll('[role="menuitem"], button, mat-list-item'));
            const t = __DL_PICK__;
            if (t) t.click();
          });
          const download = await dlPromise;
          if (download) { const out = path.join(pwd, '__CLIP__-try__IDX__.mp4'); await download.saveAs(out); console.log('ASIDE_DOWNLOAD_SAVED:' + out); }
          await p.evaluate(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('완료') || b.getAttribute('aria-label')?.includes('뒤로')); if (b) b.click(); });
        }
        """
        # 360p 생성은 720p 업스케일이 오래 걸려 30초 안에 안 받아지므로 '원본 크기'를 먼저 고른다 (download_original=True)
        if getattr(self, "download_original", False):
            pick = "items.find(el => el.innerText.includes('원본 크기')) || items.find(el => el.innerText.includes('720p'))"
        else:
            pick = "items.find(el => el.innerText.includes('720p')) || items.find(el => el.innerText.includes('원본 크기'))"
        dl_template = dl_template.replace("__DL_PICK__", pick)
        dest_video = self.result_dir / f"{clip_id}.mp4"
        start_time = time.time()
        seen_mine, last_pct, mine_idx = False, None, 0
        while time.time() - start_time < max_wait_sec:
            ok, out = self.run_aside_repl(poll_script, timeout=25)
            tiles = None
            if ok and "TILES_JSON:" in out:
                try:
                    tiles = json.loads(out.split("TILES_JSON:")[1].strip().split("\n")[0])
                except Exception:
                    tiles = None
            if tiles is None:
                time.sleep(5)
                continue
            mine = [t for t in tiles if t["mine"]]
            if any(t["failed"] for t in mine):
                raise RuntimeError(f"{clip_id} Flow 생성 실패 표시가 떴습니다 (정책·오류)")
            running = [t for t in mine if t["pct"] is not None]
            if running:
                seen_mine, mine_idx = True, running[0]["i"]
                if running[0]["pct"] != last_pct:
                    last_pct = running[0]["pct"]
                    print(f"     진행률: {last_pct}% (타일 {mine_idx})", flush=True)
                time.sleep(8)
                continue
            if not seen_mine and time.time() - start_time < 120:
                time.sleep(5)  # 아직 이 클립의 진행 타일이 안 보임
                continue
            # 완료로 보임: 추적한 위치부터 가까운 영상 타일을 받아 첫 프레임을 확인
            print("     렌더링 완료 감지 → 첫 프레임이 시작 이미지와 같은 영상을 찾아 다운로드", flush=True)
            order = [mine_idx] + [t["i"] for t in tiles if t["video"] and t["i"] != mine_idx]
            for idx in order[:6]:
                ok_dl, out_dl = self.run_aside_repl(dl_template.replace("__IDX__", str(idx)).replace("__CLIP__", clip_id), timeout=140)
                if "ASIDE_DOWNLOAD_SAVED:" not in out_dl:
                    continue
                saved = out_dl.split("ASIDE_DOWNLOAD_SAVED:")[1].strip().split("\n")[0]
                if not os.path.exists(saved) or os.path.getsize(saved) < 100000:
                    continue
                d = self._frame_diff(start_image, saved)
                print(f"     타일 {idx}: 첫 프레임 차이 {d:.1f}", flush=True)
                if d <= 18:  # 같은 컷은 보통 5~12. 28 은 비슷한 어두운 장면(다른 컷)까지 통과시켰다 (2026-09-30)
                    shutil.move(saved, str(dest_video))
                    return f"file://{dest_video}"
                os.remove(saved)
            print("     시작 이미지와 같은 영상을 아직 못 찾음 → 계속 대기", flush=True)
            time.sleep(20)
        return None

    def create_video(self, clip_id: str) -> Dict[str, Any]:
        return self.generate_clip(clip_id)


FlowConnector = AsideFlowConnector


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aside Flow Connector")
    parser.add_argument("clip_ids", nargs="*", default=["S01"], help="Clip IDs to generate (e.g. S01, S02)")
    parser.add_argument("--project", "-p", default=None, help="Project name (e.g. s012)")
    parser.add_argument("--file", "-f", default=None, help="Prompt file path (e.g. project/s012/flow-object.md)")
    parser.add_argument("--account", "-a", default=None, help="Aside account id (e.g. u1, u2)")
    args = parser.parse_args()

    connector = AsideFlowConnector(project_name=args.project, prompt_file=args.file, account=args.account)
    for t in args.clip_ids:
        print(f"\n==========================================")
        print(f"▶▶ 클립 {t} 생성 파이프라인 시작")
        print(f"==========================================")
        connector.generate_clip(t)
        print(f"✅ 클립 {t} 완료!\n")
