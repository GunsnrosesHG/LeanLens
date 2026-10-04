"""smartphone_idle_control — boucle principale du conteneur algorithme LeanLens.

Reçoit par env vars (contrat algorithms-controller) : camera_url, camera_stream_url,
username/password, server_url, link_reports, folder, camera_ip, algorithm_name, extra.

Pipeline : snapshot/RTSP -> tracking ByteTrack -> machines à états smartphone/idle
-> preuves JPEG anonymisées (RGPD) -> POST api/reports/report-with-photos/.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import cv2

from assignment import AssignmentWatcher
from config import Config
from logic import PERSON_IDLE, PERSON_PHONE, SMARTPHONE, StateMachines
from reporter import Reporter
from status_reporter import StatusReporter
from vision import FrameSource, ModelClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("smartphone_idle_control")

ACTIVE_CLASSES = {SMARTPHONE, PERSON_PHONE, PERSON_IDLE}
TRACKABLE_NAMES = {"person_phone", "smartphone", "person_idle", "person"}


def iou(a: tuple, b: tuple) -> float:
    """IoU de deux bboxes (x1, y1, x2, y2)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (area_a + area_b - inter + 1e-9)


class SimpleIoUTracker:
    """Tracker IoU léger pour le mode HTTP (production).

    Le serveur de modèles ne tracke pas : sans ce tracker, chaque snapshot
    produirait des ids éphémères et phone_start (min_hits sur un MÊME track)
    ne pourrait jamais s'ouvrir. Association gloutonne frame à frame,
    ids stables, purge après max_misses snapshots sans correspondance.
    """

    def __init__(self, iou_threshold: float = 0.5, max_misses: int = 8,
                 conf_floor: float = 0.0):
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        # Plancher de confiance : une détection sous ce seuil n'ouvre ni ne
        # maintient aucun track — les machines à états ne voient que du fiable.
        self.conf_floor = conf_floor
        self._tracks: dict[int, dict] = {}
        self._next_id = 1

    def update(self, detections: list[dict]) -> list[dict]:
        out = []
        matched: set[int] = set()
        for det in detections:
            if det.get("name") not in TRACKABLE_NAMES:
                continue
            if self.conf_floor > 0 and det.get("conf", 1.0) < self.conf_floor:
                continue
            best_id, best_iou = None, 0.0
            for tid, tr in self._tracks.items():
                if tid in matched or tr["name"] != det["name"]:
                    continue
                v = iou(det["bbox"], tr["bbox"])
                if v > best_iou:
                    best_id, best_iou = tid, v
            if best_id is not None and best_iou >= self.iou_threshold:
                tid = best_id
                self._tracks[tid].update(bbox=det["bbox"], misses=0)
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = {"name": det["name"], "bbox": det["bbox"], "misses": 0}
            matched.add(tid)
            out.append({**det, "tid": tid})
        for tid in list(self._tracks):
            if tid not in matched:
                self._tracks[tid]["misses"] += 1
                if self._tracks[tid]["misses"] > self.max_misses:
                    self._tracks.pop(tid, None)
        return out


def run() -> None:
    cfg = Config()
    log.info("démarrage %s caméra=%s modèle=%s conf=%.2f idle=%.0fs blur=%s",
             cfg.algorithm_name, cfg.camera_ip, "local" if cfg.use_local_model else cfg.server_url,
             cfg.conf_threshold, cfg.idle_seconds, cfg.blur_faces)

    source = FrameSource(cfg)
    model = ModelClient(cfg)
    reporter = Reporter(cfg)
    machines = StateMachines(cfg)

    # L'affectation plateforme (UI v2, toggle-process) pilote le worker : si
    # l'algorithme est désactivé pour la caméra, la détection est suspendue
    # (fail-open tant que la plateforme n'a pas donné d'état).
    watcher = AssignmentWatcher(
        django_url=cfg.django_base_url,
        camera_ip=cfg.camera_ip,
        algorithm_name=cfg.algorithm_name,
        username=cfg.assign_service_user,
        password=cfg.assign_service_password,
        poll_s=cfg.assign_poll_s,
        timeout_s=cfg.assign_timeout_s,
    )
    if not (cfg.assign_service_user and cfg.assign_service_password):
        log.info("affectation plateforme : pas de compte de service, détection toujours active")

    # Heartbeat RGPD : le worker publie sa config d'anonymisation (page RGPD
    # de l'UI v2) — fire-and-forget, n'affecte jamais la détection.
    status_reporter = StatusReporter(
        django_url=cfg.django_base_url,
        camera_ip=cfg.camera_ip,
        algorithm_name=cfg.algorithm_name,
        blur_faces=cfg.blur_faces,
        blur_mode=cfg.blur_mode,
        username=cfg.assign_service_user,
        password=cfg.assign_service_password,
        interval_s=cfg.report_status_s,
        timeout_s=cfg.assign_timeout_s,
    )

    tracker = None
    try:
        from ultralytics import tracking  # noqa: F401  # vérifie dispo
        have_tracker = True
    except Exception:
        have_tracker = False

    open_phone_events: dict[int, dict] = {}
    last_report_cooldown: dict[str, float] = {}
    frame_count = 0
    iou_tracker = SimpleIoUTracker(cfg.iou_threshold, conf_floor=cfg.conf_track)

    was_suspended = False
    while True:
        t0 = time.time()

        # Heartbeat RGPD : même en suspension, le worker reste vivant côté page RGPD.
        status_reporter.maybe_report()

        if not watcher.is_enabled():
            if not was_suspended:
                log.warning("algorithme désactivé pour %s — détection suspendue", cfg.camera_ip)
                was_suspended = True
            time.sleep(2.0)
            continue
        if was_suspended:
            # Reprise : remise à zéro des états (tracks périmés, événements ouverts).
            machines = StateMachines(cfg)
            iou_tracker = SimpleIoUTracker(cfg.iou_threshold, conf_floor=cfg.conf_track)
            open_phone_events.clear()
            last_report_cooldown.clear()
            was_suspended = False
            log.info("algorithme réactivé pour %s — détection reprise", cfg.camera_ip)

        ok, frame = source.read()
        if not ok or frame is None:
            log.warning("pas d'image caméra, reconnexion dans %.1fs", cfg.reconnect_delay_s)
            time.sleep(cfg.reconnect_delay_s)
            continue
        frame_count += 1

        detections = model.predict(frame)

        # Tracking : ByteTrack local si USE_LOCAL_MODEL=1, sinon SimpleIoUTracker
        # (mode HTTP de production) — les deux produisent des ids stables.
        if cfg.use_local_model and have_tracker:
            res = model._local.track(frame, persist=True, conf=0.30, iou=0.6, verbose=False)[0]
            detections = []
            names = model._local.names or {}
            if res.boxes is not None:
                for box in res.boxes:
                    cls_i = int(box.cls[0])
                    if names.get(cls_i) not in TRACKABLE_NAMES:
                        continue
                    det = {
                        "cls": cls_i,
                        "name": str(names.get(cls_i, cls_i)),
                        "conf": float(box.conf[0]),
                        "bbox": tuple(box.xyxy[0].tolist()),
                    }
                    det["tid"] = int(box.id[0]) if box.id is not None else -id(det)
                    detections.append(det)
            tracks = detections
        else:
            tracks = iou_tracker.update(detections)

        events = machines.update(tracks)
        for ev in events:
            kind = ev["event"]
            tid = ev["tid"]
            if kind == "phone_start":
                ok_wr, rel = True, ""
                rel = reporter.save_evidence(frame, f"phone_start_track{tid}")
                open_phone_events[tid] = {"start": ev["t"], "photos": [{"image": rel, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] if rel else []}
                log.info("phone_start track=%s", tid)
            elif kind == "phone_stop":
                ev_open = open_phone_events.pop(tid, None)
                if ev_open:
                    rel = reporter.save_evidence(frame, f"phone_stop_track{tid}")
                    photos = ev_open["photos"] + ([{"image": rel, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] if rel else [])
                    sent = reporter.send_report(
                        violation_found=True,
                        start=ev_open["start"],
                        stop=ev["t"],
                        photos=photos,
                        extra={"kind": "smartphone", "duration_s": ev.get("duration_s", 0), **(cfg.extra or {})},
                    )
                    log.info("phone_stop track=%s rapport=%s durée=%.0fs", tid, sent, ev.get("duration_s", 0))
            elif kind == "idle_alert":
                last = last_report_cooldown.get(f"idle_{tid}", 0)
                if time.time() - last > cfg.idle_seconds:
                    rel = reporter.save_evidence(frame, f"idle_track{tid}")
                    sent = reporter.send_report(
                        violation_found=True,
                        start=ev["t"] - ev.get("duration_s", 0),
                        stop=ev["t"],
                        photos=[{"image": rel, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] if rel else [],
                        extra={"kind": "idle", "idle": True, "duration_s": ev.get("duration_s"), **(cfg.extra or {})},
                    )
                    last_report_cooldown[f"idle_{tid}"] = time.time()
                    log.info("idle_alert track=%s rapport=%s durée=%.0fs", tid, sent, ev.get("duration_s", 0))

        if cfg.debug_frames and frame_count % 50 == 0:
            log.info("frame %s : %s détections, %s tracks", frame_count, len(detections), len(tracks))

        # cadence snapshot
        elapsed = time.time() - t0
        time.sleep(max(0.0, cfg.snapshot_interval_s - elapsed))


if __name__ == "__main__":
    run()
