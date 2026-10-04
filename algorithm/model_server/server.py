"""Serveur de modèles LeanLens : exposition POST /predict (JPEG -> détections JSON).

Équivalent de idle_python_server (port 5001) mais avec YOLO26/ultralytics natif.
Choisir les poids via MODEL_WEIGHTS (défaut best.pt monté dans le conteneur).
"""

from __future__ import annotations

import logging
import os
import time

import cv2
import numpy as np
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("leanlens-model")

MODEL_WEIGHTS = os.environ.get("MODEL_WEIGHTS", "best.pt")
CONF = float(os.environ.get("MODEL_CONF", "0.25"))
IMGSZ = int(os.environ.get("MODEL_IMGSZ", "640"))

app = Flask(__name__)
model = None
MODEL_LOAD_ERROR = None


def get_model():
    global model, MODEL_LOAD_ERROR
    if model is None and MODEL_LOAD_ERROR is None:
        try:
            from ultralytics import YOLO

            t0 = time.time()
            model = YOLO(MODEL_WEIGHTS)
            log.info("modèle %s chargé en %.1fs", MODEL_WEIGHTS, time.time() - t0)
        except Exception as exc:  # poids absents -> message clair
            MODEL_LOAD_ERROR = str(exc)
            log.error("chargement du modèle impossible : %s", exc)
    return model


@app.get("/health")
def health():
    return jsonify({
        "status": "ok" if (model is not None or get_model() is not None) else "degraded",
        "weights": MODEL_WEIGHTS,
        "error": MODEL_LOAD_ERROR,
    })


@app.post("/predict")
def predict():
    m = get_model()
    if m is None:
        return jsonify({"error": f"modèle indisponible : {MODEL_LOAD_ERROR}"}), 503
    file = request.files.get("image")
    if file is None:
        return jsonify({"error": "champ multipart 'image' manquant"}), 400
    buf = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "JPEG invalide"}), 400

    t0 = time.time()
    nms_free = os.environ.get("MODEL_NMS_FREE", "1") == "1"
    res = m.predict(frame, conf=CONF, imgsz=IMGSZ, verbose=False, nms=nms_free)[0]
    inference_ms = round((time.time() - t0) * 1000, 1)
    detections = []
    names = m.names or {}
    if res.boxes is not None:
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_i = int(box.cls[0])
            detections.append({
                "class_id": cls_i,
                "class_name": str(names.get(cls_i, cls_i)),
                "confidence": float(box.conf[0]),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            })
    return jsonify({"detections": detections, "ms": inference_ms})


if __name__ == "__main__":
    get_model()  # chargement anticipé
    app.run(host="0.0.0.0", port=int(os.environ.get("MODEL_PORT", "5000")), threaded=True)
