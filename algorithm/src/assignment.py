"""AssignmentWatcher — l'affectation plateforme pilote le worker.

Le worker interroge l'API Django (GET /api/camera-algorithms/get-process/<ip>/)
toutes les ASSIGN_POLL_S secondes pour savoir si son algorithme reste affecté
à sa caméra. L'UI v2 (page « Algorithmes », POST /api/camera-algorithms/
toggle-process/) crée/supprime cette affectation : désactivé = la ligne
CameraAlgorithm disparaît de get-process et le worker suspend la détection
(reset des machines à états et du tracker).

Auth : JWT de service (ASSIGN_SERVICE_USER / ASSIGN_SERVICE_PASSWORD),
préfixe d'en-tête « JWT » (SIMPLE_JWT.AUTH_HEADER_TYPES de la plateforme).
Dégradé : sans identifiants de service configurés, ou avant le premier état
connu / en cas d'erreur API, la détection continue (fail-open) — seule une
affectation explicitement absente ou inactive suspend le worker.
"""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger("assignment")

DEFAULT_POLL_S = 5.0
DEFAULT_TIMEOUT_S = 10.0


class AssignmentWatcher:
    """Cache TTL de l'état d'affectation (algorithme, caméra) côté plateforme."""

    def __init__(
        self,
        django_url: str,
        camera_ip: str,
        algorithm_name: str,
        username: str = "",
        password: str = "",
        poll_s: float = DEFAULT_POLL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session: requests.Session | None = None,
    ):
        self.django_url = (django_url or "").rstrip("/")
        self.camera_ip = camera_ip
        self.algorithm_name = algorithm_name
        self.username = username
        self.password = password
        self.poll_s = poll_s
        self.timeout_s = timeout_s
        self.session = session or requests.Session()
        self._token: str | None = None
        self._next_poll = 0.0
        # Dernier état connu ; True tant que la plateforme n'a rien dit d'autre.
        self.enabled = True

    # --- auth JWT -------------------------------------------------------
    def _login(self) -> None:
        r = self.session.post(
            f"{self.django_url}/api/auth/jwt/create/",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        self._token = r.json()["access"]

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self._login()
        return {"Authorization": f"JWT {self._token}"}

    # --- état plateforme -------------------------------------------------
    def fetch_assignment(self) -> bool | None:
        """True/False si l'état plateforme est lisible, None si indisponible.

        Réponse get-process/<ip>/ :
          [{"camera": {...}, "algorithms": [{"algorithm": {"id", "name"},
                                             "process_id": int, "is_active": bool}]}]
        """
        url = f"{self.django_url}/api/camera-algorithms/get-process/{self.camera_ip}/"
        try:
            r = self.session.get(url, headers=self._headers(), timeout=self.timeout_s)
            if r.status_code == 401 and self.username:
                self._login()
                r = self.session.get(url, headers=self._headers(), timeout=self.timeout_s)
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("affectation plateforme indisponible (%s) — état conservé", exc)
            return None
        try:
            entries = r.json()
            for entry in entries or []:
                for link in entry.get("algorithms") or []:
                    algo = link.get("algorithm") or {}
                    if algo.get("name") == self.algorithm_name:
                        return bool(link.get("is_active", False))
        except (ValueError, AttributeError):
            return None
        # Aucune affectation pour cet algorithme -> désactivé côté plateforme.
        return False

    def is_enabled(self, now: float | None = None) -> bool:
        """Vrai si la détection doit tourner (cache TTL, un poll / poll_s)."""
        if not self.username or not self.password:
            return True  # pas de compte de service : watcher désactivé
        now = time.time() if now is None else now
        if now >= self._next_poll:
            self._next_poll = now + self.poll_s
            state = self.fetch_assignment()
            if state is not None and state != self.enabled:
                log.info(
                    "affectation %s@%s -> %s",
                    self.algorithm_name,
                    self.camera_ip,
                    "ACTIVE" if state else "SUSPENDUE",
                )
                self.enabled = state
        return self.enabled
