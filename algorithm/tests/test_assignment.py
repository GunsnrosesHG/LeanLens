"""Tests AssignmentWatcher : le toggle plateforme suspend/reprend le worker."""
import os
import sys
import unittest
from unittest.mock import MagicMock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from assignment import AssignmentWatcher


def make_watcher(**kw):
    session = MagicMock()
    defaults = dict(
        django_url="http://django:8000",
        camera_ip="192.168.1.64",
        algorithm_name="smartphone_idle_control",
        username="leanlens-worker",
        password="pw",
        session=session,
    )
    defaults.update(kw)
    return AssignmentWatcher(**defaults), session


def response(json_data=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    else:
        r.raise_for_status.return_value = None
    return r


LINKED = [
    {
        "camera": {"id": "192.168.1.64", "name": "Demo"},
        "algorithms": [
            {"algorithm": {"id": 1, "name": "smartphone_idle_control"},
             "process_id": 0, "is_active": True}
        ],
    }
]


class TestAssignmentWatcher(unittest.TestCase):
    def test_linked_and_active(self):
        w, s = make_watcher()
        s.get.return_value = response(LINKED)
        s.post.return_value = response({"access": "tok"})
        self.assertTrue(w.is_enabled())
        self.assertEqual(s.get.call_count, 1)
        url = s.get.call_args[0][0]
        self.assertEqual(url, "http://django:8000/api/camera-algorithms/get-process/192.168.1.64/")
        hdr = s.get.call_args[1]["headers"]["Authorization"]
        self.assertEqual(hdr, "JWT tok")  # préfixe JWT, pas Bearer

    def test_no_assignment_means_disabled(self):
        w, s = make_watcher()
        s.get.return_value = response([{"camera": {}, "algorithms": []}])
        s.post.return_value = response({"access": "tok"})
        self.assertFalse(w.is_enabled())

    def test_link_present_but_inactive(self):
        w, s = make_watcher()
        s.get.return_value = response(LINKED)
        s.get.return_value = response([
            {"camera": {}, "algorithms": [
                {"algorithm": {"id": 1, "name": "smartphone_idle_control"},
                 "process_id": 0, "is_active": False}]}
        ])
        s.post.return_value = response({"access": "tok"})
        self.assertFalse(w.is_enabled())

    def test_ttl_one_poll_per_window(self):
        w, s = make_watcher()
        s.get.return_value = response(LINKED)
        s.post.return_value = response({"access": "tok"})
        self.assertTrue(w.is_enabled(now=100.0))
        self.assertTrue(w.is_enabled(now=101.0))  # dans la fenêtre TTL -> pas de poll
        self.assertEqual(s.get.call_count, 1)
        self.assertTrue(w.is_enabled(now=100.0 + w.poll_s + 1))  # fenêtre dépassée
        self.assertEqual(s.get.call_count, 2)

    def test_fail_open_keeps_last_state(self):
        w, s = make_watcher()
        s.get.return_value = response(LINKED)
        s.post.return_value = response({"access": "tok"})
        self.assertTrue(w.is_enabled(now=0.0))
        # erreur réseau pendant un cycle : état conservé (actif)
        s.get.side_effect = requests.exceptions.ConnectionError("boom")
        self.assertTrue(w.is_enabled(now=0.0 + w.poll_s + 1))
        # plateforme passe à désactivé
        s.get.side_effect = None
        s.get.return_value = response([{"camera": {}, "algorithms": []}])
        self.assertFalse(w.is_enabled(now=0.0 + 2 * (w.poll_s + 1)))
        # erreur réseau pendant la suspension : on RESTE suspendu (pas de reprise sauvage)
        s.get.side_effect = requests.exceptions.ConnectionError("boom")
        self.assertFalse(w.is_enabled(now=0.0 + 3 * (w.poll_s + 1)))

    def test_relogin_on_401(self):
        w, s = make_watcher()
        s.get.side_effect = [response(status=401), response(LINKED)]
        s.post.return_value = response({"access": "tok2"})
        self.assertTrue(w.is_enabled())
        self.assertEqual(s.post.call_count, 2)  # login initial + re-login

    def test_no_credentials_fails_open(self):
        w, _ = make_watcher(username="", password="")
        self.assertTrue(w.is_enabled())  # watcher inactif sans compte de service


if __name__ == "__main__":
    unittest.main()
