#!/usr/bin/env python3
"""
对焦稳定性测试脚本

严格按照 SKILL 中的"对焦稳定性测试"模板实现

验收目标：
- one-shot 平均耗时 ≤1.5s
- 成功率 ≥95%
- lock 后清晰度波动 <5%

使用方法：
    # 在树莓派上运行真实测试
    python scripts/test_af_lock.py

    # 在开发机上运行模拟测试
    python scripts/test_af_lock.py --mock
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.camera.cam_a import create_cam_a, get_clarity_score
from src.utils.logger import setup_logging, get_logger

# 设置日志
setup_logging(log_file="data/logs/test_af_lock.log", level="INFO")
logger = get_logger(__name__)


def run_af_stability_test(
    use_mock: bool = False,
    rounds: int = 10,
    output_csv: str = "data/logs/af_test.csv"
) -> dict:
    """
    运行对焦稳定性测试

    Args:
        use_mock: 是否使用模拟相机
        rounds: 测试轮数
        output_csv: CSV 输出路径

    Returns:
        dict: 测试结果摘要
    """
    print(f"\n{'='*50}")
    print(f"  对焦稳定性测试")
    print(f"  模式: {'模拟' if use_mock else '真实相机'}")
    print(f"  轮数: {rounds}")
    print(f"{'='*50}\n")

    # 创建相机实例
    cam_a = create_cam_a(use_mock=use_mock)

    # 初始化并启动相机
    if not cam_a.initialize():
        print("❌ 相机初始化失败")
        return {"error": "相机初始化失败"}

    if not cam_a.start():
        print("❌ 相机启动失败")
        return {"error": "相机启动失败"}

    # 确保输出目录存在
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path("data/images/test_af").mkdir(parents=True, exist_ok=True)

    results = []

    try:
        for i in range(rounds):
            print(f"\n=== Round {i+1}/{rounds} ===")

            # 1. 触发对焦
            success, duration, lens_pos = cam_a.one_shot_af(timeout=3.0)

            # 2. 锁定焦距
            locked_pos = cam_a.lock_focus()

            # 3. 等待稳定（3 秒）
            time.sleep(3)

            # 4. 拍照并计算清晰度
            test_path = f"data/images/test_af/test_af_{i}.jpg"
            capture_success = cam_a.capture(test_path)

            if capture_success and Path(test_path).exists() and Path(test_path).stat().st_size > 0:
                clarity = get_clarity_score(test_path)
            else:
                # Mock 模式下生成随机清晰度值
                import random
                clarity = random.uniform(100, 200) if use_mock else 0.0

            # 记录结果
            result = {
                "round": i + 1,
                "success": success,
                "duration": round(duration, 3),
                "lens_position": lens_pos,
                "locked_position": locked_pos,
                "clarity": round(clarity, 2)
            }
            results.append(result)

            status = "✅" if success else "❌"
            print(f"{status} 成功: {success}, 耗时: {duration:.3f}s, "
                  f"焦距: {lens_pos}, 清晰度: {clarity:.1f}")

            # 解锁焦距，准备下一轮
            cam_a.unlock_focus()

    finally:
        # 关闭相机
        cam_a.close()

    # 输出 CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["round", "success", "duration", "lens_position", "locked_position", "clarity"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ 测试数据已保存到: {output_csv}")

    # 计算验收指标
    success_count = sum(1 for r in results if r["success"])
    success_rate = success_count / len(results) if results else 0

    successful_durations = [r["duration"] for r in results if r["success"]]
    avg_duration = sum(successful_durations) / len(successful_durations) if successful_durations else 0

    clarities = [r["clarity"] for r in results if r["clarity"] > 0]
    if len(clarities) >= 2:
        avg_clarity = sum(clarities) / len(clarities)
        max_clarity = max(clarities)
        min_clarity = min(clarities)
        clarity_variation = (max_clarity - min_clarity) / avg_clarity * 100 if avg_clarity > 0 else 0
    else:
        avg_clarity = clarities[0] if clarities else 0
        clarity_variation = 0

    # 打印验收结果
    print(f"\n{'='*50}")
    print(f"  验收结果")
    print(f"{'='*50}")
    print(f"成功率: {success_rate*100:.1f}% (目标 ≥95%)")
    print(f"平均耗时: {avg_duration:.3f}s (目标 ≤1.5s)")
    print(f"清晰度波动: {clarity_variation:.1f}% (目标 <5%)")
    print(f"{'='*50}")

    # 验收判断
    passed = True
    if success_rate < 0.95:
        print(f"❌ 成功率 {success_rate:.2%} < 95%")
        passed = False
    else:
        print(f"✅ 成功率验收通过")

    if avg_duration > 1.5:
        print(f"❌ 平均耗时 {avg_duration:.3f}s > 1.5s")
        passed = False
    else:
        print(f"✅ 平均耗时验收通过")

    if clarity_variation > 5:
        print(f"❌ 清晰度波动 {clarity_variation:.1f}% > 5%")
        passed = False
    else:
        print(f"✅ 清晰度波动验收通过")

    if passed:
        print(f"\n🎉 全部验收通过！")
    else:
        print(f"\n⚠️ 部分指标未达标")

    return {
        "rounds": rounds,
        "success_rate": success_rate,
        "avg_duration": avg_duration,
        "avg_clarity": avg_clarity,
        "clarity_variation": clarity_variation,
        "passed": passed,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="对焦稳定性测试")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用模拟相机（开发机测试）"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="测试轮数（默认 10）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/logs/af_test.csv",
        help="CSV 输出路径"
    )

    args = parser.parse_args()

    summary = run_af_stability_test(
        use_mock=args.mock,
        rounds=args.rounds,
        output_csv=args.output
    )

    # 返回退出码
    if summary.get("error"):
        sys.exit(1)
    elif not summary.get("passed", False):
        sys.exit(2)  # 测试未通过
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
