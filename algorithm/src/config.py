"""Configuration du conteneur algorithme (env vars passées par algorithms-controller).

Variables (identiques au contrat plateforme LeanLens) :
  camera_url        : URL snapshot ONVIF http://onvif:3456/onvif-http/snapshot?camera_ip=<ip>
                      (ou RTSP direct si pas d'onvif)
  camera_stream_url : RTSP complet (optionnel, secours snapshot)
  username/password : identifiants caméra (auth basique snapshot)
  server_url        : URL du serveur de modèles (ex: http://leanlens-model:5000)
  link_reports      : endpoint Django (api/reports/report-with-photos/)
  folder            : sous-dossier images (ex: images/192.168.1.64)
  camera_ip         : IP caméra
  algorithm_name    : nom de l'algorithme (smartphone_idle_control)
  areas / extra     : zones JSON (string)
Plus variables propres : USE_LOCAL_MODEL, MODEL_WEIGHTS, IMAGES_ROOT, seuils…
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # --- contrat plateforme LeanLens ---
    camera_url: str = field(default_factory=lambda: _env("camera_url"))
    camera_stream_url: str = field(default_factory=lambda: _env("camera_stream_url"))
    username: str = field(default_factory=lambda: _env("username"))
    password: str = field(default_factory=lambda: _env("password"))
    server_url: str = field(default_factory=lambda: _env("server_url", "http://localhost:5000"))
    link_reports: str = field(default_factory=lambda: _env("link_reports"))
    folder: str = field(default_factory=lambda: _env("folder"))
    camera_ip: str = field(default_factory=lambda: _env("camera_ip", "unknown"))
    algorithm_name: str = field(default_factory=lambda: _env("algorithm_name", "smartphone_idle_control"))
    extra: dict[str, Any] = field(default_factory=dict)

    # --- fonctionnement ---
    images_root: str = field(default_factory=lambda: _env("IMAGES_ROOT", "/var/www/leanlens/images"))
    snapshot_interval_s: float = field(default_factory=lambda: _env_float("SNAPSHOT_INTERVAL_S", 2.0))
    reconnect_delay_s: float = field(default_factory=lambda: _env_float("RECONNECT_DELAY_S", 5.0))

    # --- modèle ---
    use_local_model: bool = field(default_factory=lambda: _env_bool("USE_LOCAL_MODEL", False))
    model_weights: str = field(default_factory=lambda: _env("MODEL_WEIGHTS", "best.pt"))
    model_timeout_s: float = field(default_factory=lambda: _env_float("MODEL_TIMEOUT_S", 15.0))

    # --- détection / seuils (objectif 84 %) ---
    conf_threshold: float = field(default_factory=lambda: _env_float("CONF_THRESHOLD", 0.84))
    conf_phone: float = field(default_factory=lambda: _env_float("CONF_PHONE", 0.84))
    conf_idle: float = field(default_factory=lambda: _env_float("CONF_IDLE", 0.84))
    # Plancher de confiance « track » : une détection sous ce seuil ne crée ni
    # ne maintient de track (les machines à états ne voient que du fiable).
    conf_track: float = field(default_factory=lambda: _env_float("CONF_TRACK", 0.25))
    iou_threshold: float = field(default_factory=lambda: _env_float("IOU_THRESHOLD", 0.5))

    # --- machines à états ---
    phone_min_hits: int = field(default_factory=lambda: _env_int("PHONE_MIN_HITS", 3))
    phone_misses_to_end: int = field(default_factory=lambda: _env_int("PHONE_MISSES_TO_END", 5))
    idle_seconds: float = field(default_factory=lambda: _env_float("IDLE_SECONDS", 30.0))
    idle_move_tolerance_px: float = field(default_factory=lambda: _env_float("IDLE_MOVE_TOLERANCE_PX", 15.0))

    # --- RGPD ---
    blur_faces: bool = field(default_factory=lambda: _env_bool("BLUR_FACES", True))
    blur_mode: str = field(default_factory=lambda: _env("BLUR_MODE", "pixelate"))

    # --- affectation plateforme (toggle UI -> worker) ---
    # Le worker interroge get-process/<ip>/ pour suspendre la détection si
    # l'algorithme est désactivé pour la caméra dans l'UI (page Algorithmes).
    assign_service_user: str = field(default_factory=lambda: _env("ASSIGN_SERVICE_USER"))
    assign_service_password: str = field(default_factory=lambda: _env("ASSIGN_SERVICE_PASSWORD"))
    assign_poll_s: float = field(default_factory=lambda: _env_float("ASSIGN_POLL_S", 5.0))
    assign_timeout_s: float = field(default_factory=lambda: _env_float("ASSIGN_TIMEOUT_S", 10.0))

    # --- statut RGPD (heartbeat vers la plateforme) ---
    report_status_s: float = field(default_factory=lambda: _env_float("REPORT_STATUS_S", 60.0))

    # --- divers ---
    debug_frames: bool = field(default_factory=lambda: _env_bool("DEBUG_FRAMES", False))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))

    def __post_init__(self) -> None:
        raw_extra = _env("extra") or _env("areas") or ""
        if raw_extra:
            try:
                parsed = json.loads(raw_extra)
                self.extra = parsed if isinstance(parsed, (dict, list)) else {"coords": parsed}
            except json.JSONDecodeError:
                self.extra = {}

    @property
    def model_endpoint(self) -> str:
        """URL du serveur de modèles.

        server_url (contrat plateforme LeanLens) est souvent un hôte nu (ex: 'django' ou
        '192.168.1.101') : on dérive http://<hôte>:5000 (port publié du model server).
        MODEL_SERVER_URL permet de forcer une URL complète (ex: http://leanlens-model:5000).
        """
        forced = _env("MODEL_SERVER_URL")
        if forced:
            return forced.rstrip("/")
        raw = (self.server_url or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw.rstrip("/")
        if raw:
            host = raw.split(":")[0]
            return f"http://{host}:5000"
        return "http://localhost:5000"

    @property
    def images_dir(self) -> str:
        """Dossier où écrire les preuves (partagé avec onvif/webserver)."""
        sub = self.folder or f"images/{self.camera_ip}"
        # folder arrive sous la forme 'images/<ip>' ; on ne garde que la partie relative
        rel = sub.split("images/")[-1] if "images/" in sub else sub
        return f"{self.images_root.rstrip('/')}/{rel}".rstrip("/")

    @property
    def is_rtsp(self) -> bool:
        return self.camera_stream_url.startswith("rtsp://") if self.camera_stream_url else (
            self.camera_url.startswith("rtsp://")
        )

    @property
    def django_base_url(self) -> str:
        """Origine de l'API Django, dérivée de link_reports (http://hôte:port/api/...)."""
        raw = (self.link_reports or "").strip()
        if "/api/" in raw:
            return raw.split("/api/")[0].rstrip("/")
        return raw.rstrip("/")
