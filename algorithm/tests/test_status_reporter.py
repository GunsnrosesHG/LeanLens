"""Tests StatusReporter : heartbeat RGPD du worker vers la plateforme."""
import os
import sys
import unittest
from unittest.mock import MagicMock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from status_reporter import StatusReporter


def make_reporter(**kw):
    session = MagicMock()
    defaults = dict(
        django_url="http://django:8000",
        camera_ip="192.168.1.64",
        algorithm_name="smartphone_idle_control",
        blur_faces=True,
        blur_mode="pixelate",
        username="leanlens-worker",
        password="pw",
        session=session,
    )
    defaults.update(kw)
    return StatusReporter(**defaults), session


def response(json_data=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(f"HTTP {status}")
    else:
        r.raise_for_status.return_value = None
    return r


class TestStatusReporter(unittest.TestCase):
    def test_report_once_posts_config_with_jwt(self):
        rp, s = make_reporter()
        s.post.return_value = response({"access": "tok"})
        ok = rp.report_once()
        self.assertTrue(ok)
        self.assertEqual(s.post.call_count, 2)  # login + statut
        login_url = s.post.call_args_list[0][0][0]
        self.assertEqual(login_url, "http://django:8000/api/auth/jwt/create/")
        url, kwargs = s.post.call_args_list[1][0][0], s.post.call_args_list[1][1]
        self.assertEqual(url, "http://django:8000/api/core/gdpr/worker-status/")
        self.assertEqual(kwargs["headers"]["Authorization"], "JWT tok")
        payload = kwargs["json"]
        self.assertTrue(payload["blur_faces"])
        self.assertEqual(payload["blur_mode"], "pixelate")
        self.assertEqual(payload["algorithm"], "smartphone_idle_control")
        self.assertEqual(payload["worker"], "leanlens-algo")

    def test_invalid_mode_falls_back_to_pixelate(self):
        rp, _ = make_reporter(blur_mode="inconnu")
        self.assertEqual(rp.blur_mode, "pixelate")

    def test_auth_error_resets_token_and_fails_soft(self):
        rp, s = make_reporter()
        s.post.return_value = response({"access": "tok"})
        rp.report_once()  # login + premier report OK
        token = rp._token
        # token expiré : le POST statut renvoie 401
        s.post.side_effect = None
        s.post.return_value = response(status=401)
        ok = rp.report_once()
        self.assertFalse(ok)
        self.assertIsNone(rp._token)  # réinitialisé -> nouveau login au prochain cycle

    def test_network_error_fails_soft(self):
        rp, s = make_reporter()
        s.post.side_effect = requests.exceptions.ConnectionError("api down")
        self.assertFalse(rp.report_once())
        self.assertIsNone(rp.last_reported_at)

    def test_maybe_report_respects_interval(self):
        rp, _ = make_reporter(interval_s=60.0)
        rp.report_once = MagicMock(return_value=True)
        now = 1000.0
        # premier appel : report immédiat (heartbeat au démarrage)
        self.assertTrue(rp.maybe_report(now=now))
        # intervalle repoussé -> pas de report dans la fenêtre
        self.assertIsNone(rp.maybe_report(now=now + 30.0))
        # fenêtre écoulée -> nouveau report
        self.assertTrue(rp.maybe_report(now=now + 60.0))
        self.assertEqual(rp.report_once.call_count, 2)

    def test_no_service_account_is_noop(self):
        rp, s = make_reporter(username="", password="")
        self.assertIsNone(rp.maybe_report())
        s.post.assert_not_called()

    def test_token_refreshed_after_expiry(self):
        rp, s = make_reporter()
        # login -> 401 statut -> login -> OK : le reporter retente proprement
        responses = [
            response({"access": "tok1"}),
            response(status=401),
            response({"access": "tok2"}),
            response({"status": True}),
        ]
        s.post.side_effect = lambda *a, **k: responses.pop(0)
        rp.report_once()
        self.assertFalse(rp.last_reported_at is not None)
        rp._next_report = 0.0
        ok = rp.report_once()
        self.assertTrue(ok)
        self.assertEqual(rp._token, "tok2")


if __name__ == "__main__":
    unittest.main()
