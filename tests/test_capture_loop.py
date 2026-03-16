"""
test_capture_loop.py — CaptureLoop 采集 + 入队 (8 tests)
"""
import time
import queue

from src.pipeline.capture_loop import CaptureLoop, get_capture_loop, set_capture_loop


class TestCaptureLoopInit:
    def test_default_state(self, capture_loop):
        assert capture_loop.is_running is False
        assert capture_loop.total_count == 0
        assert capture_loop.last_capture_time is None

    def test_status_dict(self, capture_loop):
        s = capture_loop.status
        assert s["is_running"] is False
        assert s["total_count"] == 0
        assert "interval_sec" in s
        assert "queue_size" in s


class TestCaptureLoopStartStop:
    def test_start(self, capture_loop):
        assert capture_loop.start() is True
        assert capture_loop.is_running is True
        capture_loop.stop()

    def test_double_start_returns_false(self, capture_loop):
        capture_loop.start()
        assert capture_loop.start() is False
        capture_loop.stop()

    def test_stop(self, capture_loop):
        capture_loop.start()
        assert capture_loop.stop() is True
        assert capture_loop.is_running is False

    def test_stop_when_not_running(self, capture_loop):
        assert capture_loop.stop() is False


class TestCaptureLoopCapture:
    def test_captures_images(self, capture_loop):
        capture_loop.start()
        time.sleep(0.3)  # 足够跑几轮 (interval=0.05)
        capture_loop.stop()
        assert capture_loop.total_count >= 1
        assert capture_loop.last_capture_time is not None

    def test_enqueues_to_inference_queue(self, capture_loop, inference_queue):
        capture_loop.start()
        time.sleep(0.3)
        capture_loop.stop()
        assert inference_queue.qsize() >= 1
        item = inference_queue.get_nowait()
        file_path, metadata = item
        assert "image_id" in metadata
        assert "cam_a" in metadata["camera_id"]


class TestCaptureLoopSingleton:
    def test_get_and_set(self, capture_loop):
        set_capture_loop(capture_loop)
        assert get_capture_loop() is capture_loop
