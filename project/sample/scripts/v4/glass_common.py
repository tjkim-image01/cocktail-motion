"""Shared helpers for the v4 glass measurements (measurement only; reads 01_레퍼런스/original.mp4).

Frames are read sequentially with cv2.VideoCapture, frame index i = 0-based (t = i/30).
Crops are kept in RAM only (disk is nearly full) — region X0..X1, Y0..Y1 in full-frame pixels.
"""
from pathlib import Path
import json
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / '01_레퍼런스/original.mp4'
OUT = ROOT / '01_레퍼런스/analysis-v4/glass'
OUT.mkdir(parents=True, exist_ok=True)
X0, X1, Y0, Y1 = 60, 720, 230, 900          # region that holds glass, spoon, peel, rays

def load(first=0, last=899, region=(X0, X1, Y0, Y1)):
    x0, x1, y0, y1 = region
    cap = cv2.VideoCapture(str(VIDEO)); fr = {}; i = 0
    while i <= last:
        ok, f = cap.read()
        if not ok: break
        if i >= first: fr[i] = f[y0:y1, x0:x1].copy()
        i += 1
    return fr

def ink(bgr, thr=110):
    """dark ink that survives red liquid: max channel < thr"""
    return (bgr.max(2) < thr)

def hexc(bgr):
    b, g, r = [int(round(v)) for v in bgr]
    return '#%02x%02x%02x' % (r, g, b)

def save_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=None, separators=(',', ':'), ensure_ascii=False, default=float))
