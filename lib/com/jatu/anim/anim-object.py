#!/usr/bin/env python3
"""요청된 파일 이름의 실행 진입점. 구현은 anim_object.py (python -m lib.com.jatu.anim.anim_object 로도 실행)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anim_object import main  # noqa: E402

if __name__ == '__main__':
    main()
