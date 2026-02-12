"""
相机基类
定义相机的初始化、关闭等通用方法
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CameraBase(ABC):
    """相机基类"""

    def __init__(self, camera_id: int = 0, identifier: str = ""):
        """
        初始化相机基类

        Args:
            camera_id: 相机设备 ID（对应 /dev/video{id}）
            identifier: 相机标识符（用于枚举匹配）
        """
        self.camera_id = camera_id
        self.identifier = identifier
        self.picam = None
        self._is_initialized = False
        self._is_started = False

    @property
    def is_initialized(self) -> bool:
        """相机是否已初始化"""
        return self._is_initialized

    @property
    def is_started(self) -> bool:
        """相机是否已启动"""
        return self._is_started

    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化相机

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    def start(self) -> bool:
        """
        启动相机

        Returns:
            bool: 启动是否成功
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止相机"""
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭并释放相机资源"""
        pass

    @abstractmethod
    def capture(self, file_path: str) -> bool:
        """
        拍摄照片并保存

        Args:
            file_path: 保存路径

        Returns:
            bool: 拍摄是否成功
        """
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """
        获取当前相机元数据

        Returns:
            dict: 元数据字典
        """
        pass

    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop()
        self.close()
        return False


class MockCamera(CameraBase):
    """
    模拟相机（用于开发机测试）
    """

    def __init__(self, camera_id: int = 0, identifier: str = "mock"):
        super().__init__(camera_id, identifier)
        self._mock_lens_position = 5.0
        self._mock_af_state = "Focused"

    def initialize(self) -> bool:
        logger.info(f"MockCamera {self.camera_id} 初始化")
        self._is_initialized = True
        return True

    def start(self) -> bool:
        if not self._is_initialized:
            self.initialize()
        logger.info(f"MockCamera {self.camera_id} 启动")
        self._is_started = True
        return True

    def stop(self) -> None:
        logger.info(f"MockCamera {self.camera_id} 停止")
        self._is_started = False

    def close(self) -> None:
        self.stop()
        logger.info(f"MockCamera {self.camera_id} 关闭")
        self._is_initialized = False

    def capture(self, file_path: str) -> bool:
        logger.info(f"MockCamera 拍摄: {file_path}")
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        # 创建一个空文件作为占位
        Path(file_path).touch()
        return True

    def get_metadata(self) -> dict:
        return {
            "LensPosition": self._mock_lens_position,
            "AfState": self._mock_af_state,
            "ExposureTime": 10000,
            "AnalogueGain": 1.0
        }

    def set_mock_lens_position(self, position: float) -> None:
        """设置模拟镜头位置"""
        self._mock_lens_position = position

    def set_mock_af_state(self, state: str) -> None:
        """设置模拟对焦状态"""
        self._mock_af_state = state
