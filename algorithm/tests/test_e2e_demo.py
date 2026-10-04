"""Test d'intégration E2E : serveur de modèles HTTP réel -> tracker IoU ->
machines à états -> floutage RGPD -> POST au format Django.

S'exécute contre le model server local (models/best.pt) sans caméra : les
frames viennent du split test, donc les détections sont RÉELLES (modèle
entraîné Jour 2). Nécessite le serveur démarré (docs/build_watch.sh le fait)
sinon le test est marqué SKIP avec le motif.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np
import requests

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(HERE.parent))

from config import Config                      # noqa: E402
from logic import StateMachines                # noqa: E402
from gdpr import FaceBlurrer                   # noqa: E402

MODEL_URL = os.environ.get("E2E_MODEL_URL", "http://127.0.0.1:5000")
DATA_IMAGES = HERE.parent.parent / "training" / "data" / "images" / "test"


def frame_from(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


class ReportCatcher(BaseHTTPRequestHandler):
    """Stub du endpoint Django : capture les payloads POST report-with-photos."""
    reports: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            ReportCatcher.reports.append(json.loads(body))
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": true, "message": "Data created successfully"}')
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass


class TestEndToEndDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1) model server disponible ?
        try:
            r = requests.get(f"{MODEL_URL}/health", timeout=5)
            server_up = r.ok
        except requests.RequestException:
            server_up = False
        if not server_up:
            raise unittest.SkipTest(
                f"model server absent sur {MODEL_URL} — lance-le d'abord "
                "(docker compose up leanlens-model, ou python server.py dans"
                " algorithm/model_server avec MODEL_WEIGHTS=../../models/best.pt)"
            )

        # 2) stub Django en arrière-plan
        cls.httpd = HTTPServer(("127.0.0.1", 8765), ReportCatcher)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def _cfg(self) -> Config:
        os.environ.update({
            "camera_ip": "192.168.1.64",
            "folder": "images/192.168.1.64",
            "algorithm_name": "smartphone_idle_control",
            "link_reports": "http://127.0.0.1:8765/api/reports/report-with-photos/",
            "server_url": "leanlens-model",
            "MODEL_SERVER_URL": MODEL_URL,
            "IMAGES_ROOT": str(HERE.parent / ".e2e_images"),
            "CONF_THRESHOLD": "0.5",   # démo : le modèle bootstrap a un rappel faible
            "PHONE_MIN_HITS": "2",
            "IDLE_SECONDS": "0.5",     # accéléré pour le test
        })
        return Config()

    def test_full_pipeline_produces_django_report(self):
        cfg = self._cfg()
        from main import SimpleIoUTracker  # import tardif : après os.environ

        session = requests.Session()
        tracker = SimpleIoUTracker(cfg.iou_threshold)
        machines = StateMachines(cfg)
        blurrer = FaceBlurrer() if cfg.blur_faces else None
        out_dir = Path(cfg.images_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        images = sorted(DATA_IMAGES.glob("*.jpg"))[:15]
        self.assertTrue(images, "images du split test introuvables")

        all_tracks = []
        for it, img_path in enumerate(images):
            frame = frame_from(img_path)
            self.assertIsNotNone(frame)
            buf_ok, buf = cv2.imencode(".jpg", frame)
            self.assertTrue(buf_ok)
            r = session.post(f"{MODEL_URL}/predict",
                             files={"image": ("f.jpg", buf.tobytes(), "image/jpeg")},
                             timeout=20)
            self.assertEqual(r.status_code, 200, r.text)
            dets = [
                {
                    "cls": d["class_id"],
                    "name": d["class_name"],
                    "conf": float(d["confidence"]),
                    "bbox": tuple(d["bbox"]),
                }
                for d in r.json().get("detections", [])
            ]
            tracks = tracker.update(dets)
            for t in tracks:
                t["t"] = time.time()
            all_tracks.extend(tracks)
            machines.update(tracks)
            time.sleep(0.05)

        # a) des détections réelles ont circulé
        self.assertGreater(len(all_tracks), 0, "aucune détection sur 15 images test")

        # b) une preuve JPEG floutée existe pour au moins une frame
        proof = out_dir / "e2e_proof.jpg"
        frame = frame_from(images[0])
        out, n_faces = blurrer.anonymize(frame.copy()) if blurrer else (frame, 0)
        cv2.imwrite(str(proof), out, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        self.assertTrue(proof.exists())

        # c) POST au format Django accepté par le stub (violation simulée)
        payload = {
            "algorithm": cfg.algorithm_name,
            "camera": cfg.camera_ip,
            "start_tracking": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "stop_tracking": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "violation_found": True,
            "extra": {"e2e": True},
            "photos": [{"image": f"images/192.168.1.64/{proof.name}", "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}],
        }
        r = session.post(cfg.link_reports, json=payload, timeout=10)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(ReportCatcher.reports), 1)
        rep = ReportCatcher.reports[0]
        for key in ("algorithm", "camera", "start_tracking", "stop_tracking",
                    "violation_found", "extra", "photos"):
            self.assertIn(key, rep)
        self.assertGreaterEqual(len(rep["photos"]), 1)

        # d) rapport de synthèse
        summary = {
            "frames": len(images),
            "tracks_total": len(all_tracks),
            "class_histogram": {
                name: sum(1 for t in all_tracks if t["name"] == name)
                for name in sorted({t["name"] for t in all_tracks})
            },
            "faces_blurred_in_proof": n_faces,
            "report_accepted": True,
        }
        (HERE.parent / ".e2e_images" / "e2e_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8")
        print("\nE2E SUMMARY:", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
