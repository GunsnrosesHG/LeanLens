"""Fake ONVIF snapshot camera pour la démo PFE (port 6001).

Endpoints :
  GET /snapshot            -> JPEG de la scène courante
  POST /mode  {"mode": "phone"|"idle"|"working"}   -> change de scène
  GET  /mode               -> scène courante
  GET  /preview?mode=X     -> JPEG de la scène X sans changer de mode

Scènes = PHOTOS RÉELLES du split test montées dans /scenes (lecture seule).
Les scènes dessinées de la V1 étaient hors distribution pour le modèle
entraîné (0 détection) ; les photos retenues le sont par mesure réelle des
prédictions de best.pt — cf. demo/pick_scenes.py :
  phone   : person_phone détecté (usage smartphone en cours)
  idle    : personne détectée, AUCUN smartphone (machine idle -> alerte 30 s)
  working : aucune détection (pause « travail normal »)

Fallback : si le montage /scenes manque, on retombe sur la scène dessinée.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

_state = {"mode": "phone"}
_lock = threading.Lock()

SCENES_DIR = Path(os.environ.get("SCENES_DIR", "/scenes"))
SCENE_FILES = {
    "phone": os.environ.get("PHONE_IMG", "coco_000000122962.jpg"),
    "idle": os.environ.get("IDLE_IMG", "coco_000000157767.jpg"),
    "working": os.environ.get("WORKING_IMG", "coco_000000022623.jpg"),
}

# V1 (fallback) : scène dessinée si les photos réelles ne sont pas montées
SKIN = (150, 200, 230)
SHIRT = (60, 60, 180)
DESK = (120, 130, 140)
WALL = (215, 225, 235)
PHONE = (20, 20, 25)


def _fallback_scene(mode: str) -> np.ndarray:
    H, W = 480, 640
    img = np.full((H, W, 3), WALL, dtype=np.uint8)
    cv2.rectangle(img, (0, 330), (W, H), DESK, -1)
    if mode == "working":
        return img
    cv2.circle(img, (250, 140), 34, SKIN, -1)
    cv2.rectangle(img, (195, 174), (305, 364), SHIRT, -1)
    if mode == "phone":
        cv2.rectangle(img, (365, 205), (425, 295), PHONE, -1)
    return img


_cache: dict[str, bytes | None] = {}


def _scene_jpeg(mode: str) -> bytes:
    if mode not in _cache:
        path = SCENES_DIR / SCENE_FILES.get(mode, "")
        if path.is_file():
            _cache[mode] = path.read_bytes()
        else:
            ok, buf = cv2.imencode(".jpg", _fallback_scene(mode),
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            _cache[mode] = buf.tobytes() if ok else b""
    return _cache[mode] or _fallback_scene(mode).tobytes()


@app.get("/snapshot")
def snapshot():
    with _lock:
        mode = _state["mode"]
    return Response(_scene_jpeg(mode), mimetype="image/jpeg")


@app.get("/preview")
def preview():
    mode = request.args.get("mode", "phone")
    if mode not in SCENE_FILES:
        return jsonify({"error": f"mode inconnu, choisir parmi {list(SCENE_FILES)}"}), 400
    return Response(_scene_jpeg(mode), mimetype="image/jpeg")


@app.post("/mode")
def set_mode():
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "")
    if mode not in SCENE_FILES:
        return jsonify({"error": f"mode inconnu, choisir parmi {list(SCENE_FILES)}"}), 400
    with _lock:
        _state["mode"] = mode
    return jsonify({"mode": mode})


@app.get("/mode")
def get_mode():
    with _lock:
        return jsonify({"mode": _state["mode"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6001, threaded=True)
