"""
推理模块 API 端点
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from ..inference.models import Detection, DetectionResult
from ..inference.runner import get_inference_runner
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/inference", tags=["inference"])


# ============== Pydantic Models ==============

class InferenceStatusResponse(BaseModel):
    is_running: bool
    use_mock: bool
    total_processed: int
    total_detections: int
    total_bursts_triggered: int
    errors: int
    uptime_seconds: float
    queue_size: int


class DetectionResponse(BaseModel):
    class_name: str
    confidence: float
    bbox: List[float]
    class_id: int


class LatestResultResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    success: bool
    file_path: Optional[str] = None
    detections: List[DetectionResponse] = []
    inference_time_ms: float = 0.0
    model_name: str = ""
    trigger_burst: bool = False


# ============== API 端点 ==============

@router.get("/status", response_model=InferenceStatusResponse)
async def get_inference_status() -> InferenceStatusResponse:
    """获取推理模块状态"""
    runner = get_inference_runner()
    if runner is None:
        raise HTTPException(status_code=503, detail="推理模块未初始化")

    return InferenceStatusResponse(**runner.status)


@router.get("/latest", response_model=LatestResultResponse)
async def get_latest_result() -> LatestResultResponse:
    """获取最新检测结果"""
    runner = get_inference_runner()
    if runner is None:
        raise HTTPException(status_code=503, detail="推理模块未初始化")

    result = runner.latest_result
    if result is None:
        return LatestResultResponse(success=False)

    return LatestResultResponse(
        success=True,
        file_path=result.file_path,
        detections=[
            DetectionResponse(
                class_name=d.class_name,
                confidence=d.confidence,
                bbox=list(d.bbox),
                class_id=d.class_id
            )
            for d in result.detections
        ],
        inference_time_ms=result.inference_time_ms,
        model_name=result.model_name,
        trigger_burst=result.trigger_burst
    )


@router.post("/start")
async def start_inference() -> dict:
    """启动推理"""
    runner = get_inference_runner()
    if runner is None:
        raise HTTPException(status_code=503, detail="推理模块未初始化")

    if runner.is_running:
        raise HTTPException(status_code=400, detail="推理已在运行")

    success = runner.start()
    if success:
        return {"success": True, "message": "推理已启动"}
    else:
        raise HTTPException(status_code=500, detail="启动推理失败")


@router.post("/stop")
async def stop_inference() -> dict:
    """停止推理"""
    runner = get_inference_runner()
    if runner is None:
        raise HTTPException(status_code=503, detail="推理模块未初始化")

    if not runner.is_running:
        raise HTTPException(status_code=400, detail="推理未在运行")

    success = runner.stop()
    if success:
        return {"success": True, "message": f"推理已停止，共处理 {runner._total_processed} 张"}
    else:
        raise HTTPException(status_code=500, detail="停止推理失败")
