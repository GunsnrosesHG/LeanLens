import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from config import Config
from reporter import Reporter


class TestReporter(unittest.TestCase):
    def test_save_evidence_writes_jpeg_with_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(images_root=tmp, folder="images/192.168.1.64",
                         camera_ip="192.168.1.64", blur_faces=False)
            r = Reporter(cfg)
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            rel = r.save_evidence(frame, "test")
            self.assertTrue(rel.startswith("images/192.168.1.64/"))
            f = Path(tmp) / "192.168.1.64" / Path(rel).name
            self.assertTrue(f.exists())
            self.assertGreater(f.stat().st_size, 0)

    def test_send_report_posts_expected_payload(self):
        received = {}

        class FakeResp:
            status_code = 201

            def raise_for_status(self):
                pass

        def fake_post(url, json=None, timeout=None):
            received["url"] = url
            received["json"] = json
            return FakeResp()

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(
                images_root=tmp, folder="images/10.0.0.9", camera_ip="10.0.0.9",
                link_reports="http://django:8000/api/reports/report-with-photos/",
                algorithm_name="smartphone_idle_control", blur_faces=False,
            )
            r = Reporter(cfg)
            r.session.post = fake_post
            ok = r.send_report(
                violation_found=True, start=time.time() - 60, stop=time.time(),
                photos=[{"image": "images/10.0.0.9/x.jpg", "date": "2026-09-16 10:00:00.0"}],
            )
            self.assertTrue(ok)
            payload = received["json"]
            self.assertEqual(payload["algorithm"], "smartphone_idle_control")
            self.assertEqual(payload["camera"], "10.0.0.9")
            self.assertTrue(payload["violation_found"])
            self.assertTrue(payload["photos"][0]["image"].startswith("images/"))
            self.assertIn("start_tracking", payload)
            self.assertIn("stop_tracking", payload)

    def test_blur_disabled_via_config(self):
        cfg = Config(blur_faces=False)
        r = Reporter(cfg)
        self.assertIsNone(r.blurrer)


if __name__ == "__main__":
    unittest.main()
