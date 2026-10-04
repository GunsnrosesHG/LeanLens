"""Utilitaires communs LeanLens PFE.

Fonctions partagées entre train.py / val.py / calibrate_confidence.py /
export_latency.py / realtime_demo.py : résolution du dataset YAML, chargement
du modèle, extraction des métriques de validation (précision, rappel, F1,
mAP50, mAP50-95), métriques rapportées par classe.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ultralytics import YOLO
except Exception:  # ultralytics peut être absent à l'écriture des scripts
    YOLO = None

YOLO_NAMES = ["person_phone", "smartphone", "person_idle"]
CONF_TARGET = 0.84
DEFAULT_WEIGHTS = {"yolo26n": "yolo26n.pt", "yolo26s": "yolo26s.pt", "yolov8n": "yolov8n.pt"}
DEFAULT_SIZES = ["n", "s"]

HERE = Path(__file__).resolve().parent
TRAINING_DIR = HERE
PROJECT_ROOT = HERE.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__ or "LeanLens PFE training toolkit")
    parser.add_argument("--dataset", type=Path, default=None,
                        help="Dataset YAML (default: training/configs/leanlens.yaml)")
    parser.add_argument("--weights", type=str, default=None,
                        help="Poids .pt pour fine-tuning (yolo26s.pt, yolov8n.pt, ...)")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="Répertoire runs/ pour les sorties Ultralytics")
    return parser.parse_args()


def resolve_dataset_yaml(path: Optional[Path] = None) -> Path:
    """Copie configs/leanlens.yaml en écrivant `path` = chemin absolu de data/."""
    import yaml

    cfg_path = Path(path) if path else HERE / "configs" / "leanlens.yaml"
    data_dir = HERE / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["path"] = str(data_dir.resolve())

    out_dir = data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "leanlens_resolved.yaml"
    out.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    print(f"[leanlens] dataset yaml -> {out}")
    return out


def load_model(weights: str):
    if YOLO is None:
        raise RuntimeError("ultralytics non installé (pip install -r requirements.txt)")
    return YOLO(weights)


def extract_detection_metrics(metrics) -> Dict[str, Any]:
    """Extraction défensive : accepte un objet Ultralytics metrics, renvoie dict."""
    def _get(obj, names: List[str], default=None):
        for name in names:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
            if hasattr(obj, name):
                return getattr(obj, name)
        return default

    box = getattr(metrics, "box", None)
    out = {
        "precision": float(_get(box, ["mp", "precision"], 0.0) or 0.0),
        "recall": float(_get(box, ["mr", "recall"], 0.0) or 0.0),
        "mAP50": float(_get(box, ["map50"], 0.0) or 0.0),
        "mAP50_95": float(_get(box, ["map"], 0.0) or 0.0),
        "per_class": {},
    }
    # le détail par classe dépend de la version d'Ultralytics
    names = _get(box, ["names"], None) or getattr(metrics, "names", {})
    ap50 = _get(box, ["ap50"], None)
    ap = _get(box, ["ap"], None)
    p = _get(box, ["p"], None)
    r = _get(box, ["r"], None)
    f1 = _get(box, ["f1"], None)
    if ap50 is not None:
        # Ultralytics ne renvoie les courbes que pour les classes présentes dans
        # le split (ap_class_index) : indexer par ligne, pas par id de classe.
        ap_class = _get(box, ["ap_class_index"], None)
        rows = [int(c) for c in ap_class] if ap_class is not None else list(range(len(ap50)))
        for row, cls_id in enumerate(rows):
            if isinstance(names, dict):
                name = names.get(cls_id, str(cls_id))
            elif names and cls_id < len(names):
                name = names[cls_id]
            else:
                name = str(cls_id)
            entry: Dict[str, Any] = {"ap50": float(ap50[row])}
            if ap is not None and len(ap) > row:
                entry["ap50_95"] = float(ap[row].mean()) if hasattr(ap[row], "mean") else float(ap[row])
            if p is not None and len(p) > row:
                entry["precision"] = float(p[row].mean()) if hasattr(p[row], "mean") else float(p[row])
            if r is not None and len(r) > row:
                entry["recall"] = float(r[row].mean()) if hasattr(r[row], "mean") else float(r[row])
            if f1 is not None and len(f1) > row:
                entry["f1"] = float(f1[row].mean()) if hasattr(f1[row], "mean") else float(f1[row])
            out["per_class"][str(name)] = entry
    return out


def summarize(metrics: Dict[str, Any]) -> str:
    lines = [
        f"precision={metrics.get('precision', 0):.4f}",
        f"recall={metrics.get('recall', 0):.4f}",
        f"mAP50={metrics.get('mAP50', 0):.4f}",
        f"mAP50-95={metrics.get('mAP50_95', 0):.4f}",
    ]
    for name, entry in (metrics.get("per_class") or {}).items():
        lines.append(f"  {name}: {entry}")
    return " | ".join(lines)
