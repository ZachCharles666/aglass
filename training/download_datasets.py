"""Download datasets from Roboflow for YOLO training.

Downloads:
  - PlantDoc dataset (Model A: plant species detection, ~2600 images, 13 classes)
  - Flower detection dataset (Model B: flower/bud binary detection)

Usage:
    # --- Option 1: Direct download (good network to Roboflow) ---
    export ROBOFLOW_API_KEY="your_key"
    python training/download_datasets.py

    # --- Option 2: Local Mac download + pack, then unpack on cloud ---
    # On Mac:
    export ROBOFLOW_API_KEY="your_key"
    python training/download_datasets.py --pack
    # -> produces training/datasets.tar.gz, upload to PAI-DSW
    #
    # On PAI-DSW:
    python training/download_datasets.py --unpack
"""

import argparse
import os
import sys
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "training" / "datasets"
ARCHIVE_PATH = PROJECT_ROOT / "training" / "datasets.tar.gz"


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
    """Download flower detection dataset in YOLOv8 format.

    Tries multiple public Roboflow Universe datasets as fallback.
    """
    from roboflow import Roboflow

    dest = DATASETS_DIR / "flower"
    if dest.exists() and any(dest.iterdir()):
        print(f"Flower dataset already exists at {dest}, skipping download.")
        return dest

    # Public flower detection datasets on Roboflow Universe (fallback order)
    candidates = [
        ("saidumar", "flower-detection-using-yolov5-dpzjv", 1),  # ~360 images
        ("flower-42dyl", "flower-detection-hiutj", 3),            # ~182 images
        ("yolo-581ja", "flower-xscv4", 1),                        # ~143 images
    ]

    rf = Roboflow(api_key=api_key)
    for workspace, project_slug, ver in candidates:
        try:
            print(f"Trying flower dataset: {workspace}/{project_slug} v{ver} ...")
            project = rf.workspace(workspace).project(project_slug)
            version = project.version(ver)
            dataset = version.download("yolov8", location=str(dest))
            print(f"Flower dataset downloaded to {dataset.location}")
            return Path(dataset.location)
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    print("ERROR: All flower dataset sources failed.")
    print("  You can manually download a flower detection dataset from:")
    print("  https://universe.roboflow.com/search?q=flower+detection")
    print("  and place it in:", dest)
    sys.exit(1)


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


def pack_datasets() -> None:
    """Pack datasets/ into a tar.gz for upload to cloud."""
    if not DATASETS_DIR.exists():
        print(f"Error: {DATASETS_DIR} does not exist. Download datasets first.")
        sys.exit(1)

    print(f"Packing datasets into {ARCHIVE_PATH} ...")
    with tarfile.open(ARCHIVE_PATH, "w:gz") as tar:
        tar.add(DATASETS_DIR, arcname="datasets")
    size_mb = ARCHIVE_PATH.stat().st_size / 1e6
    print(f"Done: {ARCHIVE_PATH} ({size_mb:.1f} MB)")
    print(f"\nUpload to PAI-DSW:")
    print(f"  scp {ARCHIVE_PATH} root@<dsw-ip>:/mnt/workspace/aglass/training/")
    print(f"  Or use DSW file upload panel.")
    print(f"Then run:  python training/download_datasets.py --unpack")


def unpack_datasets() -> None:
    """Unpack datasets.tar.gz on cloud."""
    if not ARCHIVE_PATH.exists():
        print(f"Error: {ARCHIVE_PATH} not found.")
        print(f"Upload datasets.tar.gz to {ARCHIVE_PATH} first.")
        sys.exit(1)

    print(f"Unpacking {ARCHIVE_PATH} ...")
    with tarfile.open(ARCHIVE_PATH, "r:gz") as tar:
        tar.extractall(ARCHIVE_PATH.parent)
    print("Done.")

    print("\nDataset verification:")
    verify_dataset(DATASETS_DIR / "plantdoc", "plantdoc")
    verify_dataset(DATASETS_DIR / "flower", "flower")
    print("\nDatasets ready for training.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download / pack / unpack datasets")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pack", action="store_true",
                       help="Pack downloaded datasets into tar.gz for cloud upload")
    group.add_argument("--unpack", action="store_true",
                       help="Unpack datasets.tar.gz on cloud")
    args = parser.parse_args()

    if args.pack:
        pack_datasets()
        return

    if args.unpack:
        unpack_datasets()
        return

    # Default: download from Roboflow
    api_key = get_api_key()
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    download_plantdoc(api_key)
    download_flower(api_key)

    print("\nDataset verification:")
    verify_dataset(DATASETS_DIR / "plantdoc", "plantdoc")
    verify_dataset(DATASETS_DIR / "flower", "flower")
    print("\nDone. Datasets ready for training.")


if __name__ == "__main__":
    main()
