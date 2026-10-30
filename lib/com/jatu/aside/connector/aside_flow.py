"""Aside Flow Connector.
Aside 브라우저와 연동하여 Google Flow 영상 생성을 지시하고 프레임 체이닝을 관리합니다.
"""

import os
import re
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[5]


class AsideFlowConnector:
    def __init__(self, project_name: str = "mh003"):
        self.project_name = project_name
        self.project_dir = ROOT_DIR / "project" / project_name
        self.prompts_file = self.project_dir / "prompts" / "flow-prompts-basic.md"
        self.res_dir = self.project_dir / "res"
        self.result_dir = self.project_dir / "result"
        self.frames_dir = self.result_dir / ".frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    def get_clip_info(self, clip_id: str) -> Dict[str, Any]:
        """지정된 클립 ID(C01, C02 등)의 프롬프트 및 설정 정보를 추출합니다."""
        if not self.prompts_file.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {self.prompts_file}")

        content = self.prompts_file.read_text(encoding="utf-8")
        
        # 클립 코드블록 추출
        pattern = rf"({clip_id}\s*:\s*Duration\s+[0-9]+\s+seconds.*?)(?=```|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            raise ValueError(f"클립 '{clip_id}'의 프롬프트를 찾을 수 없습니다.")

        prompt = match.group(1).strip()

        # 시작 프레임 계산 (C00 -> basic.png, C01 -> C00_last.png, C02 -> C01_last.png ...)
        if clip_id == "C00":
            start_frame = self.res_dir / "basic.png"
        else:
            prev_num = int(clip_id[1:]) - 1
            prev_id = f"C{prev_num:02d}"
            # C00_last.png 또는 C00last.png 탐색
            candidate_1 = self.frames_dir / f"{prev_id}_last.png"
            candidate_2 = self.frames_dir / f"{prev_id}last.png"
            if candidate_1.exists():
                start_frame = candidate_1
            elif candidate_2.exists():
                start_frame = candidate_2
            else:
                # 기본 basic.png 대체
                start_frame = candidate_1

        return {
            "clip_id": clip_id,
            "project_name": self.project_name,
            "prompt": prompt,
            "start_frame_path": str(start_frame),
            "model": "Omni 1.1 Flash",
            "duration": "10초" if clip_id != "C10" else "3초",
            "resolution": "360p",
            "aspect_ratio": "16:9",
            "quantity": "x1",
        }

    def build_chat_command(self, clip_id: str) -> str:
        """Aside AI 채팅창에 주입할 표준 지시문 문자열을 생성합니다."""
        info = self.get_clip_info(clip_id)
        start_frame_exists = os.path.exists(info["start_frame_path"])
        frame_note = f" (존재 확인됨)" if start_frame_exists else " (생성 후 전달 필요)"

        msg = (
            f"Google Flow에서 {clip_id} 비디오 생성을 진행해줘.\n\n"
            f"[설정 지침]\n"
            f"- 모드: 동영상 · 프레임 (Frames to Video)\n"
            f"- 모델: {info['model']}\n"
            f"- 해상도: {info['resolution']}\n"
            f"- 길이: {info['duration']}\n"
            f"- 화면비: {info['aspect_ratio']}\n"
            f"- 수량: {info['quantity']}\n"
            f"- [시작] 프레임 이미지: {info['start_frame_path']}{frame_note}\n\n"
            f"[프롬프트]\n"
            f"{info['prompt']}\n\n"
            f"위 내용대로 Flow 웹페이지의 시작 프레임을 첨부하고 프롬프트를 입력한 뒤 생성을 실행해줘."
        )
        return msg

    def inject_to_aside_chat(self, clip_id: str) -> bool:
        """Aside 브라우저를 활성화하고 클립보드를 통해 Aside 채팅/명령창에 지시문을 전달합니다."""
        command_text = self.build_chat_command(clip_id)
        
        # 1. 클립보드에 복사
        process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        process.communicate(command_text.encode("utf-8"))

        # 2. AppleScript로 Aside 활성화 및 창 포커스
        script = """
        tell application "Aside" to activate
        delay 0.5
        tell application "System Events"
            tell process "Aside"
                set frontmost to true
            end tell
        end tell
        """
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return res.returncode == 0

    def extract_last_frame(self, clip_id: str, video_path: Optional[str] = None) -> str:
        """완료된 클립 영상에서 마지막 프레임을 추출하여 다음 클립용 시작 프레임으로 저장합니다."""
        if not video_path:
            video_path = str(self.result_dir / f"{clip_id}.mp4")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"영상 파일이 존재하지 않습니다: {video_path}")

        out_path = self.frames_dir / f"{clip_id}_last.png"
        cmd = [
            "ffmpeg", "-y",
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


if __name__ == "__main__":
    import sys
    clip = sys.argv[1] if len(sys.argv) > 1 else "C01"
    project = sys.argv[2] if len(sys.argv) > 2 else "mh003"
    
    connector = AsideFlowConnector(project)
    print(f"=== {clip} ({project}) 지시문 생성 및 Aside 전달 ===")
    cmd = connector.build_chat_command(clip)
    print(cmd)
    print("--------------------------------------------------")
    success = connector.inject_to_aside_chat(clip)
    if success:
        print(f"✅ {clip} 생성 지시문이 클립보드에 복사되었으며 Aside 브라우저가 활성화되었습니다.")
        print(f"Aside 채팅창(Ask Aside)에 붙여넣기(Cmd+V)하여 바로 실행할 수 있습니다.")
