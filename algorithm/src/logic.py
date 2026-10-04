import time
from collections import deque

import numpy as np

from config import Config

PERSON_PHONE = 0
SMARTPHONE = 1
PERSON_IDLE = 2


class PhoneState:
    """État smartphone par track : requiert min_hits détections pour s'ouvrir."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.open = False
        self.started_at: float | None = None


class StateMachines:
    """Fusionne détections par track-id et décrit les évènements start/stop."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.phone: dict[int, PhoneState] = {}
        self.centers: dict[int, deque] = deque(maxlen=4096)  # (tid, t, cx, cy) en deque
        self.centers_by_track: dict[int, deque] = {}
        self._tid_seen: set[int] = set()

    def update(self, tracks: list[dict]) -> list[dict]:
        """tracks: [{tid, cls, conf, bbox, t}] -> évènements {'event': 'phone_start'|'phone_stop'|'idle_alert', ...}"""
        events = []
        now = time.time()
        seen_now = set()

        for tr in tracks:
            tid = tr["tid"]
            cls = tr["cls"]
            conf = tr["conf"]
            x1, y1, x2, y2 = tr["bbox"]
            seen_now.add(tid)

            if cls == SMARTPHONE:
                st = self.phone.setdefault(tid, PhoneState())
                if conf >= self.cfg.conf_phone:
                    st.hits += 1
                    st.misses = 0
                    if not st.open and st.hits >= self.cfg.phone_min_hits:
                        st.open = True
                        st.started_at = now
                        events.append({"event": "phone_start", "tid": tid, "t": now, "bbox": (x1, y1, x2, y2)})
            elif cls in (PERSON_PHONE, PERSON_IDLE, SMARTPHONE):
                pass

            # historique de mouvement (toutes classes confondues)
            # fenêtre dimensionnée sur l'intervalle snapshot (pas un fps arbitraire)
            maxlen = max(20, int(self.cfg.idle_seconds / max(self.cfg.snapshot_interval_s, 0.1)) + 10)
            hist = self.centers_by_track.setdefault(tid, deque(maxlen=maxlen))
            hist.append((now, (x1 + x2) / 2, (y1 + y2) / 2))
            self._tid_seen.add(tid)

        # fermeture des états smartphone
        for tid, st in self.phone.items():
            if tid not in seen_now:
                st.misses += 1
                if st.open and st.misses >= self.cfg.phone_misses_to_end:
                    events.append({
                        "event": "phone_stop",
                        "tid": tid,
                        "t": now,
                        "started_at": st.started_at,
                        "duration_s": now - (st.started_at or now),
                    })
                    st.open = False
                    st.hits = 0
                    st.misses = 0

        # idle : tracks personnelles SANS mouvement significatif.
        # Gate sur seen_now : un track qui a disparu de la scène ne doit plus
        # émettre d'alerte idle (son historique gelé resterait sinon statique
        # et réémettrait à chaque cooldown — bug détecté en démo J5).
        for tid, hist in self.centers_by_track.items():
            if not hist or tid not in seen_now:
                continue
            t0 = hist[0][0]
            duration = now - t0
            if duration < self.cfg.idle_seconds:
                continue
            pts = np.array([(x, y) for _, x, y in hist])
            movement = float(np.max(np.linalg.norm(pts - pts.mean(axis=0), axis=1)))
            if movement < self.cfg.idle_move_tolerance_px and not self.phone.get(tid, PhoneState()).open:
                events.append({"event": "idle_alert", "tid": tid, "t": now, "duration_s": duration})

        # purge des tracks disparus depuis longtemps
        if len(self._tid_seen) > 512:
            keep = set(seen_now)
            for tid in list(self.centers_by_track):
                if tid not in keep:
                    self.centers_by_track.pop(tid, None)
            for tid in list(self.phone):
                if tid not in keep and not self.phone[tid].open:
                    self.phone.pop(tid, None)
            self._tid_seen = keep

        return events
