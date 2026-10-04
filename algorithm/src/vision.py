import cv2
import numpy as np
import requests

from config import Config


class FrameSource:
    """Source d'images : snapshots HTTP ONVIF (défaut) ou flux RTSP (fallback)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._cap = None

    def _http_session(self) -> requests.Session:
        s = requests.Session()
        if self.cfg.username:
            s.auth = (self.cfg.username, self.cfg.password or "")
        return s

    def read(self):
        """Retourne (ok, frame BGR)."""
        if self.cfg.is_rtsp:
            return self._read_rtsp()
        return self._read_snapshot()

    def _read_snapshot(self):
        url = self.cfg.camera_url
        if not url:
            return False, None
        try:
            r = self._http_session().get(url, timeout=10)
            r.raise_for_status()
            arr = np.frombuffer(r.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return (frame is not None), frame
        except requests.RequestException:
            return False, None

    def _read_rtsp(self):
        url = self.cfg.camera_stream_url or self.cfg.camera_url
        if self._cap is None or not self._cap.isOpened():
            self._cap = cv2.VideoCapture(url)
            if not self._cap.isOpened():
                return False, None
        ok, frame = self._cap.read()
        if not ok:
            self._cap.release()
            self._cap = None
        return ok, frame

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class ModelClient:
    """Client du serveur de modèles ; bascule en local si USE_LOCAL_MODEL=1."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._local = None

    def predict(self, frame: np.ndarray) -> list[dict]:
        if self.cfg.use_local_model:
            return self._predict_local(frame)
        return self._predict_http(frame)

    def _predict_http(self, frame: np.ndarray) -> list[dict]:
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return []
        try:
            r = requests.post(
                f"{self.cfg.model_endpoint}/predict",
                files={"image": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                timeout=self.cfg.model_timeout_s,
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException:
            return []
        out = []
        for d in data.get("detections", []):
            x1, y1, x2, y2 = d["bbox"]
            out.append({
                "cls": int(d.get("class_id", -1)),
                "name": str(d.get("class_name", "")),
                "conf": float(d.get("confidence", 0.0)),
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
            })
        return out

    def _predict_local(self, frame: np.ndarray) -> list[dict]:
        if self._local is None:
            from ultralytics import YOLO  # import tardif : pas requis côté serveur

            self._local = YOLO(self.cfg.model_weights)
        res = self._local.predict(frame, conf=0.01, verbose=False)[0]
        names = self._local.names or {}
        out = []
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_i = int(box.cls[0])
            out.append({
                "cls": cls_i,
                "name": str(names.get(cls_i, cls_i)),
                "conf": float(box.conf[0]),
                "bbox": (x1, y1, x2, y2),
            })
        return out
