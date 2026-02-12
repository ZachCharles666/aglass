"""Download datasets from Roboflow for YOLO training.

Downloads:
  - PlantDoc dataset (Model A: plant species detection, ~2600 images, 13 classes)
  - Flower detection dataset (Model B: flower/bud binary detection)

Usage:
    export ROBOFLOW_API_KEY="your_key"
    python training/download_datasets.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "training" / "datasets"


def get_api_key() -> str:
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        print("Error: ROBOFLOW_API_KEY environment variable not set.")
        print("  export ROBOFLOW_API_KEY='your_key_here'")
        print("  Get your key at https://app.roboflow.com/settings/api")
        sys.exit(1)
    return key


def download_plantdoc(api_key: str) -> Path:
    """Download PlantDoc dataset in YOLOv8 format."""
    from roboflow import Roboflow

    dest = DATASETS_DIR / "plantdoc"
    if dest.exists() and any(dest.iterdir()):
        print(f"PlantDoc dataset already exists at {dest}, skipping download.")
        return dest

    print("Downloading PlantDoc dataset...")
    rf = Roboflow(api_key=api_key)
    project = rf.workspace("joseph-nelson").project("plantdoc")
    version = project.version(1)
    dataset = version.download("yolov8", location=str(dest))
    print(f"PlantDoc downloaded to {dataset.location}")
    return Path(dataset.location)


def download_flower(api_key: str) -> Path:
    """Download flower detection dataset in YOLOv8 format."""
    from roboflow import Roboflow

    dest = DATASETS_DIR / "flower"
    if dest.exists() and any(dest.iterdir()):
        print(f"Flower dataset already exists at {dest}, skipping download.")
        return dest

    print("Downloading flower detection dataset...")
    rf = Roboflow(api_key=api_key)
    # Roboflow flower detection dataset (flower / bud classes)
    project = rf.workspace("flowers-kyocp").project("flower-detection-yhlmb")
    version = project.version(1)
    dataset = version.download("yolov8", location=str(dest))
    print(f"Flower dataset downloaded to {dataset.location}")
    return Path(dataset.location)


def verify_dataset(path: Path, name: str) -> None:
    """Verify YOLO dataset directory structure."""
    for split in ("train", "valid"):
        images_dir = path / split / "images"
        labels_dir = path / split / "labels"
        if not images_dir.exists():
            print(f"  WARNING: {name} missing {split}/images")
            continue
        n_images = len(list(images_dir.glob("*")))
        n_labels = len(list(labels_dir.glob("*.txt"))) if labels_dir.exists() else 0
        print(f"  {name}/{split}: {n_images} images, {n_labels} labels")


def main() -> None:
    api_key = get_api_key()
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    plantdoc_path = download_plantdoc(api_key)
    download_flower(api_key)

    print("\nDataset verification:")
    verify_dataset(DATASETS_DIR / "plantdoc", "plantdoc")
    verify_dataset(DATASETS_DIR / "flower", "flower")
    print("\nDone. Datasets ready for training.")


if __name__ == "__main__":
    main()
