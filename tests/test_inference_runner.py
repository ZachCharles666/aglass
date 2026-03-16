"""
test_inference_runner.py — InferenceRunner 生命周期 + mock 推理 (10 tests)
"""
import time
import queue

from src.inference.runner import InferenceRunner, get_inference_runner, set_inference_runner
from src.inference.models import Detection, DetectionResult


class TestInferenceRunnerInit:
    def test_default_state(self, inference_runner):
        assert inference_runner.is_running is False
        assert inference_runner.use_mock is True

    def test_status_dict(self, inference_runner):
        s = inference_runner.status
        assert s["is_running"] is False
        assert s["total_processed"] == 0
        assert s["use_mock"] is True

    def test_latest_result_none(self, inference_runner):
        assert inference_runner.latest_result is None


class TestInferenceRunnerStartStop:
    def test_start(self, inference_runner):
        assert inference_runner.start() is True
        assert inference_runner.is_running is True
        inference_runner.stop()

    def test_double_start_returns_false(self, inference_runner):
        inference_runner.start()
        assert inference_runner.start() is False
        inference_runner.stop()

    def test_stop(self, inference_runner):
        inference_runner.start()
        assert inference_runner.stop() is True
        assert inference_runner.is_running is False

    def test_stop_when_not_running(self, inference_runner):
        assert inference_runner.stop() is False


class TestInferenceRunnerProcessing:
    def test_processes_queue_item(self, inference_runner, inference_queue, tmp_path):
        # 放入一个 item
        fp = str(tmp_path / "infer.jpg")
        open(fp, "w").close()
        inference_queue.put((fp, {"image_id": "test_001"}))

        inference_runner.start()
        time.sleep(0.5)  # 等待处理
        inference_runner.stop()

        assert inference_runner.status["total_processed"] >= 1
        assert inference_runner.latest_result is not None
        assert inference_runner.latest_result.file_path == fp

    def test_mock_inference_result_type(self, inference_runner, inference_queue, tmp_path):
        fp = str(tmp_path / "mock.jpg")
        open(fp, "w").close()
        inference_queue.put((fp, {}))

        inference_runner.start()
        time.sleep(0.5)
        inference_runner.stop()

        result = inference_runner.latest_result
        assert isinstance(result, DetectionResult)
        assert result.model_name == "mock"


class TestInferenceRunnerSingleton:
    def test_get_and_set(self, inference_runner):
        set_inference_runner(inference_runner)
        assert get_inference_runner() is inference_runner
