"""Choix des scènes de démo à partir du split test RÉEL.

Pour chaque image du split test, interroge le model server (best.pt entraîné)
et catégorise :
  - phone   : plus forte détection `person_phone` (scène « usage smartphone »)
  - idle    : détection personnelle stable SANS `smartphone` au-dessus du seuil
              (la machine idle suit toute classe -> alerte sans rapport phone)
  - working : aucune détection au-dessus du seuil (pause « travail normal »)

Usage :
    python demo/pick_scenes.py [--url http://127.0.0.1:5000] [--conf 0.4]

Sortie : bloc YAML prêt à coller dans docker-compose.pfe.yml (env du fake camera).
"""
from __future__ import annotations

import argparse
import json
import urllib.request
import uuid
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent.parent / "training" / "data" / "images" / "test"
LABEL_DIR = Path(__file__).resolve().parent.parent / "training" / "data" / "labels" / "test"

PERSON_PHONE, SMARTPHONE = 0, 1


def predict(url: str, jpg: bytes) -> list[dict]:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="f.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + jpg + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url + "/predict", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("detections", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5000")
    ap.add_argument("--conf", type=float, default=0.4)
    args = ap.parse_args()

    rows = []
    for img in sorted(TEST_DIR.glob("*.jpg")):
        jpg = img.read_bytes()
        dets = [d for d in predict(args.url, jpg) if d.get("confidence", 0) >= args.conf]
        pp = [d for d in dets if d.get("class_id") == PERSON_PHONE]
        sm = [d for d in dets if d.get("class_id") == SMARTPHONE]
        rows.append({
            "file": img.name,
            "n": len(dets),
            "pp_max": max((d["confidence"] for d in pp), default=0.0),
            "sm_max": max((d["confidence"] for d in sm), default=0.0),
            "classes": sorted({d.get("class_id") for d in dets}),
        })
        print(f"{img.name:32s} dets={len(dets)} "
              f"person_phone={rows[-1]['pp_max']:.2f} smartphone={rows[-1]['sm_max']:.2f}")

    def pick(pred):
        # scène la plus « propre » : le moins de détections parasites possible
        cands = sorted((r for r in rows if pred(r)), key=lambda r: (r["n"], -max(r["pp_max"], r["sm_max"])))
        return cands[0]["file"] if cands else None

    # phone : la machine phone_start exige des hits sur un track SMARTPHONE
    # -> il faut les DEUX classes dans la scène (personne + smartphone)
    phone = pick(lambda r: r["pp_max"] > 0 and r["sm_max"] > 0)
    idle = pick(lambda r: r["pp_max"] > 0 and r["sm_max"] == 0.0 and r["file"] != phone)
    working = pick(lambda r: r["n"] == 0)

    print("\n# === scènes retenues (à coller dans docker-compose.pfe.yml) ===")
    print(f"PHONE_IMG:   {phone}")
    print(f"IDLE_IMG:    {idle}")
    print(f"WORKING_IMG: {working}")


if __name__ == "__main__":
    main()
