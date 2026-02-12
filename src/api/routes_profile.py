"""
Profile 管理 API 端点
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List

from ..store.models import (
    FocusProfile, CameraConfig, DistancePolicy,
    ProfileCreateRequest, ProfileResponse, ProfileListResponse
)
from ..store.repo import ProfileRepository, get_profile_repo
from ..camera.af_control import AFController
from .routes_camera import get_controller
from ..utils.logger import get_logger
from ..utils.time_id import get_iso_timestamp

logger = get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


# ============== 依赖注入 ==============

def get_repo() -> ProfileRepository:
    """获取 ProfileRepository 实例"""
    return get_profile_repo()


# ============== 辅助函数 ==============

def profile_to_response(profile: FocusProfile) -> ProfileResponse:
    """将 FocusProfile 转换为 API 响应格式"""
    return ProfileResponse(
        profile_id=profile.profile_id,
        operator_id=profile.operator_id,
        created_at=profile.created_at.isoformat(),
        cam_a_config=profile.cam_a_config,
        distance_policy=profile.distance_policy,
        notes=profile.notes,
        is_current=profile.is_current
    )


# ============== API 端点 ==============

@router.post("/create", response_model=ProfileResponse)
async def create_profile(
    request: ProfileCreateRequest,
    repo: ProfileRepository = Depends(get_repo),
    af_controller: AFController = Depends(get_controller)
) -> ProfileResponse:
    """
    创建新的 Focus Profile

    流程：
    1. 触发 Cam-A one-shot 自动对焦
    2. 锁定焦距
    3. 保存 Profile 到数据库
    4. 设置为当前 Profile

    Args:
        request: 包含 operator_id 和 notes 的请求体
    """
    logger.info(f"创建 Profile: operator={request.operator_id}")

    # 1. 检查相机是否初始化
    if not af_controller.is_initialized:
        raise HTTPException(status_code=503, detail="相机控制器未初始化")

    # 2. 触发 one-shot 自动对焦
    success, duration, lens_pos = af_controller.trigger_one_shot_af(timeout=3.0)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"对焦失败，超时 3.0s。请确保光照充足（>300 lux）且目标距离在 10cm-2m 范围内"
        )

    # 3. 锁定焦距
    locked_pos = af_controller.lock_focus()

    if locked_pos is None:
        logger.warning("无法读取 LensPosition，使用对焦返回的位置")
        locked_pos = lens_pos

    # 4. 创建 Profile 对象
    profile = FocusProfile(
        operator_id=request.operator_id,
        cam_a_config=CameraConfig(
            af_mode="locked",
            lens_position=locked_pos,
            focus_distance_cm=request.focus_distance_cm
        ),
        distance_policy=DistancePolicy(),
        notes=request.notes,
        is_current=True
    )

    # 5. 保存到数据库
    if not repo.save_profile(profile):
        raise HTTPException(status_code=500, detail="保存 Profile 失败")

    # 6. 设置为当前 Profile
    repo.set_current_profile(profile.profile_id)

    logger.info(f"Profile 创建成功: {profile.profile_id}, lens_position={locked_pos}, duration={duration:.3f}s")

    return profile_to_response(profile)


@router.get("/current", response_model=Optional[ProfileResponse])
async def get_current_profile(
    repo: ProfileRepository = Depends(get_repo)
) -> Optional[ProfileResponse]:
    """
    获取当前激活的 Profile
    """
    profile = repo.get_current_profile()

    if profile:
        return profile_to_response(profile)
    return None


@router.get("/list", response_model=ProfileListResponse)
async def list_profiles(
    limit: int = 100,
    offset: int = 0,
    repo: ProfileRepository = Depends(get_repo)
) -> ProfileListResponse:
    """
    列出所有 Profile
    """
    profiles = repo.list_profiles(limit=limit, offset=offset)
    total = repo.count_profiles()
    current = repo.get_current_profile()

    return ProfileListResponse(
        profiles=[profile_to_response(p) for p in profiles],
        total=total,
        current_profile_id=current.profile_id if current else None
    )


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    repo: ProfileRepository = Depends(get_repo)
) -> ProfileResponse:
    """
    根据 ID 获取 Profile
    """
    profile = repo.get_profile_by_id(profile_id)

    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile 不存在: {profile_id}")

    return profile_to_response(profile)


@router.post("/select/{profile_id}")
async def select_profile(
    profile_id: str,
    repo: ProfileRepository = Depends(get_repo),
    af_controller: AFController = Depends(get_controller)
) -> dict:
    """
    选择并激活指定的 Profile

    会根据 Profile 中保存的 lens_position 重新设置相机焦距
    """
    # 获取 Profile
    profile = repo.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile 不存在: {profile_id}")

    # 设置为当前 Profile
    if not repo.set_current_profile(profile_id):
        raise HTTPException(status_code=500, detail="设置当前 Profile 失败")

    # 如果相机已初始化，恢复焦距设置
    if af_controller.is_initialized and profile.cam_a_config.lens_position is not None:
        # 锁定到 Profile 中保存的焦距
        camera = af_controller.camera
        if camera and hasattr(camera, 'picam') and camera.picam:
            try:
                from libcamera import controls
                camera.picam.set_controls({
                    "AfMode": controls.AfModeEnum.Manual,
                    "LensPosition": profile.cam_a_config.lens_position
                })
                logger.info(f"已恢复焦距: {profile.cam_a_config.lens_position}")
            except Exception as e:
                logger.warning(f"恢复焦距失败（可能是 Mock 模式）: {e}")

    return {
        "success": True,
        "profile_id": profile_id,
        "message": f"已切换到 Profile: {profile_id}"
    }


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    repo: ProfileRepository = Depends(get_repo)
) -> dict:
    """
    删除指定的 Profile

    注意：不能删除当前激活的 Profile
    """
    # 检查是否为当前 Profile
    current = repo.get_current_profile()
    if current and current.profile_id == profile_id:
        raise HTTPException(
            status_code=400,
            detail="不能删除当前激活的 Profile，请先切换到其他 Profile"
        )

    # 删除
    if not repo.delete_profile(profile_id):
        raise HTTPException(status_code=500, detail="删除 Profile 失败")

    return {
        "success": True,
        "profile_id": profile_id,
        "message": f"Profile 已删除: {profile_id}"
    }
