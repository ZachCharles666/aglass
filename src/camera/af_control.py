"""
统一对焦控制接口
提供对 Cam-A 对焦功能的封装
"""
from typing import Optional, Tuple

from .cam_a import CamA, MockCamA, get_clarity_score, create_cam_a, PICAMERA2_AVAILABLE
from .cam_base import CameraBase
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AFController:
    """
    自动对焦控制器

    提供统一的对焦控制接口，封装 Cam-A 的对焦功能
    """

    def __init__(self, camera: Optional[CameraBase] = None, use_mock: bool = False):
        """
        初始化对焦控制器

        Args:
            camera: 已初始化的相机实例（可选）
            use_mock: 是否使用模拟相机
        """
        self._camera = camera
        self._use_mock = use_mock or not PICAMERA2_AVAILABLE
        self._is_initialized = camera is not None

    def initialize(self, **camera_kwargs) -> bool:
        """
        初始化对焦控制器和相机

        Args:
            **camera_kwargs: 传递给相机构造函数的参数

        Returns:
            bool: 初始化是否成功
        """
        if self._is_initialized and self._camera is not None:
            logger.info("AFController 已初始化")
            return True

        try:
            self._camera = create_cam_a(use_mock=self._use_mock, **camera_kwargs)
            if self._camera.initialize() and self._camera.start():
                self._is_initialized = True
                logger.info("AFController 初始化成功")
                return True
            else:
                logger.error("AFController 初始化失败：相机启动失败")
                return False
        except Exception as e:
            logger.error(f"AFController 初始化失败: {e}")
            return False

    def close(self) -> None:
        """关闭对焦控制器和相机"""
        if self._camera:
            self._camera.close()
            self._camera = None
        self._is_initialized = False
        logger.info("AFController 已关闭")

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized

    @property
    def camera(self) -> Optional[CameraBase]:
        """获取相机实例"""
        return self._camera

    def trigger_one_shot_af(self, timeout: float = 3.0) -> Tuple[bool, float, Optional[float]]:
        """
        触发一次自动对焦

        ⚠️ 注意事项（遵循 SKILL Anti-patterns）：
        - 不要在连续采集时每张都调用此方法
        - 建议：建 Profile 时对焦一次，后续使用 lock_focus()

        Args:
            timeout: 超时时间（秒）

        Returns:
            Tuple[bool, float, Optional[float]]:
                - success: 对焦是否成功
                - duration: 对焦耗时（秒）
                - lens_position: 镜头位置
        """
        if not self._is_initialized or self._camera is None:
            logger.error("AFController 未初始化")
            return False, 0.0, None

        # 检查相机是否支持 one_shot_af
        if hasattr(self._camera, 'one_shot_af'):
            return self._camera.one_shot_af(timeout)
        else:
            logger.error("相机不支持 one_shot_af")
            return False, 0.0, None

    def lock_focus(self) -> Optional[float]:
        """
        锁定当前焦距

        Returns:
            Optional[float]: 锁定的镜头位置
        """
        if not self._is_initialized or self._camera is None:
            logger.error("AFController 未初始化")
            return None

        if hasattr(self._camera, 'lock_focus'):
            return self._camera.lock_focus()
        else:
            logger.error("相机不支持 lock_focus")
            return None

    def unlock_focus(self) -> bool:
        """
        解锁焦距，恢复自动对焦

        Returns:
            bool: 是否成功
        """
        if not self._is_initialized or self._camera is None:
            logger.error("AFController 未初始化")
            return False

        if hasattr(self._camera, 'unlock_focus'):
            return self._camera.unlock_focus()
        else:
            logger.error("相机不支持 unlock_focus")
            return False

    def get_af_state(self) -> dict:
        """
        获取当前对焦状态

        Returns:
            dict: 对焦状态信息
        """
        if not self._is_initialized or self._camera is None:
            return {
                "af_mode": "not_initialized",
                "lens_position": None,
                "af_state": "not_initialized",
                "locked_position": None
            }

        if hasattr(self._camera, 'get_af_state'):
            return self._camera.get_af_state()
        else:
            return {
                "af_mode": "unknown",
                "lens_position": None,
                "af_state": "unknown",
                "locked_position": None
            }

    def capture_and_get_clarity(self, file_path: str, method: str = "laplacian") -> Tuple[bool, float]:
        """
        拍摄照片并计算清晰度

        Args:
            file_path: 保存路径
            method: 清晰度计算方法

        Returns:
            Tuple[bool, float]: (拍摄是否成功, 清晰度分数)
        """
        if not self._is_initialized or self._camera is None:
            logger.error("AFController 未初始化")
            return False, 0.0

        success = self._camera.capture(file_path)
        if success:
            clarity = get_clarity_score(file_path, method)
            return True, clarity
        else:
            return False, 0.0


# 全局单例（可选）
_global_af_controller: Optional[AFController] = None


def get_af_controller() -> AFController:
    """
    获取全局 AFController 单例

    Returns:
        AFController 实例
    """
    global _global_af_controller
    if _global_af_controller is None:
        _global_af_controller = AFController()
    return _global_af_controller


def set_af_controller(controller: AFController) -> None:
    """
    设置全局 AFController 单例

    Args:
        controller: AFController 实例
    """
    global _global_af_controller
    _global_af_controller = controller
