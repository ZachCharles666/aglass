"""
Burst 触发协调器
连接 flower_detector 检测结果和 Cam-B burst 拍摄

职责：
- 作为 InferenceRunner 的 burst_callback
- 检测到花朵时，在独立线程中执行 Cam-B burst（不阻塞推理线程）
- 防止重叠 burst
- 将 burst 图片元数据写入 FileStore
"""
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..camera.cam_b import CamB, MockCamB
from ..camera.cam_base import CameraBase
from ..inference.models import DetectionResult
from ..store.file_store import FileStore, get_file_store
from ..utils.logger import get_logger
from ..utils.time_id import generate_time_id

logger = get_logger(__name__)


class BurstCoordinator:
    """
    Burst 触发协调器

    功能：
    - 接收花朵检测结果
    - 在独立线程中执行 Cam-B burst 拍摄
    - 保存 burst 图片元数据到 FileStore
    - 防止重叠 burst（_is_bursting 标志）
    """

    def __init__(
        self,
        cam_b: CameraBase,
        file_store: Optional[FileStore] = None
    ):
        """
        Args:
            cam_b: Cam-B 相机实例（CamB 或 MockCamB）
            file_store: 文件存储实例
        """
        self.cam_b = cam_b
        self.file_store = file_store or get_file_store()

        self._is_bursting = False
        self._lock = threading.Lock()

        # 统计
        self._total_bursts = 0
        self._total_images = 0
        self._last_burst_time: Optional[str] = None
        self._errors = 0

    def on_flower_detected(self, result: DetectionResult) -> None:
        """
        花朵检测回调（由 InferenceRunner 调用）

        在独立线程中执行 burst，不阻塞推理线程。
        如果正在 burst 中，跳过本次触发。

        Args:
            result: 触发 burst 的检测结果
        """
        with self._lock:
            if self._is_bursting:
                logger.info("正在 burst 中，跳过本次触发")
                return
            self._is_bursting = True

        # 在独立线程中执行 burst
        thread = threading.Thread(
            target=self._execute_burst,
            args=(result,),
            daemon=True
        )
        thread.start()

    def _execute_burst(self, result: DetectionResult):
        """执行一次 burst 拍摄"""
        try:
            now = datetime.now(timezone.utc)
            burst_id = generate_time_id("burst")
            ts = now.isoformat()

            logger.info(f"开始 burst 拍摄: burst_id={burst_id}")

            # 构建文件路径前缀
            img_dir = self.file_store.get_image_dir(now)
            prefix = str(img_dir / f"{now.strftime('%H%M%S')}_{burst_id[-6:]}_cam_b")

            # 执行 burst
            captured_files = self.cam_b.burst_capture(prefix)

            if not captured_files:
                logger.warning(f"Burst 拍摄失败: burst_id={burst_id}")
                self._errors += 1
                return

            # 保存每张 burst 图片的元数据
            for i, file_path in enumerate(captured_files):
                image_id = generate_time_id("img")
                metadata = {
                    "image_id": image_id,
                    "profile_id": "unknown",
                    "camera_id": "cam_b",
                    "ts": ts,
                    "distance_bucket": "unknown",
                    "focus_state": "fixed",
                    "quality_score": 0.0,
                    "file_path": file_path,
                    "burst_id": burst_id,
                    "burst_index": i,
                    "trigger_source": result.file_path
                }
                self.file_store.save_image_metadata(metadata)

            # 更新统计
            self._total_bursts += 1
            self._total_images += len(captured_files)
            self._last_burst_time = ts

            logger.info(
                f"Burst 完成: burst_id={burst_id}, "
                f"images={len(captured_files)}"
            )

        except Exception as e:
            self._errors += 1
            logger.error(f"Burst 执行失败: {e}")

        finally:
            with self._lock:
                self._is_bursting = False

    @property
    def is_bursting(self) -> bool:
        return self._is_bursting

    @property
    def status(self) -> Dict[str, Any]:
        """获取 burst 协调器状态"""
        return {
            "is_bursting": self._is_bursting,
            "total_bursts": self._total_bursts,
            "total_images": self._total_images,
            "last_burst_time": self._last_burst_time,
            "errors": self._errors,
            "cam_b_initialized": self.cam_b.is_initialized if self.cam_b else False,
            "cam_b_started": self.cam_b.is_started if self.cam_b else False
        }


# 全局 BurstCoordinator 实例
_burst_coordinator: Optional[BurstCoordinator] = None


def get_burst_coordinator() -> Optional[BurstCoordinator]:
    """获取全局 BurstCoordinator 实例"""
    return _burst_coordinator


def set_burst_coordinator(coordinator: BurstCoordinator) -> None:
    """设置全局 BurstCoordinator 实例"""
    global _burst_coordinator
    _burst_coordinator = coordinator
