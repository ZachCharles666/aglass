"""
采集控制 API 端点
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from ..pipeline.capture_loop import CaptureLoop, get_capture_loop, set_capture_loop
from ..camera.af_control import AFController
from .routes_camera import get_controller
from ..store.file_store import get_file_store
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/capture", tags=["capture"])


# ============== Pydantic Models ==============

class CaptureStartRequest(BaseModel):
    interval_sec: float = 1.5


class CaptureStatusResponse(BaseModel):
    is_running: bool
    total_count: int
    last_capture_time: Optional[str]
    interval_sec: float
    uptime_seconds: float
    errors: int
    queue_size: int


class ImageSummaryResponse(BaseModel):
    total_count: int
    average_quality: float
    min_quality: float
    max_quality: float
    missing_files: int
    images: List[dict]


# ============== 依赖注入 ==============

def get_loop() -> CaptureLoop:
    """获取 CaptureLoop 实例"""
    return get_capture_loop()


# ============== API 端点 ==============

@router.post("/start")
async def start_capture(
    request: CaptureStartRequest = CaptureStartRequest(),
    loop: CaptureLoop = Depends(get_loop),
    af_controller: AFController = Depends(get_controller)
) -> dict:
    """
    启动采集循环

    Args:
        request: 包含 interval_sec 的请求体
    """
    # 确保 CaptureLoop 有正确的控制器
    if loop.af_controller is None:
        loop.af_controller = af_controller

    if loop.is_running:
        raise HTTPException(status_code=400, detail="采集循环已在运行")

    success = loop.start(interval_sec=request.interval_sec)

    if success:
        return {
            "success": True,
            "message": f"采集循环已启动，间隔 {request.interval_sec}s"
        }
    else:
        raise HTTPException(status_code=500, detail="启动采集循环失败")


@router.post("/stop")
async def stop_capture(
    loop: CaptureLoop = Depends(get_loop)
) -> dict:
    """
    停止采集循环
    """
    if not loop.is_running:
        raise HTTPException(status_code=400, detail="采集循环未在运行")

    success = loop.stop()

    if success:
        return {
            "success": True,
            "message": f"采集循环已停止，共采集 {loop.total_count} 张"
        }
    else:
        raise HTTPException(status_code=500, detail="停止采集循环失败")


@router.get("/status", response_model=CaptureStatusResponse)
async def get_capture_status(
    loop: CaptureLoop = Depends(get_loop)
) -> CaptureStatusResponse:
    """
    获取采集状态
    """
    status = loop.status
    return CaptureStatusResponse(**status)


@router.get("/summary")
async def get_capture_summary(
    minutes: int = 30
) -> ImageSummaryResponse:
    """
    获取采集摘要统计

    Args:
        minutes: 往前查询的分钟数
    """
    from pathlib import Path

    file_store = get_file_store()
    images = file_store.query_images_since(minutes_ago=minutes)

    if not images:
        return ImageSummaryResponse(
            total_count=0,
            average_quality=0.0,
            min_quality=0.0,
            max_quality=0.0,
            missing_files=0,
            images=[]
        )

    # 统计
    qualities = [img["quality_score"] for img in images if img["quality_score"]]
    missing_count = sum(1 for img in images if not Path(img["file_path"]).exists())

    avg_quality = sum(qualities) / len(qualities) if qualities else 0
    min_quality = min(qualities) if qualities else 0
    max_quality = max(qualities) if qualities else 0

    return ImageSummaryResponse(
        total_count=len(images),
        average_quality=round(avg_quality, 2),
        min_quality=round(min_quality, 2),
        max_quality=round(max_quality, 2),
        missing_files=missing_count,
        images=images[:100]  # 最多返回 100 条
    )


@router.get("/latest")
async def get_latest_capture() -> dict:
    """
    获取最新采集的图片
    """
    file_store = get_file_store()
    latest = file_store.get_latest_image()

    if latest:
        return {"success": True, "image": latest}
    else:
        return {"success": False, "image": None, "message": "暂无采集记录"}
