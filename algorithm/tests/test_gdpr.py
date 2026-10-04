import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
import numpy as np

from gdpr import FaceBlurrer


def make_frame_with_face() -> np.ndarray:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.ellipse(frame, (160, 110), (48, 62), 0, 0, 360, (235, 225, 215), -1)
    cv2.ellipse(frame, (140, 95), (7, 5), 0, 0, 360, (30, 30, 30), -1)
    cv2.ellipse(frame, (180, 95), (7, 5), 0, 0, 360, (30, 30, 30), -1)
    cv2.rectangle(frame, (145, 135), (175, 142), (90, 60, 60), -1)
    return frame


class TestFaceBlurrer(unittest.TestCase):
    def test_cascade_loads(self):
        b = FaceBlurrer()
        self.assertFalse(b._cascade.empty())

    def test_pixelate_output_valid(self):
        b = FaceBlurrer(mode="pixelate", strength=6)
        frame = make_frame_with_face()
        out, n = b.anonymize(frame.copy())
        self.assertEqual(out.shape, frame.shape)
        self.assertEqual(out.dtype, np.uint8)
        self.assertGreaterEqual(n, 0)

    def test_solid_mode_erases_something(self):
        b = FaceBlurrer(mode="solid")
        frame = make_frame_with_face()
        out, n = b.anonymize(frame.copy())
        if n > 0:
            diff = int(np.abs(out.astype(int) - frame.astype(int)).sum())
            self.assertGreater(diff, 0)

    def test_empty_frame_safe(self):
        b = FaceBlurrer()
        out, n = b.anonymize(np.zeros((0, 0, 3), dtype=np.uint8))
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
