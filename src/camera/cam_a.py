"""
Cam-A (IMX708 Module 3) 控制模块
支持自动对焦 (PDAF)，针对 40-52cm 近距离优化
"""
import time
from typing import Optional, Tuple
from pathlib import Path

import cv2
import numpy as np

from .cam_base import CameraBase, MockCamera
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入 picamera2（仅在树莓派上可用）
try:
    from picamera2 import Picamera2
    from libcamera import controls
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    logger.warning("picamera2 不可用，将使用 MockCamera")


class CamA(CameraBase):
    """
    Cam-A (IMX708 Module 3) 控制类

    特性：
    - 相位检测自动对焦 (PDAF)
    - 对焦范围：10cm 到无穷远
    - 最佳工作距离：40-52cm（近档巡检）
    - 对焦速度：Macro 模式下 500ms-1.2s
    """

    def __init__(
        self,
        camera_id: int = 0,
        identifier: str = "imx708",
        resolution: Tuple[int, int] = (1920, 1080)
    ):
        super().__init__(camera_id, identifier)
        self.resolution = resolution
        self._af_mode = "auto"
        self._locked_lens_position: Optional[float] = None

    def initialize(self) -> bool:
        """初始化 Cam-A"""
        if not PICAMERA2_AVAILABLE:
            logger.warning("picamera2 不可用，无法初始化真实相机")
            return False

        try:
            self.picam = Picamera2(self.camera_id)
            config = self.picam.create_still_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self.picam.configure(config)
            self._is_initialized = True
            logger.info(f"Cam-A 初始化成功: camera_id={self.camera_id}, resolution={self.resolution}")
            return True
        except Exception as e:
            logger.error(f"Cam-A 初始化失败: {e}")
            return False

    def start(self) -> bool:
        """启动 Cam-A 并设置对焦参数"""
        if not self._is_initialized:
            if not self.initialize():
                return False

        try:
            self.picam.start()

            # 设置对焦参数：Auto + Macro + Fast
            # 针对 40-52cm 近距离优化
            self.picam.set_controls({
                "AfMode": controls.AfModeEnum.Auto,
                "AfRange": controls.AfRangeEnum.Macro,
                "AfSpeed": controls.AfSpeedEnum.Fast
            })

            self._af_mode = "auto"
            self._is_started = True
            logger.info("Cam-A 启动成功，对焦模式: Auto/Macro/Fast")
            return True
        except Exception as e:
            logger.error(f"Cam-A 启动失败: {e}")
            return False

    def stop(self) -> None:
        """停止 Cam-A"""
        if self.picam and self._is_started:
            try:
                self.picam.stop()
                self._is_started = False
                logger.info("Cam-A 已停止")
            except Exception as e:
                logger.error(f"Cam-A 停止失败: {e}")

    def close(self) -> None:
        """关闭并释放 Cam-A 资源"""
        self.stop()
        if self.picam:
            try:
                self.picam.close()
                self.picam = None
                self._is_initialized = False
                logger.info("Cam-A 已关闭")
            except Exception as e:
                logger.error(f"Cam-A 关闭失败: {e}")

    def capture(self, file_path: str) -> bool:
        """拍摄照片"""
        if not self._is_started:
            logger.error("Cam-A 未启动，无法拍摄")
            return False

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            self.picam.capture_file(file_path)
            logger.info(f"Cam-A 拍摄成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Cam-A 拍摄失败: {e}")
            return False

    def get_metadata(self) -> dict:
        """获取当前相机元数据"""
        if not self._is_started:
            return {}

        try:
            return self.picam.capture_metadata()
        except Exception as e:
            logger.error(f"获取元数据失败: {e}")
            return {}

    def one_shot_af(self, timeout: float = 3.0) -> Tuple[bool, float, Optional[float]]:
        """
        触发一次自动对焦并等待完成

        ⚠️ Anti-pattern 警告：
        - 不要在连续采集时每张都触发 AF（会导致巡检速度慢且不稳定）
        - 正确做法：建 Profile 时对焦一次，后续锁定焦距

        Args:
            timeout: 超时时间（秒），默认 3.0s

        Returns:
            Tuple[bool, float, Optional[float]]:
                - success: 对焦是否成功
                - duration: 对焦耗时（秒）
                - lens_position: 镜头位置（对焦成功时）
        """
        if not self._is_started:
            logger.error("Cam-A 未启动，无法对焦")
            return False, 0.0, None

        try:
            # 确保处于 Auto 模式并触发对焦
            self.picam.set_controls({
                "AfMode": controls.AfModeEnum.Auto,
                "AfTrigger": controls.AfTriggerEnum.Start
            })

            start = time.time()
            while time.time() - start < timeout:
                metadata = self.picam.capture_metadata()
                af_state = metadata.get("AfState", None)

                if af_state == controls.AfStateEnum.Focused:
                    duration = time.time() - start
                    lens_pos = metadata.get("LensPosition", None)
                    logger.info(f"对焦成功: duration={duration:.3f}s, lens_position={lens_pos}")
                    return True, duration, lens_pos

                time.sleep(0.05)  # 50ms 轮询

            logger.warning(f"对焦超时: timeout={timeout}s")
            return False, timeout, None

        except Exception as e:
            logger.error(f"对焦失败: {e}")
            return False, 0.0, None

    def lock_focus(self) -> Optional[float]:
        """
        锁定当前焦距，禁止继续对焦（防止 hunting）

        使用场景：建立 Profile 后，在整个巡检过程中保持焦距不变

        ⚠️ Anti-pattern 警告：
        - 不要用 AfMode.Continuous（会持续 hunting，消耗算力）

        Returns:
            Optional[float]: 锁定的镜头位置，失败时返回 None
        """
        if not self._is_started:
            logger.error("Cam-A 未启动，无法锁定焦距")
            return None

        try:
            # 读取当前焦距位置
            metadata = self.picam.capture_metadata()
            lens_pos = metadata.get("LensPosition", None)

            # 切换到 Manual 模式并锁定焦距
            if lens_pos is not None:
                self.picam.set_controls({
                    "AfMode": controls.AfModeEnum.Manual,
                    "LensPosition": lens_pos
                })
                self._af_mode = "locked"
                self._locked_lens_position = lens_pos
                logger.info(f"焦距已锁定: lens_position={lens_pos}")
                return lens_pos
            else:
                # 如果无法读取 LensPosition，仅切换模式
                self.picam.set_controls({"AfMode": controls.AfModeEnum.Manual})
                self._af_mode = "locked"
                logger.warning("无法读取 LensPosition，仅切换到 Manual 模式")
                return None

        except Exception as e:
            logger.error(f"锁定焦距失败: {e}")
            return None

    def unlock_focus(self) -> bool:
        """
        解锁焦距，恢复自动对焦模式

        Returns:
            bool: 是否成功解锁
        """
        if not self._is_started:
            logger.error("Cam-A 未启动")
            return False

        try:
            self.picam.set_controls({
                "AfMode": controls.AfModeEnum.Auto,
                "AfRange": controls.AfRangeEnum.Macro,
                "AfSpeed": controls.AfSpeedEnum.Fast
            })
            self._af_mode = "auto"
            self._locked_lens_position = None
            logger.info("焦距已解锁，恢复 Auto 模式")
            return True
        except Exception as e:
            logger.error(f"解锁焦距失败: {e}")
            return False

    def get_af_state(self) -> dict:
        """
        获取当前对焦状态

        Returns:
            dict: 包含 af_mode, lens_position, af_state 的字典
        """
        metadata = self.get_metadata()

        af_state_value = metadata.get("AfState", None)
        af_state_str = "unknown"
        if PICAMERA2_AVAILABLE and af_state_value is not None:
            try:
                if af_state_value == controls.AfStateEnum.Idle:
                    af_state_str = "idle"
                elif af_state_value == controls.AfStateEnum.Scanning:
                    af_state_str = "scanning"
                elif af_state_value == controls.AfStateEnum.Focused:
                    af_state_str = "focused"
                elif af_state_value == controls.AfStateEnum.Failed:
                    af_state_str = "failed"
            except Exception:
                pass

        return {
            "af_mode": self._af_mode,
            "lens_position": metadata.get("LensPosition", self._locked_lens_position),
            "af_state": af_state_str,
            "locked_position": self._locked_lens_position
        }

    @property
    def af_mode(self) -> str:
        """当前对焦模式"""
        return self._af_mode

    @property
    def locked_lens_position(self) -> Optional[float]:
        """锁定的镜头位置"""
        return self._locked_lens_position


class MockCamA(MockCamera):
    """
    Cam-A 模拟类（用于开发机测试）
    """

    def __init__(
        self,
        camera_id: int = 0,
        identifier: str = "imx708_mock",
        resolution: Tuple[int, int] = (1920, 1080)
    ):
        super().__init__(camera_id, identifier)
        self.resolution = resolution
        self._af_mode = "auto"
        self._locked_lens_position: Optional[float] = None
        self._mock_af_duration = 0.8  # 模拟对焦耗时

    def one_shot_af(self, timeout: float = 3.0) -> Tuple[bool, float, Optional[float]]:
        """模拟 one-shot 自动对焦"""
        if not self._is_started:
            return False, 0.0, None

        # 模拟对焦过程
        time.sleep(min(self._mock_af_duration, timeout))

        if self._mock_af_duration <= timeout:
            lens_pos = self._mock_lens_position
            logger.info(f"[Mock] 对焦成功: duration={self._mock_af_duration}s, lens_position={lens_pos}")
            return True, self._mock_af_duration, lens_pos
        else:
            logger.warning(f"[Mock] 对焦超时: timeout={timeout}s")
            return False, timeout, None

    def lock_focus(self) -> Optional[float]:
        """模拟锁定焦距"""
        if not self._is_started:
            return None

        self._af_mode = "locked"
        self._locked_lens_position = self._mock_lens_position
        logger.info(f"[Mock] 焦距已锁定: lens_position={self._locked_lens_position}")
        return self._locked_lens_position

    def unlock_focus(self) -> bool:
        """模拟解锁焦距"""
        if not self._is_started:
            return False

        self._af_mode = "auto"
        self._locked_lens_position = None
        logger.info("[Mock] 焦距已解锁")
        return True

    def get_af_state(self) -> dict:
        """获取模拟对焦状态"""
        return {
            "af_mode": self._af_mode,
            "lens_position": self._mock_lens_position,
            "af_state": "focused" if self._af_mode == "locked" else "idle",
            "locked_position": self._locked_lens_position
        }

    @property
    def af_mode(self) -> str:
        return self._af_mode

    @property
    def locked_lens_position(self) -> Optional[float]:
        return self._locked_lens_position


def get_clarity_score(image_path: str, method: str = "laplacian") -> float:
    """
    计算图像清晰度分数

    Args:
        image_path: 图像文件路径
        method: 计算方法 ("laplacian" 或 "tenengrad")

    Returns:
        float: 清晰度分数（越大越清晰，通常 >100 为可接受）
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.warning(f"无法读取图像: {image_path}")
        return 0.0

    if method == "laplacian":
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        score = float(laplacian.var())
    elif method == "tenengrad":
        gx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx**2 + gy**2)
        score = float(np.sum(gradient_magnitude**2))
    else:
        logger.warning(f"未知的清晰度计算方法: {method}，使用 laplacian")
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        score = float(laplacian.var())

    return score


def create_cam_a(use_mock: bool = False, **kwargs) -> CameraBase:
    """
    工厂函数：创建 Cam-A 实例

    Args:
        use_mock: 是否使用模拟相机
        **kwargs: 传递给相机构造函数的参数

    Returns:
        CamA 或 MockCamA 实例
    """
    if use_mock or not PICAMERA2_AVAILABLE:
        logger.info("使用 MockCamA")
        return MockCamA(**kwargs)
    else:
        logger.info("使用真实 CamA")
        return CamA(**kwargs)
