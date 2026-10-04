"""Pilote de scénario de démo PFE.

La caméra factice (fake-camera:6001) sert trois scènes ; le mode « working »
(bureau vide) n'engendre aucune détection donc aucune violation — il sert de
pause naturelle entre deux scénarios.

Endpoints UI (port 6002) :
  GET  /               -> panneau de contrôle
  POST /mode           -> {"mode": "phone"|"idle"|"working"} : change la scène
  GET  /scene_preview  -> JPEG de la scène caméra courante
  GET  /reports        -> compteurs Django (lecture directe Postgres)

Le driver se connecte à Postgres en direct (psycopg) — pas besoin du CLI
docker ni du socket : lecture seule, table report.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)

FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<circle cx="16" cy="16" r="13" fill="#0b1016" stroke="#3d8bfd" stroke-width="4"/>'
    '<circle cx="16" cy="16" r="5" fill="#7ab8ff"/></svg>'
)


@app.get("/favicon.ico")
def favicon():
    return Response(FAVICON_SVG, mimetype="image/svg+xml")

CAMERA_URL = os.environ.get("CAMERA_URL", "http://fake-camera:6001")
PG_DSN = os.environ.get(
    "PG_DSN",
    "host=db port=5432 dbname=leanlens user=leanlens password=leanlens-pfe",
)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/mode")
def set_mode():
    data = request.get_json(force=True, silent=True) or {}
    r = requests.post(f"{CAMERA_URL}/mode", json=data, timeout=5)
    return jsonify(r.json()), r.status_code


@app.get("/scene_preview")
def scene_preview():
    r = requests.get(f"{CAMERA_URL}/snapshot", timeout=5)
    return Response(r.content, mimetype="image/jpeg")


@app.post("/reset")
def reset_demo():
    """Remise à zéro : rapports, photos, événements du scénario en cours."""
    deleted = {"reports": 0, "photos": 0}
    try:
        with psycopg.connect(PG_DSN, connect_timeout=5) as conn:
            deleted["photos"] = conn.execute("DELETE FROM images_reports").rowcount
            deleted["reports"] = conn.execute("DELETE FROM report").rowcount
            conn.commit()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503
    img_dir = Path("/var/www/leanlens/images/192.168.1.64")
    if img_dir.is_dir():
        for f in img_dir.iterdir():
            if f.is_file():
                f.unlink()
                deleted["photos"] += 1
    return jsonify({"ok": True, **deleted})


@app.get("/reports")
def report_counts():
    """KPIs pour le panneau : total, par type (extra->>'kind'), preuves photo."""
    try:
        with psycopg.connect(PG_DSN, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT COUNT(*), "
                "COALESCE(SUM(CASE WHEN violation_found THEN 1 ELSE 0 END), 0), "
                "COALESCE(SUM(CASE WHEN extra->>'kind' = 'smartphone' THEN 1 ELSE 0 END), 0), "
                "COALESCE(SUM(CASE WHEN extra->>'kind' = 'idle' "
                "OR COALESCE(extra->>'idle','false') = 'true' THEN 1 ELSE 0 END), 0) "
                "FROM report"
            ).fetchone()
            photos = conn.execute(
                "SELECT COUNT(*) FROM images_reports"
            ).fetchone()
        return jsonify({
            "total": row[0],
            "violations": row[1],
            "phone": row[2],
            "idle": row[3],
            "photos": photos[0],
        })
    except Exception as exc:  # base pas encore prête, etc.
        return jsonify({"error": str(exc), "total": 0, "violations": 0,
                        "phone": 0, "idle": 0, "photos": 0})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6002, threaded=True)
