"""
test_burst_coordinator.py — BurstCoordinator 回调 + 防重叠 (8 tests)
"""
import time
import threading

from src.pipeline.burst_coordinator import (
    BurstCoordinator,
    get_burst_coordinator,
    set_burst_coordinator,
)
from src.inference.models import Detection, DetectionResult


def _flower_result(file_path="/tmp/trigger.jpg"):
    return DetectionResult(
        file_path=file_path,
        detections=[
            Detection(class_name="flower", confidence=0.9, bbox=(0, 0, 100, 100), class_id=0)
        ],
        trigger_burst=True,
    )


class TestBurstCoordinatorInit:
    def test_default_state(self, burst_coordinator):
        assert burst_coordinator.is_bursting is False
        assert burst_coordinator.status["total_bursts"] == 0
        assert burst_coordinator.status["total_images"] == 0

    def test_status_keys(self, burst_coordinator):
        s = burst_coordinator.status
        expected_keys = {
            "is_bursting", "total_bursts", "total_images",
            "last_burst_time", "errors", "cam_b_initialized", "cam_b_started",
        }
        assert expected_keys == set(s.keys())


class TestBurstCoordinatorExecution:
    def test_on_flower_detected_triggers_burst(self, burst_coordinator):
        result = _flower_result()
        burst_coordinator.on_flower_detected(result)
        # 等待 burst 线程完成
        time.sleep(0.5)
        assert burst_coordinator.status["total_bursts"] == 1
        assert burst_coordinator.status["total_images"] == 3  # burst_count=3

    def test_saves_metadata(self, burst_coordinator, file_store):
        result = _flower_result()
        burst_coordinator.on_flower_detected(result)
        time.sleep(0.5)
        count = file_store.count_images()
        assert count == 3

    def test_burst_id_in_metadata(self, burst_coordinator, file_store):
        result = _flower_result()
        burst_coordinator.on_flower_detected(result)
        time.sleep(0.5)
        latest = file_store.get_latest_image()
        assert latest is not None
        assert latest["camera_id"] == "cam_b"

    def test_prevents_overlap(self, burst_coordinator):
        """两次快速调用，第二次应被跳过"""
        r1 = _flower_result("/tmp/t1.jpg")
        r2 = _flower_result("/tmp/t2.jpg")
        burst_coordinator.on_flower_detected(r1)
        burst_coordinator.on_flower_detected(r2)  # 应被跳过
        time.sleep(1.0)
        assert burst_coordinator.status["total_bursts"] == 1

    def test_can_burst_again_after_completion(self, burst_coordinator):
        r1 = _flower_result("/tmp/a.jpg")
        burst_coordinator.on_flower_detected(r1)
        time.sleep(0.5)
        assert burst_coordinator.is_bursting is False  # 已完成
        r2 = _flower_result("/tmp/b.jpg")
        burst_coordinator.on_flower_detected(r2)
        time.sleep(0.5)
        assert burst_coordinator.status["total_bursts"] == 2


class TestBurstCoordinatorSingleton:
    def test_get_and_set(self, burst_coordinator):
        set_burst_coordinator(burst_coordinator)
        assert get_burst_coordinator() is burst_coordinator
