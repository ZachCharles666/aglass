"""Validate trained models: mAP metrics + inference speed estimation.

Runs validation on the test/val split and reports:
  - mAP@50, mAP@50-95
  - Model size
  - Inference speed (local measurement)

Usage:
    python training/validate_models.py
    python training/validate_models.py --model plant_detector
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
DATASETS_DIR = PROJECT_ROOT / "training" / "datasets"

MODELS = {
    "plant_detector": {
        "pt": MODELS_DIR / "plant_detector_v1.pt",
        "dataset": DATASETS_DIR / "plantdoc",
    },
    "flower_detector": {
        "pt": MODELS_DIR / "flower_detector_v1.pt",
        "dataset": DATASETS_DIR / "flower",
    },
}


def find_data_yaml(dataset_dir: Path) -> Path | None:
    for name in ("data.yaml", "dataset.yaml"):
        p = dataset_dir / name
        if p.exists():
            return p
    found = list(dataset_dir.rglob("data.yaml"))
    return found[0] if found else None


def validate_model(name: str, config: dict) -> dict | None:
    """Run validation on a single model, return metrics."""
    pt_path = config["pt"]
    if not pt_path.exists():
        print(f"SKIP {name}: {pt_path} not found")
        return None

    data_yaml = find_data_yaml(config["dataset"])
    if not data_yaml:
        print(f"SKIP {name}: no data.yaml found in {config['dataset']}")
        return None

    print(f"\n{'='*60}")
    print(f"Validating {name}")
    print(f"{'='*60}")

    model = YOLO(str(pt_path))
    size_mb = pt_path.stat().st_size / 1e6
    print(f"  Model: {pt_path} ({size_mb:.1f} MB)")

    # Validation metrics
    results = model.val(data=str(data_yaml), imgsz=640, batch=16)

    map50 = results.results_dict.get("metrics/mAP50(B)", 0)
    map50_95 = results.results_dict.get("metrics/mAP50-95(B)", 0)

    # Inference speed: average over a few dummy runs
    speeds = []
    for _ in range(5):
        import numpy as np
        dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        t0 = time.perf_counter()
        model.predict(dummy, imgsz=640, verbose=False)
        speeds.append(time.perf_counter() - t0)
    avg_speed_ms = sum(speeds) / len(speeds) * 1000

    metrics = {
        "model": name,
        "file": str(pt_path),
        "size_mb": round(size_mb, 1),
        "mAP50": round(map50, 4),
        "mAP50_95": round(map50_95, 4),
        "inference_ms_local": round(avg_speed_ms, 1),
        "imgsz": 640,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    print(f"\n  Results:")
    print(f"    mAP@50:       {metrics['mAP50']:.4f}")
    print(f"    mAP@50-95:    {metrics['mAP50_95']:.4f}")
    print(f"    Size:          {metrics['size_mb']} MB")
    print(f"    Inference:     {metrics['inference_ms_local']} ms (local)")

    passed = metrics["mAP50"] > 0.5 and metrics["size_mb"] < 15
    status = "PASS" if passed else "FAIL"
    print(f"    Status:        {status}")
    if metrics["mAP50"] <= 0.5:
        print(f"    WARNING: mAP@50 below 0.5 threshold")
    if metrics["size_mb"] >= 15:
        print(f"    WARNING: model size exceeds 15 MB limit")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate trained models")
    parser.add_argument("--model", choices=list(MODELS.keys()), help="Validate single model")
    args = parser.parse_args()

    models = {args.model: MODELS[args.model]} if args.model else MODELS
    all_metrics = []

    for name, config in models.items():
        m = validate_model(name, config)
        if m:
            all_metrics.append(m)

    # Save validation report
    if all_metrics:
        report_path = PROJECT_ROOT / "training" / "validation_report.json"
        with open(report_path, "w") as f:
            json.dump(all_metrics, f, indent=2)
        print(f"\nValidation report saved to {report_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
