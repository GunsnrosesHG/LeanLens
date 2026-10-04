"""StatusReporter — heartbeat RGPD du worker vers la plateforme.

Le worker publie sa config d'anonymisation (POST /api/core/gdpr/worker-status/)
toutes les REPORT_STATUS_S secondes : l'UI v2 (page RGPD) affiche ainsi un
indicateur LIVE du floutage des visages, rafraîchi par le processus qui écrit
réellement les preuves.

Auth : même compte de service JWT que l'AssignmentWatcher (ASSIGN_SERVICE_USER /
ASSIGN_SERVICE_PASSWORD), préfixe d'en-tête « JWT ».
Dégradé : sans identifiants, ou si l'API est injoignable, aucun crash — le
prochain cycle retentera. Le reporting n'affecte jamais la détection.
"""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger("status_reporter")

DEFAULT_INTERVAL_S = 60.0
DEFAULT_TIMEOUT_S = 10.0


class StatusReporter:
    """Publie la config RGPD du worker (fire-and-forget, TTL-gated)."""

    def __init__(
        self,
        django_url: str,
        camera_ip: str,
        algorithm_name: str,
        blur_faces: bool,
        blur_mode: str = "pixelate",
        username: str = "",
        password: str = "",
        interval_s: float = DEFAULT_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session: requests.Session | None = None,
    ):
        self.django_url = (django_url or "").rstrip("/")
        self.camera_ip = camera_ip
        self.algorithm_name = algorithm_name
        self.blur_faces = bool(blur_faces)
        self.blur_mode = blur_mode if blur_mode in ("pixelate", "blur", "solid") else "pixelate"
        self.username = username
        self.password = password
        self.interval_s = interval_s
        self.timeout_s = timeout_s
        self.session = session or requests.Session()
        self._token: str | None = None
        self._next_report = 0.0
        self.last_reported_at: float | None = None

    # --- auth JWT (même contrat que AssignmentWatcher) -------------------
    def _login(self) -> None:
        r = self.session.post(
            f"{self.django_url}/api/auth/jwt/create/",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        self._token = r.json()["access"]

    # --- publication ------------------------------------------------------
    def report_once(self) -> bool:
        """Un POST de statut ; True si accepté par la plateforme."""
        if not self.django_url:
            return False
        try:
            if not self._token:
                self._login()
            r = self.session.post(
                f"{self.django_url}/api/core/gdpr/worker-status/",
                headers={"Authorization": f"JWT {self._token}"},
                json={
                    "blur_faces": self.blur_faces,
                    "blur_mode": self.blur_mode,
                    "algorithm": self.algorithm_name,
                    "camera": self.camera_ip,
                    "worker": "leanlens-algo",
                },
                timeout=self.timeout_s,
            )
            if r.status_code in (401, 403):
                # token expiré -> nouveau login au prochain cycle
                self._token = None
                return False
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("heartbeat RGPD non envoyé (%s)", exc)
            return False
        self.last_reported_at = time.time()
        return True

    def maybe_report(self, now: float | None = None) -> bool | None:
        """Report si l'intervalle est écoulé ; None si pas de compte de service."""
        if not (self.username and self.password):
            return None
        now = time.time() if now is None else now
        if now < self._next_report:
            return None
        self._next_report = now + self.interval_s
        return self.report_once()
