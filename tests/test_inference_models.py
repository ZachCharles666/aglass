"""
test_inference_models.py — Detection/DetectionResult 模型 (6 tests)
"""
from src.inference.models import Detection, DetectionResult


class TestDetection:
    def test_creation(self):
        d = Detection(
            class_name="flower",
            confidence=0.95,
            bbox=(10.0, 20.0, 100.0, 200.0),
            class_id=0,
        )
        assert d.class_name == "flower"
        assert d.confidence == 0.95
        assert len(d.bbox) == 4

    def test_bbox_tuple(self):
        d = Detection(class_name="leaf", confidence=0.5, bbox=(1, 2, 3, 4), class_id=1)
        assert d.bbox == (1, 2, 3, 4)


class TestDetectionResult:
    def test_defaults(self):
        r = DetectionResult(file_path="/tmp/test.jpg")
        assert r.detections == []
        assert r.inference_time_ms == 0.0
        assert r.model_name == ""
        assert r.trigger_burst is False

    def test_with_detections(self):
        det = Detection(class_name="rose", confidence=0.8, bbox=(0, 0, 50, 50), class_id=0)
        r = DetectionResult(
            file_path="/tmp/x.jpg",
            detections=[det],
            inference_time_ms=12.3,
            model_name="yolov8n",
            trigger_burst=True,
        )
        assert len(r.detections) == 1
        assert r.trigger_burst is True
        assert r.model_name == "yolov8n"

    def test_json_round_trip(self):
        det = Detection(class_name="a", confidence=0.1, bbox=(0, 0, 1, 1), class_id=2)
        r = DetectionResult(file_path="/f.jpg", detections=[det], trigger_burst=True)
        data = r.model_dump_json()
        r2 = DetectionResult.model_validate_json(data)
        assert r2.file_path == "/f.jpg"
        assert r2.trigger_burst is True
        assert r2.detections[0].class_name == "a"

    def test_empty_result(self):
        r = DetectionResult(file_path="x.jpg")
        assert len(r.detections) == 0
        assert r.trigger_burst is False
