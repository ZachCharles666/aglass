"""
相机控制 API 端点
包括 Cam-A 的对焦控制
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from ..camera.af_control import AFController, get_af_controller
from ..camera.cam_a import get_clarity_score
from ..utils.logger import get_logger
from ..utils.time_id import generate_time_id

logger = get_logger(__name__)

router = APIRouter(prefix="/camera", tags=["camera"])


# ============== Pydantic Models ==============

class OneShotAFRequest(BaseModel):
    timeout: float = 3.0


class OneShotAFResponse(BaseModel):
    success: bool
    duration: float
    lens_position: Optional[float]
    message: str


class LockFocusResponse(BaseModel):
    success: bool
    locked_position: Optional[float]
    message: str


class AFStateResponse(BaseModel):
    af_mode: str
    lens_position: Optional[float]
    af_state: str
    locked_position: Optional[float]
    clarity_score: Optional[float] = None


class CaptureRequest(BaseModel):
    file_path: Optional[str] = None


class CaptureResponse(BaseModel):
    success: bool
    file_path: str
    clarity_score: float
    message: str


# ============== 依赖注入 ==============

# 全局 AFController 实例
_af_controller: Optional[AFController] = None


def get_controller() -> AFController:
    """获取 AFController 实例"""
    global _af_controller
    if _af_controller is None:
        _af_controller = AFController(use_mock=True)  # 默认使用 mock
        _af_controller.initialize()
    return _af_controller


def init_camera_controller(use_mock: bool = True) -> AFController:
    """
    初始化相机控制器（在应用启动时调用）

    Args:
        use_mock: 是否使用模拟相机

    Returns:
        AFController 实例
    """
    global _af_controller
    _af_controller = AFController(use_mock=use_mock)
    _af_controller.initialize()
    logger.info(f"相机控制器已初始化: use_mock={use_mock}")
    return _af_controller


def close_camera_controller() -> None:
    """关闭相机控制器（在应用关闭时调用）"""
    global _af_controller
    if _af_controller:
        _af_controller.close()
        _af_controller = None
    logger.info("相机控制器已关闭")


# ============== API 端点 ==============

@router.post("/cam-a/af/one-shot", response_model=OneShotAFResponse)
async def trigger_one_shot_af(
    request: OneShotAFRequest = OneShotAFRequest(),
    controller: AFController = Depends(get_controller)
) -> OneShotAFResponse:
    """
    触发 Cam-A 一次自动对焦

    ⚠️ 注意事项：
    - 不要在连续采集时频繁调用此接口
    - 建议：建 Profile 时对焦一次，后续使用 /af/lock 锁定
    """
    if not controller.is_initialized:
        raise HTTPException(status_code=503, detail="相机控制器未初始化")

    success, duration, lens_pos = controller.trigger_one_shot_af(timeout=request.timeout)

    if success:
        message = f"对焦成功，耗时 {duration:.3f}s"
    else:
        message = f"对焦失败，超时 {request.timeout}s"

    return OneShotAFResponse(
        success=success,
        duration=round(duration, 3),
        lens_position=lens_pos,
        message=message
    )


@router.post("/cam-a/af/lock", response_model=LockFocusResponse)
async def lock_focus(
    controller: AFController = Depends(get_controller)
) -> LockFocusResponse:
    """
    锁定 Cam-A 当前焦距

    建议流程：
    1. 调用 /af/one-shot 完成对焦
    2. 调用此接口锁定焦距
    3. 后续采集时焦距保持不变
    """
    if not controller.is_initialized:
        raise HTTPException(status_code=503, detail="相机控制器未初始化")

    locked_pos = controller.lock_focus()

    if locked_pos is not None:
        return LockFocusResponse(
            success=True,
            locked_position=locked_pos,
            message=f"焦距已锁定: {locked_pos}"
        )
    else:
        return LockFocusResponse(
            success=False,
            locked_position=None,
            message="锁定失败，无法读取 LensPosition"
        )


@router.post("/cam-a/af/unlock", response_model=LockFocusResponse)
async def unlock_focus(
    controller: AFController = Depends(get_controller)
) -> LockFocusResponse:
    """
    解锁 Cam-A 焦距，恢复自动对焦模式
    """
    if not controller.is_initialized:
        raise HTTPException(status_code=503, detail="相机控制器未初始化")

    success = controller.unlock_focus()

    return LockFocusResponse(
        success=success,
        locked_position=None,
        message="焦距已解锁" if success else "解锁失败"
    )


@router.get("/cam-a/af/state", response_model=AFStateResponse)
async def get_af_state(
    controller: AFController = Depends(get_controller)
) -> AFStateResponse:
    """
    获取 Cam-A 当前对焦状态
    """
    state = controller.get_af_state()

    return AFStateResponse(
        af_mode=state.get("af_mode", "unknown"),
        lens_position=state.get("lens_position"),
        af_state=state.get("af_state", "unknown"),
        locked_position=state.get("locked_position"),
        clarity_score=None  # 需要拍照后才能计算
    )


@router.post("/cam-a/capture", response_model=CaptureResponse)
async def capture_image(
    request: CaptureRequest = CaptureRequest(),
    controller: AFController = Depends(get_controller)
) -> CaptureResponse:
    """
    使用 Cam-A 拍摄照片并计算清晰度
    """
    if not controller.is_initialized:
        raise HTTPException(status_code=503, detail="相机控制器未初始化")

    # 生成文件路径
    if request.file_path:
        file_path = request.file_path
    else:
        file_path = f"data/images/{generate_time_id('cam_a')}.jpg"

    success, clarity = controller.capture_and_get_clarity(file_path)

    if success:
        return CaptureResponse(
            success=True,
            file_path=file_path,
            clarity_score=round(clarity, 2),
            message=f"拍摄成功，清晰度: {clarity:.2f}"
        )
    else:
        raise HTTPException(status_code=500, detail="拍摄失败")


@router.get("/cam-a/status")
async def get_cam_a_status(
    controller: AFController = Depends(get_controller)
) -> dict:
    """
    获取 Cam-A 完整状态
    """
    af_state = controller.get_af_state()

    return {
        "initialized": controller.is_initialized,
        "camera_type": "mock" if not controller.is_initialized else (
            "mock" if hasattr(controller.camera, '_mock_lens_position') else "real"
        ),
        "af_state": af_state
    }
