"""Reporter : écriture des preuves JPEG dans le volume images + POST Django.

Format attendu par /api/reports/report-with-photos/ (voir src/Reports/views.py) :
  { "algorithm": str, "camera": str(ip), "start_tracking": "%Y-%m-%d %H:%M:%S.%f",
    "stop_tracking": "%Y-%m-%d %H:%M:%S.%f", "violation_found": bool, "extra": ...,
    "photos": [ {"image": "images/<ip>/<fichier>.jpg", "date": "..."} ] }
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import cv2
import numpy as np
import requests

from config import Config
from gdpr import FaceBlurrer

# Format attendu par le backend : datetime.strptime("%Y-%m-%d %H:%M:%S.%f")
TS_FMT = "%Y-%m-%d %H:%M:%S.%f"


def ts(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime(TS_FMT)


class Reporter:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.blurrer = FaceBlurrer(mode=cfg.blur_mode) if cfg.blur_faces else None
        self.session = requests.Session()

    def _rel_path(self, fname: str) -> str:
        rel_cam = self.cfg.folder.split("images/")[-1] if "images/" in self.cfg.folder else self.cfg.camera_ip
        return f"images/{rel_cam}/{fname}"

    def save_evidence(self, frame: np.ndarray, tag: str) -> str:
        """Écrit la frame anonymisée dans le volume images partagé ; retourne le chemin relatif."""
        d = self.cfg.images_dir
        os.makedirs(d, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{stamp}_{tag}.jpg"
        path = os.path.join(d, fname)
        out = frame
        if self.blurrer is not None:
            out, _ = self.blurrer.anonymize(frame.copy())
        cv2.imwrite(path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return self._rel_path(fname)

    def send_report(self, violation_found: bool, start: float, stop: float,
                    extra: dict | None = None, photos: list[dict] | None = None) -> bool:
        payload = {
            "algorithm": self.cfg.algorithm_name,
            "camera": self.cfg.camera_ip,
            "start_tracking": ts(start),
            "stop_tracking": ts(stop),
            "violation_found": bool(violation_found),
            "extra": extra if extra is not None else self.cfg.extra,
            "photos": photos or [],
        }
        if not self.cfg.link_reports:
            return False
        try:
            r = self.session.post(self.cfg.link_reports, json=payload, timeout=15)
            r.raise_for_status()
            return True
        except requests.RequestException:
            return False
