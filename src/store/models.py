"""
数据模型定义
严格按照 SKILL 中的 Profile 数据模型
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field


class CameraConfig(BaseModel):
    """相机配置"""
    af_mode: str = "auto"  # "auto" | "locked"
    lens_position: Optional[float] = None
    focus_distance_cm: Optional[int] = None


class DistancePolicy(BaseModel):
    """距离档位策略"""
    near: List[int] = [40, 52]   # cm - 唯一可标记"资产级"的档位
    mid: List[int] = [52, 85]    # cm
    far: List[int] = [85, 300]   # cm


class FocusProfile(BaseModel):
    """Mission Focus Profile"""
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operator_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cam_a_config: CameraConfig
    distance_policy: DistancePolicy = Field(default_factory=DistancePolicy)
    notes: Optional[str] = None
    is_current: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProfileCreateRequest(BaseModel):
    """创建 Profile 的请求"""
    operator_id: str
    notes: Optional[str] = None
    focus_distance_cm: int = 45  # 默认 45cm


class ProfileResponse(BaseModel):
    """Profile 响应"""
    profile_id: str
    operator_id: str
    created_at: str
    cam_a_config: CameraConfig
    distance_policy: DistancePolicy
    notes: Optional[str]
    is_current: bool


class ProfileListResponse(BaseModel):
    """Profile 列表响应"""
    profiles: List[ProfileResponse]
    total: int
    current_profile_id: Optional[str]
