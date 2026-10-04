"""Export du modèle LeanLens (ONNX / OpenVINO / TensorRT) + benchmark latence.

Usage :
    python export_latency.py --weights best.pt --formats onnx openvino
    python export_latency.py --weights best.pt --benchmark --n 200
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from leanlens_common import TRAINING_DIR, load_model


def export(weights: str, formats: list[str], nms_free: bool, imgsz: int, device: str) -> dict:
    model = load_model(weights)
    out = {}
    for fmt in formats:
        try:
            kwargs = {}
            if fmt in {"onnx", "openvino", "engine"}:
                kwargs["nms"] = False if nms_free else True
            path = model.export(format=fmt, imgsz=imgsz, device=device or None, **kwargs)
            out[fmt] = str(path)
            print(f"[export] {fmt} -> {path}")
        except Exception as exc:  # TensorRT peut être absent
            out[fmt] = f"ERREUR: {exc}"
            print(f"[export] {fmt} a échoué : {exc}")
    return out


def benchmark(weights: str, n: int, imgsz: int, device: str) -> dict:
    model = load_model(weights)
    dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)

    # warmup
    for _ in range(10):
        model.predict(dummy, imgsz=imgsz, device=device or None, verbose=False, nms=False)

    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        model.predict(dummy, imgsz=imgsz, device=device or None, verbose=False, nms=False)
        latencies.append((time.perf_counter() - t0) * 1000)

    arr = np.array(latencies)
    report = {
        "n": n,
        "imgsz": imgsz,
        "device": device or "auto",
        "latency_ms_mean": float(arr.mean()),
        "latency_ms_p50": float(np.percentile(arr, 50)),
        "latency_ms_p95": float(np.percentile(arr, 95)),
        "fps_mean": float(1000.0 / arr.mean()),
    }
    print(f"[benchmark] {report}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export + latence LeanLens")
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--formats", type=str, nargs="*", default=["onnx"],
                        choices=["onnx", "openvino", "engine", "torchscript", "coreml"])
    parser.add_argument("--nms-free", dest="nms_free", action="store_true", default=True,
                        help="Export end-to-end sans NMS (YOLO26, défaut)")
    parser.add_argument("--with-nms", dest="nms_free", action="store_false")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = {}
    report["exports"] = export(args.weights, args.formats, args.nms_free, args.imgsz, args.device)
    if args.benchmark:
        report["benchmark"] = benchmark(args.weights, args.n, args.imgsz, args.device)

    out = args.out or (TRAINING_DIR / "runs" / "export_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[export] rapport -> {out}")


if __name__ == "__main__":
    main()
