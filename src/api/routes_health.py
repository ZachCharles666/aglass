"""
健康检查端点
GET /health 返回系统状态
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from ..utils.sysinfo import get_system_info
from ..utils.time_id import get_iso_timestamp
from ..store.repo import get_profile_repo
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


class CpuInfo(BaseModel):
    usage_percent: float
    count: int


class MemoryInfo(BaseModel):
    total_mb: float
    used_mb: float
    available_mb: float
    percent: float


class TemperatureInfo(BaseModel):
    cpu_celsius: Optional[float]


class DiskInfo(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


class PlatformInfo(BaseModel):
    system: str
    release: str
    machine: str
    python_version: str


class SystemInfo(BaseModel):
    cpu: CpuInfo
    memory: MemoryInfo
    temperature: TemperatureInfo
    disk: DiskInfo
    platform: PlatformInfo


class CameraStatus(BaseModel):
    cam_a: str = "not_initialized"
    cam_b: str = "not_initialized"


class CurrentProfileInfo(BaseModel):
    profile_id: Optional[str] = None
    operator_id: Optional[str] = None
    af_mode: Optional[str] = None
    lens_position: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    system: SystemInfo
    cameras: CameraStatus
    profile_loaded: bool
    current_profile: Optional[CurrentProfileInfo] = None
    queue_sizes: dict


_start_time = datetime.now(timezone.utc)


def get_uptime() -> float:
    """获取服务运行时间（秒）"""
    delta = datetime.now(timezone.utc) - _start_time
    return round(delta.total_seconds(), 2)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    健康检查端点

    返回系统状态，包括：
    - CPU/内存/磁盘使用率
    - CPU 温度
    - 相机状态
    - 当前 Profile 状态
    - 队列状态
    """
    sys_info = get_system_info()

    # 获取当前 Profile
    profile_loaded = False
    current_profile_info = None

    try:
        repo = get_profile_repo()
        current_profile = repo.get_current_profile()

        if current_profile:
            profile_loaded = True
            current_profile_info = CurrentProfileInfo(
                profile_id=current_profile.profile_id,
                operator_id=current_profile.operator_id,
                af_mode=current_profile.cam_a_config.af_mode,
                lens_position=current_profile.cam_a_config.lens_position
            )
    except Exception as e:
        logger.warning(f"获取当前 Profile 失败: {e}")

    # 获取相机状态
    cam_a_status = "not_initialized"
    cam_b_status = "not_initialized"

    try:
        from .routes_camera import get_controller
        controller = get_controller()
        if controller.is_initialized:
            cam_a_status = "ready"
    except Exception:
        pass

    # 获取采集状态
    capture_queue_size = 0
    try:
        from ..pipeline.capture_loop import get_capture_loop
        capture_loop = get_capture_loop()
        if capture_loop.is_running:
            cam_a_status = "capturing"
        capture_queue_size = capture_loop.inference_queue.qsize()
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        timestamp=get_iso_timestamp(),
        version="0.1.0",
        uptime_seconds=get_uptime(),
        system=SystemInfo(
            cpu=CpuInfo(**sys_info["cpu"]),
            memory=MemoryInfo(**sys_info["memory"]),
            temperature=TemperatureInfo(**sys_info["temperature"]),
            disk=DiskInfo(**sys_info["disk"]),
            platform=PlatformInfo(**sys_info["platform"])
        ),
        cameras=CameraStatus(
            cam_a=cam_a_status,
            cam_b=cam_b_status
        ),
        profile_loaded=profile_loaded,
        current_profile=current_profile_info,
        queue_sizes={
            "capture_queue": capture_queue_size,
            "burst_queue": 0,
            "upload_queue": 0
        }
    )
