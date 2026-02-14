"""Analyze and filter YOLO dataset by class sample count.

Removes underrepresented classes (< min_samples) from labels and
generates a new data.yaml with filtered class list.

Usage:
    # Analyze class distribution (dry run)
    python training/filter_dataset.py --dataset training/datasets/plantdoc --analyze

    # Filter out classes with < 20 samples, write to filtered/
    python training/filter_dataset.py --dataset training/datasets/plantdoc --min-samples 20
"""

import argparse
import shutil
from collections import Counter
from pathlib import Path

import yaml


def load_data_yaml(dataset_dir: Path) -> tuple[Path, dict]:
    """Find and load data.yaml."""
    for name in ("data.yaml", "dataset.yaml"):
        p = dataset_dir / name
        if p.exists():
            with open(p) as f:
                return p, yaml.safe_load(f)
    found = list(dataset_dir.rglob("data.yaml"))
    if found:
        with open(found[0]) as f:
            return found[0], yaml.safe_load(f)
    raise FileNotFoundError(f"No data.yaml in {dataset_dir}")


def count_class_samples(dataset_dir: Path) -> Counter:
    """Count total label instances per class across train+valid."""
    counts = Counter()
    for split in ("train", "valid", "test"):
        labels_dir = dataset_dir / split / "labels"
        if not labels_dir.exists():
            continue
        for txt in labels_dir.glob("*.txt"):
            for line in txt.read_text().strip().splitlines():
                if line.strip():
                    class_id = int(line.strip().split()[0])
                    counts[class_id] += 1
    return counts


def analyze(dataset_dir: Path, class_names: list) -> None:
    """Print class distribution analysis."""
    counts = count_class_samples(dataset_dir)

    print(f"\nClass distribution ({dataset_dir.name}):")
    print(f"{'ID':>4}  {'Count':>6}  Class Name")
    print("-" * 50)
    for cid in range(len(class_names)):
        c = counts.get(cid, 0)
        marker = " *** LOW" if c < 20 else ""
        print(f"{cid:>4}  {c:>6}  {class_names[cid]}{marker}")

    print(f"\nTotal classes: {len(class_names)}")
    print(f"Total instances: {sum(counts.values())}")
    low = [class_names[cid] for cid in range(len(class_names)) if counts.get(cid, 0) < 20]
    if low:
        print(f"Low sample classes (<20): {', '.join(low)}")


def filter_dataset(dataset_dir: Path, data_yaml_path: Path, data_cfg: dict,
                   min_samples: int) -> Path:
    """Create filtered copy of dataset, removing underrepresented classes."""
    counts = count_class_samples(dataset_dir)
    class_names = data_cfg.get("names", [])

    # Determine which classes to keep
    keep_ids = {cid for cid in range(len(class_names)) if counts.get(cid, 0) >= min_samples}
    drop_names = [class_names[cid] for cid in range(len(class_names)) if cid not in keep_ids]

    if not drop_names:
        print("All classes meet the minimum sample threshold. No filtering needed.")
        return dataset_dir

    print(f"\nDropping {len(drop_names)} classes (< {min_samples} samples): {', '.join(drop_names)}")
    print(f"Keeping {len(keep_ids)} classes")

    # Build new class mapping: old_id -> new_id
    sorted_keep = sorted(keep_ids)
    id_map = {old: new for new, old in enumerate(sorted_keep)}
    new_names = [class_names[old] for old in sorted_keep]

    # Output directory
    out_dir = dataset_dir.parent / f"{dataset_dir.name}_filtered"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # Copy and filter
    for split in ("train", "valid", "test"):
        src_images = dataset_dir / split / "images"
        src_labels = dataset_dir / split / "labels"
        if not src_images.exists():
            continue

        dst_images = out_dir / split / "images"
        dst_labels = out_dir / split / "labels"
        dst_images.mkdir(parents=True, exist_ok=True)
        dst_labels.mkdir(parents=True, exist_ok=True)

        for label_file in src_labels.glob("*.txt"):
            # Filter lines
            new_lines = []
            for line in label_file.read_text().strip().splitlines():
                parts = line.strip().split()
                if not parts:
                    continue
                old_id = int(parts[0])
                if old_id in id_map:
                    parts[0] = str(id_map[old_id])
                    new_lines.append(" ".join(parts))

            if not new_lines:
                continue  # Skip images with no remaining labels

            # Write filtered label
            (dst_labels / label_file.name).write_text("\n".join(new_lines) + "\n")

            # Copy corresponding image
            stem = label_file.stem
            for ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                img = src_images / (stem + ext)
                if img.exists():
                    shutil.copy2(img, dst_images / img.name)
                    break

    # Write new data.yaml
    new_cfg = {
        "train": str(out_dir / "train" / "images"),
        "val": str(out_dir / "valid" / "images"),
        "nc": len(new_names),
        "names": new_names,
    }
    test_dir = out_dir / "test" / "images"
    if test_dir.exists():
        new_cfg["test"] = str(test_dir)

    new_yaml = out_dir / "data.yaml"
    with open(new_yaml, "w") as f:
        yaml.dump(new_cfg, f, default_flow_style=False)

    # Summary
    for split in ("train", "valid"):
        imgs = out_dir / split / "images"
        if imgs.exists():
            n = len(list(imgs.glob("*")))
            print(f"  {split}: {n} images")

    print(f"\nFiltered dataset: {out_dir}")
    print(f"New data.yaml: {new_yaml}")
    print(f"Classes ({len(new_names)}): {', '.join(new_names)}")
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Analyze/filter YOLO dataset")
    parser.add_argument("--dataset", required=True, help="Path to dataset directory")
    parser.add_argument("--analyze", action="store_true", help="Only analyze, don't filter")
    parser.add_argument("--min-samples", type=int, default=20,
                        help="Minimum samples per class to keep (default: 20)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset).resolve()
    yaml_path, data_cfg = load_data_yaml(dataset_dir)
    class_names = data_cfg.get("names", [])

    if args.analyze:
        analyze(dataset_dir, class_names)
        return

    analyze(dataset_dir, class_names)
    filter_dataset(dataset_dir, yaml_path, data_cfg, args.min_samples)


if __name__ == "__main__":
    main()
