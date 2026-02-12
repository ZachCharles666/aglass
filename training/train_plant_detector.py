"""Train Model A: Plant species detector on PlantDoc dataset.

Uses YOLOv8n pretrained weights, fine-tuned on PlantDoc (~2600 images, 13 classes).
Saves best.pt to models/plant_detector_v1.pt.

Usage:
    python training/train_plant_detector.py
    python training/train_plant_detector.py --epochs 50 --batch 32
"""

import argparse
import shutil
from pathlib import Path

import yaml
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "training" / "configs" / "plant_detector.yaml"
DATASET_DIR = PROJECT_ROOT / "training" / "datasets" / "plantdoc"
OUTPUT_MODEL = PROJECT_ROOT / "models" / "plant_detector_v1.pt"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def find_data_yaml() -> Path:
    """Find the data.yaml file in the dataset directory."""
    candidates = [
        DATASET_DIR / "data.yaml",
        DATASET_DIR / "dataset.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Search recursively
    found = list(DATASET_DIR.rglob("data.yaml"))
    if found:
        return found[0]
    raise FileNotFoundError(
        f"No data.yaml found in {DATASET_DIR}. Run download_datasets.py first."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train plant species detector")
    parser.add_argument("--epochs", type=int, help="Override epoch count")
    parser.add_argument("--batch", type=int, help="Override batch size")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    cfg = load_config()
    data_yaml = find_data_yaml()
    print(f"Dataset config: {data_yaml}")

    # CLI overrides
    if args.epochs:
        cfg["epochs"] = args.epochs
    if args.batch:
        cfg["batch"] = args.batch

    model = YOLO(cfg["model"])

    if args.resume:
        last_pt = PROJECT_ROOT / cfg["project"] / cfg["name"] / "weights" / "last.pt"
        if last_pt.exists():
            model = YOLO(str(last_pt))
            print(f"Resuming from {last_pt}")

    results = model.train(
        data=str(data_yaml),
        imgsz=cfg["imgsz"],
        epochs=cfg["epochs"],
        batch=cfg["batch"],
        patience=cfg["patience"],
        lr0=cfg["lr0"],
        lrf=cfg["lrf"],
        momentum=cfg["momentum"],
        weight_decay=cfg["weight_decay"],
        warmup_epochs=cfg["warmup_epochs"],
        warmup_momentum=cfg["warmup_momentum"],
        hsv_h=cfg["hsv_h"],
        hsv_s=cfg["hsv_s"],
        hsv_v=cfg["hsv_v"],
        degrees=cfg["degrees"],
        translate=cfg["translate"],
        scale=cfg["scale"],
        fliplr=cfg["fliplr"],
        mosaic=cfg["mosaic"],
        project=cfg["project"],
        name=cfg["name"],
        save=cfg["save"],
        save_period=cfg["save_period"],
    )

    # Copy best.pt to models/
    best_pt = Path(results.save_dir) / "weights" / "best.pt"
    if best_pt.exists():
        OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_pt, OUTPUT_MODEL)
        print(f"\nBest model saved to {OUTPUT_MODEL}")
        print(f"  Size: {OUTPUT_MODEL.stat().st_size / 1e6:.1f} MB")
    else:
        print(f"WARNING: best.pt not found at {best_pt}")

    print("\nTraining complete. Key metrics:")
    print(f"  mAP@50:    {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"  mAP@50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A')}")


if __name__ == "__main__":
    main()
