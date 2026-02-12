#!/usr/bin/env python3
"""
采集数据导出脚本

功能：
- 统计指定时间范围内的采集数据
- 输出 summary.csv
- 可选生成抽样图片目录

使用方法：
    python scripts/export_summary.py --minutes 30
    python scripts/export_summary.py --minutes 60 --sample
"""
import argparse
import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.store.db import init_db
from src.store.file_store import get_file_store
from src.utils.logger import setup_logging, get_logger

# 设置日志
setup_logging(log_file="data/logs/export_summary.log", level="INFO")
logger = get_logger(__name__)


def export_summary(
    minutes_ago: int = 30,
    output_dir: str = "data/exports",
    create_sample: bool = False,
    sample_rate: int = 10
) -> dict:
    """
    导出采集数据摘要

    Args:
        minutes_ago: 往前查询的分钟数
        output_dir: 输出目录
        create_sample: 是否创建抽样图片目录
        sample_rate: 抽样率（每 N 张抽 1 张）

    Returns:
        dict: 统计结果
    """
    print(f"\n{'='*50}")
    print(f"  采集数据导出")
    print(f"  时间范围: 最近 {minutes_ago} 分钟")
    print(f"{'='*50}\n")

    # 初始化数据库
    init_db()

    # 获取文件存储
    file_store = get_file_store()

    # 查询图片
    images = file_store.query_images_since(minutes_ago=minutes_ago)

    if not images:
        print("没有找到任何采集记录")
        return {"total": 0}

    # 准备输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 统计数据
    total_count = len(images)
    qualities = [img["quality_score"] for img in images if img["quality_score"]]

    missing_files = []
    for img in images:
        if not Path(img["file_path"]).exists():
            missing_files.append(img["file_path"])

    avg_quality = sum(qualities) / len(qualities) if qualities else 0
    min_quality = min(qualities) if qualities else 0
    max_quality = max(qualities) if qualities else 0

    # 输出 summary.csv
    csv_path = output_path / f"summary_{timestamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image_id", "profile_id", "camera_id", "ts",
            "distance_bucket", "focus_state", "quality_score",
            "file_path", "file_exists"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for img in images:
            file_exists = Path(img["file_path"]).exists()
            writer.writerow({
                "image_id": img["image_id"],
                "profile_id": img["profile_id"],
                "camera_id": img["camera_id"],
                "ts": img["ts"],
                "distance_bucket": img["distance_bucket"],
                "focus_state": img["focus_state"],
                "quality_score": img["quality_score"],
                "file_path": img["file_path"],
                "file_exists": file_exists
            })

    print(f"CSV 已导出: {csv_path}")

    # 创建抽样图片目录
    sample_dir = None
    sampled_count = 0

    if create_sample:
        sample_dir = output_path / f"samples_{timestamp}"
        sample_dir.mkdir(parents=True, exist_ok=True)

        for i, img in enumerate(images):
            if i % sample_rate == 0:
                src_path = Path(img["file_path"])
                if src_path.exists():
                    dst_path = sample_dir / src_path.name
                    shutil.copy2(src_path, dst_path)
                    sampled_count += 1

        print(f"抽样图片目录: {sample_dir}")
        print(f"抽样数量: {sampled_count} 张（每 {sample_rate} 张抽 1 张）")

    # 输出统计报告
    report_path = output_path / f"report_{timestamp}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"采集数据统计报告\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n")
        f.write(f"查询范围: 最近 {minutes_ago} 分钟\n")
        f.write(f"\n{'='*40}\n\n")
        f.write(f"总图片数: {total_count}\n")
        f.write(f"平均清晰度: {avg_quality:.2f}\n")
        f.write(f"最低清晰度: {min_quality:.2f}\n")
        f.write(f"最高清晰度: {max_quality:.2f}\n")
        f.write(f"缺失文件数: {len(missing_files)}\n")

        if missing_files:
            f.write(f"\n缺失文件列表:\n")
            for path in missing_files[:20]:  # 最多列出 20 个
                f.write(f"  - {path}\n")
            if len(missing_files) > 20:
                f.write(f"  ... 还有 {len(missing_files) - 20} 个文件\n")

    print(f"统计报告: {report_path}")

    # 打印统计摘要
    print(f"\n{'='*50}")
    print(f"  统计摘要")
    print(f"{'='*50}")
    print(f"总图片数: {total_count}")
    print(f"平均清晰度: {avg_quality:.2f}")
    print(f"最低清晰度: {min_quality:.2f}")
    print(f"最高清晰度: {max_quality:.2f}")
    print(f"缺失文件数: {len(missing_files)}")
    print(f"{'='*50}\n")

    return {
        "total": total_count,
        "avg_quality": avg_quality,
        "min_quality": min_quality,
        "max_quality": max_quality,
        "missing_files": len(missing_files),
        "csv_path": str(csv_path),
        "report_path": str(report_path),
        "sample_dir": str(sample_dir) if sample_dir else None,
        "sampled_count": sampled_count
    }


def main():
    parser = argparse.ArgumentParser(description="采集数据导出")
    parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="往前查询的分钟数（默认 30）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/exports",
        help="输出目录"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="创建抽样图片目录"
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=10,
        help="抽样率（默认每 10 张抽 1 张）"
    )

    args = parser.parse_args()

    result = export_summary(
        minutes_ago=args.minutes,
        output_dir=args.output,
        create_sample=args.sample,
        sample_rate=args.sample_rate
    )

    # 返回退出码
    if result["total"] == 0:
        sys.exit(1)
    elif result["missing_files"] > 0:
        print(f"\n警告: 有 {result['missing_files']} 个文件缺失")
        sys.exit(2)
    else:
        print("\n导出完成!")
        sys.exit(0)


if __name__ == "__main__":
    main()
