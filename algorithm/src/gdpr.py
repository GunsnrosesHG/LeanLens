"""Anonymisation RGPD : floutage des visages sur les photos de preuve.

Utilise la cascade Haar intégrée à OpenCV (aucun téléchargement requis).
Deux modes : rect blanc (réversible ni visuellement ni OCR) ou flou gaussien.
Les visages ne sont floutés QUE sur les preuves envoyées/stockées ; les frames
d'analyse restent intactes pour la détection.
"""

from __future__ import annotations

import cv2
import numpy as np


class FaceBlurrer:
    def __init__(self, mode: str = "pixelate", strength: int = 14):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError("Haar cascade introuvable dans OpenCV")
        self.mode = mode if mode in ("pixelate", "blur", "solid") else "pixelate"
        self.strength = max(4, int(strength))

    def anonymize(self, frame: np.ndarray) -> tuple[np.ndarray, int]:
        """Retourne (frame_anonymisée, nb_visages_floutés)."""
        if frame is None or frame.size == 0:
            return frame, 0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(28, 28))
        n = 0
        for (x, y, w, h) in faces:
            pad = max(2, w // 6)
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(frame.shape[1], x + w + pad), min(frame.shape[0], y + h + pad)
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            if self.mode == "pixelate":
                small = cv2.resize(roi, (self.strength, self.strength), interpolation=cv2.INTER_LINEAR)
                roi_anon = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
            elif self.mode == "blur":
                k = self.strength * 2 + 1
                roi_anon = cv2.GaussianBlur(roi, (k, k), 0)
            else:  # solid
                roi_anon = np.full_like(roi, 245)
            frame[y1:y2, x1:x2] = roi_anon
            n += 1
        return frame, n
