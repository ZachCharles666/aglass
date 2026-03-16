"""
device.yaml 配置校验
用 Pydantic BaseModel 定义完整结构，启动时校验配置格式
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class CamAConfig(BaseModel):
    """Cam-A (IMX708) 配置"""
    identifier: str = "imx708"
    resolution: List[int] = [1920, 1080]
    af_mode: str = "auto"
    af_range: str = "macro"
    af_speed: str = "fast"


class CamBConfig(BaseModel):
    """Cam-B (IMX477) 配置"""
    identifier: str = "imx477"
    resolution: List[int] = [4056, 3040]
    fixed_focus_distance_cm: int = 45
    burst_count: int = 5
    burst_interval_ms: int = 150


class CameraSection(BaseModel):
    """camera 配置段"""
    cam_a: CamAConfig = Field(default_factory=CamAConfig)
    cam_b: CamBConfig = Field(default_factory=CamBConfig)


class CaptureConfig(BaseModel):
    """capture 配置段"""
    interval_sec: float = 1.5
    storage_path: str = "data/images"


class DistanceBucketsConfig(BaseModel):
    """distance_buckets 配置段"""
    near: List[int] = [40, 52]
    mid: List[int] = [52, 85]
    far: List[int] = [85, 300]


class LedConfig(BaseModel):
    """led 配置段"""
    gpio_pin: int = 17
    warmup_ms: int = 100


class DetectorConfig(BaseModel):
    """单个检测器配置"""
    model_config = {"protected_namespaces": ()}

    model_path: str
    conf_threshold: float = 0.3
    imgsz: int = 640
    camera: str = "cam_a"
    trigger_burst: bool = False


class InferenceConfig(BaseModel):
    """inference 配置段"""
    plant_detector: Optional[DetectorConfig] = None
    flower_detector: Optional[DetectorConfig] = None


class CloudConfig(BaseModel):
    """cloud 配置段"""
    api_base: str = "http://localhost:8080"
    api_key: str = ""
    upload_interval_sec: int = 30


class StorageConfig(BaseModel):
    """storage 配置段"""
    db_path: str = "data/db.sqlite"
    max_storage_gb: int = 50
    auto_cleanup: bool = False


class LoggingConfig(BaseModel):
    """logging 配置段"""
    level: str = "INFO"
    file_path: str = "data/logs/app.log"
    format: str = "json"


class DeviceConfig(BaseModel):
    """device.yaml 完整配置"""
    camera: CameraSection = Field(default_factory=CameraSection)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    distance_buckets: DistanceBucketsConfig = Field(default_factory=DistanceBucketsConfig)
    led: LedConfig = Field(default_factory=LedConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
