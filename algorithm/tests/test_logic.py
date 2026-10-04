import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config
from logic import PERSON_PHONE, SMARTPHONE, StateMachines


def tr(tid, cls, conf=0.9, bbox=(100, 100, 200, 200)):
    return {"tid": tid, "cls": cls, "name": "", "conf": conf, "bbox": bbox, "t": None}


class TestStateMachines(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_phone_opens_after_min_hits_and_closes_after_misses(self):
        m = StateMachines(self.cfg)
        evs = []
        for _ in range(3):
            evs += m.update([tr(1, SMARTPHONE)])
        self.assertTrue(any(e["event"] == "phone_start" for e in evs), evs)
        for _ in range(self.cfg.phone_misses_to_end + 1):
            m.update([])
        self.assertFalse(m.phone[1].open)

    def test_phone_below_conf_never_opens(self):
        m = StateMachines(self.cfg)
        evs = []
        for _ in range(10):
            evs = m.update([tr(1, SMARTPHONE, conf=0.5)])
        self.assertFalse(any(e["event"] == "phone_start" for e in evs))

    def test_idle_alert_after_configured_duration(self):
        cfg = Config(idle_seconds=1.0, idle_move_tolerance_px=15.0)
        m = StateMachines(cfg)
        t0 = time.time()
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0
            m.update([tr(2, PERSON_PHONE)])
        hist = m.centers_by_track[2]
        for i in range(6):
            hist.append((t0 + 1.2 + i * 0.1, 150.0, 150.0))
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0 + 2.0
            evs = m.update([tr(2, PERSON_PHONE)])
        self.assertTrue(any(e["event"] == "idle_alert" for e in evs), evs)

    def test_moving_track_not_idle(self):
        cfg = Config(idle_seconds=1.0)
        m = StateMachines(cfg)
        t0 = time.time()
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0
            m.update([tr(3, PERSON_PHONE)])
        hist = m.centers_by_track[3]
        for i in range(6):
            hist.append((t0 + 1.2 + i * 0.1, 150.0 + i * 40, 150.0))
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0 + 2.0
            evs = m.update([tr(3, PERSON_PHONE)])
        self.assertFalse(any(e["event"] == "idle_alert" for e in evs))
    def test_idle_gate_on_seen_tracks(self):
        """Un track disparu de la scène ne doit plus émettre d'alerte idle."""
        cfg = Config(idle_seconds=1.0)
        m = StateMachines(cfg)
        t0 = time.time()
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0
            m.update([tr(4, PERSON_PHONE)])
        hist = m.centers_by_track[4]
        for i in range(6):
            hist.append((t0 + 1.2 + i * 0.1, 150.0, 150.0))
        with patch("logic.time") as fake_time:
            fake_time.time.return_value = t0 + 2.0
            evs = m.update([])  # le track n'est plus vu
        self.assertFalse(any(e["event"] == "idle_alert" for e in evs))


class TestSimpleIoUTrackerConfFloor(unittest.TestCase):
    """Plancher de confiance : les détections faibles ne pilotent rien."""

    def _tracker(self, floor):
        from main import SimpleIoUTracker
        return SimpleIoUTracker(conf_floor=floor)

    @staticmethod
    def detr(name, conf, bbox=(100, 100, 200, 200)):
        """Détection au format du serveur de modèles (clé « name »)."""
        return {"tid": 0, "cls": name, "name": name, "conf": conf, "bbox": bbox, "t": None}

    def test_below_floor_creates_no_track(self):
        tk = self._tracker(0.25)
        out = tk.update([self.detr("person", 0.20)])
        self.assertEqual(out, [])
        self.assertEqual(tk._tracks, {})

    def test_below_floor_cannot_resurrect_or_idle(self):
        """Une détection faible ne doit ni maintenir un track existant,
        ni alimenter l'historique idle d'un track quelconque."""
        from logic import StateMachines
        tk = self._tracker(0.25)
        machines = StateMachines(Config(idle_seconds=0.5, idle_move_tolerance_px=1e6))
        out0 = tk.update([self.detr("person", 0.9)])
        machines.update(out0)
        tid0 = out0[0]["tid"]
        n_idle = 0
        # rafale de détections sous le plancher sur le même emplacement
        for _ in range(3):  # < max_misses : le track ne doit pas en dépendre
            weak = tk.update([self.detr("person", 0.20)])
            self.assertEqual(weak, [])
            evs = machines.update([tr(9, PERSON_PHONE, conf=0.9)])
            n_idle += sum(1 for e in evs if e["event"] == "idle_alert")
        self.assertEqual(n_idle, 0)
        self.assertIn(tid0, tk._tracks)  # le track survit (peu de misses)
        out1 = tk.update([self.detr("person", 0.9)])
        self.assertEqual(out1[0]["tid"], tid0)  # ré-association au même id

    def test_below_floor_dropped_when_matched_to_existing(self):
        tk = self._tracker(0.25)
        tk.update([self.detr("person", 0.9, bbox=(100, 100, 200, 200))])
        out = tk.update([self.detr("person", 0.20, bbox=(102, 100, 202, 200))])
        self.assertEqual(out, [])  # filtrée AVANT l'association

    def test_floor_zero_keeps_everything(self):
        tk = self._tracker(0.0)
        out = tk.update([self.detr("person", 0.05)])
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
