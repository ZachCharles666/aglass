"""
device.yaml Pydantic 配置校验测试
"""
import pytest
from pydantic import ValidationError

from src.config import (
    DeviceConfig,
    CamAConfig,
    CamBConfig,
    CameraSection,
    CaptureConfig,
    DetectorConfig,
    InferenceConfig,
    StorageConfig,
    LoggingConfig,
)


class TestDeviceConfigValid:
    """合法配置解析"""

    def test_full_yaml_dict(self):
        """完整 device.yaml 内容 → 解析成功"""
        raw = {
            "camera": {
                "cam_a": {
                    "identifier": "imx708",
                    "resolution": [1920, 1080],
                    "af_mode": "auto",
                    "af_range": "macro",
                    "af_speed": "fast",
                },
                "cam_b": {
                    "identifier": "imx477",
                    "resolution": [4056, 3040],
                    "fixed_focus_distance_cm": 45,
                    "burst_count": 5,
                    "burst_interval_ms": 150,
                },
            },
            "capture": {"interval_sec": 1.5, "storage_path": "data/images"},
            "distance_buckets": {
                "near": [40, 52],
                "mid": [52, 85],
                "far": [85, 300],
            },
            "led": {"gpio_pin": 17, "warmup_ms": 100},
            "inference": {
                "plant_detector": {
                    "model_path": "models/plant_detector_v1.pt",
                    "conf_threshold": 0.3,
                    "imgsz": 640,
                    "camera": "cam_a",
                },
                "flower_detector": {
                    "model_path": "models/flower_detector_v1.pt",
                    "conf_threshold": 0.4,
                    "imgsz": 640,
                    "camera": "cam_a",
                    "trigger_burst": True,
                },
            },
            "cloud": {
                "api_base": "http://localhost:8080",
                "api_key": "test_key_12345",
                "upload_interval_sec": 30,
            },
            "storage": {
                "db_path": "data/db.sqlite",
                "max_storage_gb": 50,
                "auto_cleanup": False,
            },
            "logging": {
                "level": "INFO",
                "file_path": "data/logs/app.log",
                "format": "json",
            },
        }
        cfg = DeviceConfig(**raw)

        assert cfg.camera.cam_a.identifier == "imx708"
        assert cfg.camera.cam_b.burst_count == 5
        assert cfg.capture.interval_sec == 1.5
        assert cfg.inference.flower_detector.trigger_burst is True
        assert cfg.storage.db_path == "data/db.sqlite"
        assert cfg.logging.level == "INFO"

    def test_empty_dict_uses_defaults(self):
        """空 dict → 所有默认值"""
        cfg = DeviceConfig()

        assert cfg.camera.cam_a.identifier == "imx708"
        assert cfg.camera.cam_b.burst_count == 5
        assert cfg.capture.interval_sec == 1.5
        assert cfg.storage.db_path == "data/db.sqlite"
        assert cfg.logging.level == "INFO"

    def test_partial_config(self):
        """部分字段 → 其余用默认值"""
        cfg = DeviceConfig(
            storage={"db_path": "custom/path.db"},
            logging={"level": "DEBUG"},
        )
        assert cfg.storage.db_path == "custom/path.db"
        assert cfg.logging.level == "DEBUG"
        # 未指定的仍为默认
        assert cfg.camera.cam_a.identifier == "imx708"


class TestDeviceConfigInvalid:
    """非法配置校验"""

    def test_burst_count_wrong_type(self):
        """burst_count 传字符串 → ValidationError"""
        with pytest.raises(ValidationError):
            DeviceConfig(
                camera={"cam_b": {"burst_count": "abc"}}
            )

    def test_detector_missing_model_path(self):
        """DetectorConfig 缺少必填 model_path → ValidationError"""
        with pytest.raises(ValidationError):
            DetectorConfig(conf_threshold=0.5)

    def test_interval_sec_wrong_type(self):
        """interval_sec 传非数字 → ValidationError"""
        with pytest.raises(ValidationError):
            CaptureConfig(interval_sec="fast")

    def test_resolution_wrong_type(self):
        """resolution 传字符串 → ValidationError"""
        with pytest.raises(ValidationError):
            CamAConfig(resolution="1920x1080")


class TestDeviceConfigDefaults:
    """默认值正确填充"""

    def test_cam_a_defaults(self):
        cfg = CamAConfig()
        assert cfg.identifier == "imx708"
        assert cfg.resolution == [1920, 1080]
        assert cfg.af_mode == "auto"
        assert cfg.af_range == "macro"
        assert cfg.af_speed == "fast"

    def test_cam_b_defaults(self):
        cfg = CamBConfig()
        assert cfg.identifier == "imx477"
        assert cfg.resolution == [4056, 3040]
        assert cfg.fixed_focus_distance_cm == 45
        assert cfg.burst_count == 5
        assert cfg.burst_interval_ms == 150

    def test_storage_defaults(self):
        cfg = StorageConfig()
        assert cfg.db_path == "data/db.sqlite"
        assert cfg.max_storage_gb == 50
        assert cfg.auto_cleanup is False

    def test_logging_defaults(self):
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.file_path == "data/logs/app.log"
        assert cfg.format == "json"
