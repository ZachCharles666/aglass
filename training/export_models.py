"""Export trained models to ONNX and NCNN formats for edge deployment.

ONNX: universal format, works on any platform
NCNN: optimized for Raspberry Pi ARM inference

Usage:
    python training/export_models.py
    python training/export_models.py --format onnx       # ONNX only
    python training/export_models.py --format ncnn       # NCNN only
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

MODELS = {
    "plant_detector": MODELS_DIR / "plant_detector_v1.pt",
    "flower_detector": MODELS_DIR / "flower_detector_v1.pt",
}

EXPORT_FORMATS = ["onnx", "ncnn"]


def export_model(name: str, pt_path: Path, formats: List[str]) -> None:
    """Export a single model to the specified formats."""
    if not pt_path.exists():
        print(f"SKIP {name}: {pt_path} not found (train first)")
        return

    print(f"\n{'='*60}")
    print(f"Exporting {name}: {pt_path}")
    print(f"{'='*60}")

    model = YOLO(str(pt_path))

    # Print model info
    info = model.info()
    size_mb = pt_path.stat().st_size / 1e6
    print(f"  PT size:   {size_mb:.1f} MB")
    print(f"  Parameters: {info[1]:,}" if isinstance(info, tuple) else "")

    for fmt in formats:
        print(f"\n  Exporting to {fmt.upper()}...")
        export_path = model.export(format=fmt, imgsz=640)
        if export_path:
            ep = Path(export_path)
            if ep.is_file():
                print(f"  Exported:  {ep} ({ep.stat().st_size / 1e6:.1f} MB)")
            elif ep.is_dir():
                total = sum(f.stat().st_size for f in ep.rglob("*") if f.is_file())
                print(f"  Exported:  {ep} ({total / 1e6:.1f} MB total)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export models to deployment formats")
    parser.add_argument(
        "--format",
        choices=EXPORT_FORMATS,
        help="Export only this format (default: all)",
    )
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        help="Export only this model (default: all)",
    )
    args = parser.parse_args()

    formats = [args.format] if args.format else EXPORT_FORMATS
    models = {args.model: MODELS[args.model]} if args.model else MODELS

    for name, pt_path in models.items():
        export_model(name, pt_path, formats)

    print("\n\nExport summary:")
    for name, pt_path in models.items():
        if not pt_path.exists():
            continue
        parent = pt_path.parent
        print(f"\n  {name}:")
        for fmt in formats:
            if fmt == "onnx":
                onnx_path = parent / f"{pt_path.stem}.onnx"
                if onnx_path.exists():
                    print(f"    ONNX: {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB)")
            elif fmt == "ncnn":
                ncnn_dir = parent / f"{pt_path.stem}_ncnn_model"
                if ncnn_dir.exists():
                    total = sum(f.stat().st_size for f in ncnn_dir.rglob("*") if f.is_file())
                    print(f"    NCNN: {ncnn_dir} ({total / 1e6:.1f} MB)")

    print("\nDone.")


if __name__ == "__main__":
    main()
