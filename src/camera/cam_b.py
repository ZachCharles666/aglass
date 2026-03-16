"""
Cam-B (IMX477 HQ Camera) 控制模块
固定焦距，无自动对焦，用于花朵检测后的高分辨率 burst 拍摄
"""
import time
from typing import List, Tuple, Optional
from pathlib import Path

from .cam_base import CameraBase, MockCamera
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入 picamera2（仅在树莓派上可用）
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False


class CamB(CameraBase):
    """
    Cam-B (IMX477 HQ Camera) 控制类

    特性：
    - 固定焦距（无自动对焦）
    - 高分辨率：4056x3040
    - burst 连拍模式
    - 用于花朵检测后的高清拍摄
    """

    def __init__(
        self,
        camera_id: int = 1,
        identifier: str = "imx477",
        resolution: Tuple[int, int] = (4056, 3040),
        burst_count: int = 5,
        burst_interval_ms: int = 150
    ):
        super().__init__(camera_id, identifier)
        self.resolution = resolution
        self.burst_count = burst_count
        self.burst_interval_ms = burst_interval_ms

    def initialize(self) -> bool:
        """初始化 Cam-B"""
        if not PICAMERA2_AVAILABLE:
            logger.warning("picamera2 不可用，无法初始化真实 Cam-B")
            return False

        try:
            self.picam = Picamera2(self.camera_id)
            config = self.picam.create_still_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self.picam.configure(config)
            self._is_initialized = True
            logger.info(f"Cam-B 初始化成功: camera_id={self.camera_id}, resolution={self.resolution}")
            return True
        except Exception as e:
            logger.error(f"Cam-B 初始化失败: {e}")
            return False

    def start(self) -> bool:
        """启动 Cam-B"""
        if not self._is_initialized:
            if not self.initialize():
                return False

        try:
            self.picam.start()
            self._is_started = True
            logger.info("Cam-B 启动成功（固定焦距）")
            return True
        except Exception as e:
            logger.error(f"Cam-B 启动失败: {e}")
            return False

    def stop(self) -> None:
        """停止 Cam-B"""
        if self.picam and self._is_started:
            try:
                self.picam.stop()
                self._is_started = False
                logger.info("Cam-B 已停止")
            except Exception as e:
                logger.error(f"Cam-B 停止失败: {e}")

    def close(self) -> None:
        """关闭并释放 Cam-B 资源"""
        self.stop()
        if self.picam:
            try:
                self.picam.close()
                self.picam = None
                self._is_initialized = False
                logger.info("Cam-B 已关闭")
            except Exception as e:
                logger.error(f"Cam-B 关闭失败: {e}")

    def capture(self, file_path: str) -> bool:
        """拍摄单张照片"""
        if not self._is_started:
            logger.error("Cam-B 未启动，无法拍摄")
            return False

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            self.picam.capture_file(file_path)
            logger.info(f"Cam-B 拍摄成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Cam-B 拍摄失败: {e}")
            return False

    def get_metadata(self) -> dict:
        """获取当前相机元数据"""
        if not self._is_started:
            return {}

        try:
            return self.picam.capture_metadata()
        except Exception as e:
            logger.error(f"获取 Cam-B 元数据失败: {e}")
            return {}

    def burst_capture(self, file_path_prefix: str) -> List[str]:
        """
        连拍 N 张高分辨率照片

        Args:
            file_path_prefix: 文件路径前缀，如 "data/images/2024-01-01/burst_001"
                              输出: burst_001_0.jpg, burst_001_1.jpg, ...

        Returns:
            List[str]: 成功拍摄的文件路径列表
        """
        if not self._is_started:
            logger.error("Cam-B 未启动，无法 burst 拍摄")
            return []

        captured = []
        interval_sec = self.burst_interval_ms / 1000.0

        for i in range(self.burst_count):
            file_path = f"{file_path_prefix}_{i}.jpg"
            if self.capture(file_path):
                captured.append(file_path)
            else:
                logger.warning(f"Burst 第 {i} 张拍摄失败")

            # 最后一张不需要等待
            if i < self.burst_count - 1:
                time.sleep(interval_sec)

        logger.info(f"Burst 完成: {len(captured)}/{self.burst_count} 张成功")
        return captured


class MockCamB(MockCamera):
    """
    Cam-B 模拟类（用于开发机测试）
    """

    def __init__(
        self,
        camera_id: int = 1,
        identifier: str = "imx477_mock",
        resolution: Tuple[int, int] = (4056, 3040),
        burst_count: int = 5,
        burst_interval_ms: int = 150
    ):
        super().__init__(camera_id, identifier)
        self.resolution = resolution
        self.burst_count = burst_count
        self.burst_interval_ms = burst_interval_ms

    def burst_capture(self, file_path_prefix: str) -> List[str]:
        """
        模拟 burst 连拍

        创建空占位文件模拟拍摄
        """
        if not self._is_started:
            if not self._is_initialized:
                self.initialize()
            self.start()

        captured = []

        for i in range(self.burst_count):
            file_path = f"{file_path_prefix}_{i}.jpg"
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).touch()
            captured.append(file_path)

        logger.info(f"[Mock] Burst 完成: {len(captured)}/{self.burst_count} 张")
        return captured


def create_cam_b(use_mock: bool = False, **kwargs) -> CameraBase:
    """
    工厂函数：创建 Cam-B 实例

    Args:
        use_mock: 是否使用模拟相机
        **kwargs: 传递给相机构造函数的参数

    Returns:
        CamB 或 MockCamB 实例
    """
    if use_mock or not PICAMERA2_AVAILABLE:
        logger.info("使用 MockCamB")
        return MockCamB(**kwargs)
    else:
        logger.info("使用真实 CamB")
        return CamB(**kwargs)
