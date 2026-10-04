"""Évaluation LeanLens : précision, rappel, F1, mAP par classe + matrice de confusion.

Usage :
    python val.py --weights runs/train/leanlens_exp1/weights/best.pt
    python val.py --weights yolo26n.pt --split test
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from leanlens_common import TRAINING_DIR, extract_detection_metrics, load_model, resolve_dataset_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Évaluation LeanLens (val/test)")
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--split", type=str, default="test", choices=["val", "test"])
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="")
    parser.add_argument("--out", type=Path, default=None, help="JSON de sortie")
    args = parser.parse_args()

    dataset_yaml = resolve_dataset_yaml(args.dataset)
    os_env_workaround = TRAINING_DIR / ".ultralytics"  # YOLO_CONFIG_DIR si absent
    import os

    os.environ.setdefault("YOLO_CONFIG_DIR", str(os_env_workaround))

    model = load_model(args.weights)
    metrics = model.val(
        data=str(dataset_yaml),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        plots=True,
    )

    summary = extract_detection_metrics(metrics)
    out = args.out or (TRAINING_DIR / "runs" / f"val_{args.split}_metrics.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[val] per-class summary ->", out)
    for name, entry in (summary.get("per_class") or {}).items():
        print(f"  {name}: {entry}")


if __name__ == "__main__":
    main()
