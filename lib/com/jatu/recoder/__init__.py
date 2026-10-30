"""시스템 소리 녹음 (audio_clip 기능). 사용: from lib.com.jatu.recoder import start, stop, record"""
from .recorder import RecorderError, record, start, status, stop

__all__ = ["start", "stop", "status", "record", "RecorderError"]
