"""Sweep empirique du split test via le serveur de modèles EN VIE.

Poste chaque image du split test à http://localhost:5000/predict et classe
les images par nombre de détections. Les candidates « scène working » sont
celles à zéro détection (et l'on affiche la meilleure conf par image pour
vérifier la marge par rapport au plancher de track CONF_TRACK=0.35).

Usage :  python demo/sweep_working_scene.py [--limit 150]
"""
from __future__ import annotations

import argparse
import mimetypes
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

URL = "http://localhost:5000/predict"
TEST_DIR = Path(__file__).resolve().parent.parent / "training" / "data" / "images" / "test"


def post_image(path: Path) -> dict:
    boundary = "----LeanLensSweep"
    with open(path, "rb") as fh:
        data = fh.read()
    ctype = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        URL, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    args = ap.parse_args()

    images = sorted(TEST_DIR.glob("*.jpg"))[: args.limit]
    if not images:
        print(f"pas d'images dans {TEST_DIR}", file=sys.stderr)
        return 1

    results = []
    for i, img in enumerate(images):
        try:
            det = post_image(img).get("detections", [])
        except urllib.error.URLError as exc:
            print(f"serveur injoignable ({exc}) — le stack est-il démarré ?", file=sys.stderr)
            return 2
        results.append((img.name, len(det), max((d["confidence"] for d in det), default=0.0),
                        Counter(d["class_name"] for d in det)))
        if (i + 1) % 25 == 0:
            print(f"  … {i + 1}/{len(images)}", file=sys.stderr)

    zeros = [r for r in results if r[1] == 0]
    print(f"\n=== {len(zeros)}/{len(results)} images à zéro détection ===")
    for name, n, maxc, classes in zeros:
        print(f"  {name}")
    print("\n=== 15 plus proches de zéro (n_det, max_conf) ===")
    for name, n, maxc, classes in sorted(results, key=lambda r: (r[1], -r[2]))[:15]:
        print(f"  {n} det  conf_max={maxc:.3f}  {dict(classes)}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
