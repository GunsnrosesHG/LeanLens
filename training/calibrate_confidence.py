"""Calibration du seuil de confiance : objectif ≥ 84 % de confiance par classe.

Le « taux de confiance ≥ 84 % » du cahier des charges se traduit en pratique par :
1. un seuil de confiance de déploiement choisi pour maximiser le F1 (ou atteindre
   une précision cible) — courbe P/R/F1 en fonction du seuil ;
2. la confiance moyenne des prédictions retenues sur le jeu de test, qui doit
   rester ≥ 0.84 sans sacrifier le rappel.

Usage :
    python calibrate_confidence.py --weights runs/train/leanlens_exp1/weights/best.pt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from leanlens_common import CONF_TARGET, TRAINING_DIR, load_model, resolve_dataset_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibration seuil de confiance LeanLens")
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--split", type=str, default="test", choices=["val", "test"])
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    dataset_yaml = resolve_dataset_yaml(args.dataset)
    model = load_model(args.weights)
    names = model.names or {}

    # Passe 1 : confiance moyenne des détections retenues, par seuil
    data_dir = Path(resolve_dataset_yaml(args.dataset)).parent
    test_images_dir = data_dir / "images" / args.split
    test_images = sorted(
        p for p in test_images_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    ) if test_images_dir.exists() else []

    conf_by_thresh = {}
    if test_images:
        thresholds = np.round(np.arange(0.30, 0.96, 0.02), 2)
        for t in thresholds:
            conf_by_thresh[float(t)] = []
        results = model.predict(
            source=[str(p) for p in test_images],
            imgsz=args.imgsz,
            device=args.device,
            conf=0.30,
            iou=0.6,
            verbose=False,
            stream=True,
        )
        for res in results:
            for conf in res.boxes.conf.tolist():
                for t in thresholds:
                    if conf >= t:
                        conf_by_thresh[float(t)].append(conf)

    # Passe 2 : P/R/F1 par seuil via model.val()
    metrics_by_threshold = {}
    for t in np.round(np.arange(0.30, 0.96, 0.02), 2):
        m = model.val(
            data=str(dataset_yaml),
            split=args.split,
            conf=float(t),
            iou=0.6,
            imgsz=args.imgsz,
            device=args.device,
            plots=False,
            verbose=False,
        )
        p, r = float(m.box.mp), float(m.box.mr)
        f1 = 2 * p * r / max(p + r, 1e-9)
        confs = conf_by_thresh.get(float(t), [])
        metrics_by_threshold[float(t)] = {
            "precision": p,
            "recall": r,
            "f1": f1,
            "mean_conf": float(np.mean(confs)) if confs else 0.0,
        }

    best = max(metrics_by_threshold.items(), key=lambda kv: kv[1]["f1"])
    report = {
        "conf_target": CONF_TARGET,
        "best_f1_threshold": best[0],
        "best_f1": best[1],
        "metrics_by_threshold": metrics_by_threshold,
    }

    out = args.out or (TRAINING_DIR / "runs" / "calibration_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[calibrate] best F1={best[1]['f1']:.4f} au seuil {best[0]:.2f}")
    print(f"[calibrate] rapport -> {out}")
    print("[calibrate] NB : la confiance moyenne des détections retenues doit rester >= 0.84 "
          "— voir metrics_by_threshold[t]['mean_conf'].")


if __name__ == "__main__":
    main()
