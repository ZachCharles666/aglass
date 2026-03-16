"""
推理数据模型
"""
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class Detection(BaseModel):
    """单个检测框"""
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    class_id: int


class DetectionResult(BaseModel):
    """一张图的推理结果"""
    model_config = {"protected_namespaces": ()}

    file_path: str
    detections: List[Detection] = Field(default_factory=list)
    inference_time_ms: float = 0.0
    model_name: str = ""
    trigger_burst: bool = False
