"""Démo temps réel : webcam / RTSP / fichier vidéo, détection 3 classes + idle.

- Seuil de confiance par classe (défaut 0.84, objectif cahier des charges).
- Tracking ByteTrack (track_ids) + lissage par moyenne glissante.
- Détection idle : une personne-track sans mouvement significatif du centre
  de sa boîte pendant idle_seconds est affichée « IDLE ».
- Superposition boîtes + labels, affichage/écriture vidéo.

Usage :
    python realtime_demo.py --source 0
    python realtime_demo.py --source rtsp://user:pass@192.168.1.64/Streaming/Channels/101
    python realtime_demo.py --source video.mp4 --save out.mp4
"""

from __future__ import annotations

import argparse
import collections
import time
from pathlib import Path

import cv2
import numpy as np

from leanlens_common import CONF_TARGET, load_model

CLASS_COLORS = {
    0: (60, 180, 75),    # person_phone  - vert
    1: (255, 140, 0),    # smartphone    - orange
    2: (0, 90, 255),     # person_idle   - rouge
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Démo temps réel LeanLens")
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--source", type=str, default="0",
                        help="index webcam, chemin vidéo ou URL RTSP")
    parser.add_argument("--conf", type=float, default=CONF_TARGET)
    parser.add_argument("--conf-smartphone", type=float, default=None,
                        help="seuil spécifique classe smartphone (occlusions)")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="")
    parser.add_argument("--tracker", type=str, default="bytetrack.yaml")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--smooth", type=int, default=5,
                        help="fenêtre de lissage des confiances (frames)")
    parser.add_argument("--save", type=str, default=None, help="chemin mp4 de sortie")
    parser.add_argument("--show", action="store_true", default=True)
    parser.add_argument("--no-show", dest="show", action="store_false")
    return parser.parse_args()


class IdleWatcher:
    """Détecte l'immobilité d'un track (centre de boîte) sur idle_seconds."""

    def __init__(self, idle_seconds: float, fps_estimate: float = 15.0):
        self.idle_seconds = idle_seconds
        self.centers: dict[int, collections.deque] = {}
        self.times: dict[int, collections.deque] = {}
        self.fps_estimate = fps_estimate
        self.maxlen = int(max(2, idle_seconds * fps_estimate))

    def update(self, track_id: int, center: tuple[float, float], now: float) -> bool:
        self.centers.setdefault(track_id, collections.deque(maxlen=self.maxlen))
        self.times.setdefault(track_id, collections.deque(maxlen=self.maxlen))
        self.centers[track_id].append(center)
        self.times[track_id].append(now)
        if len(self.times[track_id]) < 2:
            return False
        duration = self.times[track_id][-1] - self.times[track_id][0]
        if duration < self.idle_seconds * 0.9:
            return False
        pts = np.array(self.centers[track_id])
        movement = float(np.max(np.linalg.norm(pts - pts.mean(axis=0), axis=1)))
        return movement < 15.0  # px : quasi-immobile

    def forget_missing(self, active_ids: set[int]) -> None:
        for tid in list(self.centers):
            if tid not in active_ids:
                self.centers.pop(tid, None)
                self.times.pop(tid, None)


def draw(frame, box, label: str, color, conf: float):
    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label} {conf * 100:.1f}%"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
    cv2.putText(frame, text, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 2, cv2.LINE_AA)


def main() -> None:
    args = parse_args()
    model = load_model(args.weights)
    names = model.names or {}
    smartphone_cls = next((k for k, v in names.items() if v == "smartphone"), None)

    src = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f"Impossible d'ouvrir la source {args.source}")

    fps_in = cap.get(cv2.CAP_PROP_FPS) or 15.0
    watcher = IdleWatcher(args.idle_seconds, fps_estimate=max(fps_in, 1.0))
    conf_history: dict[int, collections.deque] = {}

    writer = None
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"),
                                 max(fps_in, 1.0), (width, height))

    frame_idx = 0
    t_prev = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1

        results = model.track(
            frame,
            persist=True,
            tracker=args.tracker,
            imgsz=args.imgsz,
            conf=0.30,          # on garde les détections brutes, filtre après lissage
            iou=0.6,
            device=args.device or None,
            verbose=False,
        )
        res = results[0]
        active_ids = set()
        annotations = []
        if res.boxes is not None and len(res.boxes):
            for box, conf, cls, tid in zip(
                res.boxes.xyxy.tolist(),
                res.boxes.conf.tolist(),
                res.boxes.cls.tolist(),
                (res.boxes.id.int().tolist() if res.boxes.id is not None else [None] * len(res.boxes)),
            ):
                cls_i = int(cls)
                cname = names.get(cls_i, str(cls_i))
                thresh = args.conf_smartphone if (cls_i == smartphone_cls and args.conf_smartphone) else args.conf
                h = conf_history.setdefault(tid, collections.deque(maxlen=args.smooth)) if tid is not None else None
                if h is not None:
                    h.append(conf)
                    conf_s = float(np.mean(h))
                else:
                    conf_s = conf
                if conf_s < thresh:
                    continue
                x1, y1, x2, y2 = box
                center = ((x1 + x2) / 2, (y1 + y2) / 2)
                now = frame_idx / max(fps_in, 1.0)
                is_idle = watcher.update(tid, center, now) if tid is not None else False
                if cname == "person_phone":
                    label = "PERSONNE + SMARTPHONE"
                elif cname == "person_idle" or is_idle:
                    label = "IDLE"
                    cname = 2
                else:
                    label = "SMARTPHONE" if cname == "smartphone" else cname.upper()
                active_ids.add(tid)
                annotations.append((box, label, CLASS_COLORS.get(cname, (200, 200, 200)), conf_s))

        watcher.forget_missing(active_ids)

        fps = 1.0 / max(time.perf_counter() - t_prev, 1e-6)
        t_prev = time.perf_counter()
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        for box, label, color, conf_s in annotations:
            draw(frame, box, label, color, conf_s)

        if writer is not None:
            writer.write(frame)
        if args.show:
            cv2.imshow("LeanLens", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
