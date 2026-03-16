"""
Cam-B (IMX477) API 端点
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from ..camera.cam_b import MockCamB
from ..pipeline.burst_coordinator import get_burst_coordinator
from ..store.file_store import get_file_store
from ..utils.logger import get_logger
from ..utils.time_id import generate_time_id

logger = get_logger(__name__)

router = APIRouter(prefix="/camera/cam-b", tags=["camera-b"])


# ============== Pydantic Models ==============

class CamBStatusResponse(BaseModel):
    initialized: bool
    started: bool
    camera_type: str
    resolution: List[int]
    burst_count: int
    burst_interval_ms: int


class BurstResponse(BaseModel):
    success: bool
    burst_id: str
    files: List[str]
    message: str


class BurstCoordinatorStatusResponse(BaseModel):
    is_bursting: bool
    total_bursts: int
    total_images: int
    last_burst_time: Optional[str]
    errors: int
    cam_b_initialized: bool
    cam_b_started: bool


# ============== API 端点 ==============

@router.get("/status", response_model=CamBStatusResponse)
async def get_cam_b_status() -> CamBStatusResponse:
    """获取 Cam-B 状态"""
    coordinator = get_burst_coordinator()
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Cam-B 未初始化")

    cam_b = coordinator.cam_b
    is_mock = isinstance(cam_b, MockCamB)

    return CamBStatusResponse(
        initialized=cam_b.is_initialized,
        started=cam_b.is_started,
        camera_type="mock" if is_mock else "real",
        resolution=list(cam_b.resolution),
        burst_count=cam_b.burst_count,
        burst_interval_ms=cam_b.burst_interval_ms
    )


@router.post("/burst", response_model=BurstResponse)
async def trigger_manual_burst() -> BurstResponse:
    """手动触发 Cam-B burst 拍摄"""
    coordinator = get_burst_coordinator()
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Cam-B 未初始化")

    if coordinator.is_bursting:
        raise HTTPException(status_code=409, detail="正在 burst 中，请稍后再试")

    cam_b = coordinator.cam_b
    if not cam_b.is_started:
        raise HTTPException(status_code=503, detail="Cam-B 未启动")

    # 直接执行 burst（手动触发不走推理回调）
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    burst_id = generate_time_id("burst")
    file_store = get_file_store()
    img_dir = file_store.get_image_dir(now)
    prefix = str(img_dir / f"{now.strftime('%H%M%S')}_{burst_id[-6:]}_cam_b")

    captured = cam_b.burst_capture(prefix)

    if not captured:
        raise HTTPException(status_code=500, detail="Burst 拍摄失败")

    # 保存元数据
    ts = now.isoformat()
    for i, file_path in enumerate(captured):
        metadata = {
            "image_id": generate_time_id("img"),
            "profile_id": "unknown",
            "camera_id": "cam_b",
            "ts": ts,
            "distance_bucket": "unknown",
            "focus_state": "fixed",
            "quality_score": 0.0,
            "file_path": file_path,
            "burst_id": burst_id,
            "burst_index": i,
            "trigger_source": "manual"
        }
        file_store.save_image_metadata(metadata)

    return BurstResponse(
        success=True,
        burst_id=burst_id,
        files=captured,
        message=f"Burst 完成: {len(captured)} 张"
    )


@router.get("/burst/status", response_model=BurstCoordinatorStatusResponse)
async def get_burst_status() -> BurstCoordinatorStatusResponse:
    """获取 burst 协调器状态"""
    coordinator = get_burst_coordinator()
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Burst 协调器未初始化")

    return BurstCoordinatorStatusResponse(**coordinator.status)
