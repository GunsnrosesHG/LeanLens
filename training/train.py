"""Fine-tuning YOLO26 / YOLOv8 sur le dataset LeanLens (3 classes).

Usage :
    python train.py --weights yolo26s.pt --epochs 150 --imgsz 640 --batch 16
    python train.py --weights yolo26n.pt --epochs 150 --device 0

Le dataset est lu depuis training/data (images/ + labels/, split train/val/test),
config copiée/auto-résolue depuis configs/leanlens.yaml.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from leanlens_common import (
    DEFAULT_WEIGHTS,
    TRAINING_DIR,
    extract_detection_metrics,
    load_model,
    resolve_dataset_yaml,
)


def parse_train_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tuning LeanLens (YOLO26 / YOLOv8)")
    parser.add_argument("--dataset", type=Path, default=None,
                        help="Dataset YAML (default: training/configs/leanlens.yaml)")
    parser.add_argument("--weights", type=str, default=None,
                        help="Poids .pt de départ (yolo26n.pt, yolo26s.pt, yolov8n.pt, ...)")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="Répertoire de sortie des runs (default: training/runs)")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="",
                        help="'' = auto, '0' = GPU 0, 'cpu'")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--name", type=str, default="leanlens_exp1")
    parser.add_argument("--no-amp", dest="amp", action="store_false", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_train_args()
    dataset_yaml = resolve_dataset_yaml(args.dataset)

    weights = args.weights or DEFAULT_WEIGHTS["yolo26n"]
    run_dir = (args.run_dir or (TRAINING_DIR / "runs")).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(TRAINING_DIR / ".ultralytics"))

    model = load_model(weights)
    results = model.train(
        data=str(dataset_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
        project=str(run_dir / "train"),
        name=args.name,
        seed=42,
        deterministic=True,
        amp=args.amp,
        val=True,
        plots=True,
    )

    metrics = extract_detection_metrics(results)
    out_json = run_dir / "train" / args.name / "leanlens_train_metrics.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[train] metrics -> {out_json}")
    print("[train] best weights ->", run_dir / "train" / args.name / "weights" / "best.pt")


if __name__ == "__main__":
    main()
