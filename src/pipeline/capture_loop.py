"""
巡检采集循环模块
后台线程按 interval_sec 循环拍照（Cam-A）

⚠️ Anti-patterns（来自 SKILL）：
- 不要用 asyncio 包装 picamera2（同步 API 会卡死）
- 不要在回调里做推理（会阻塞采集主线程）
- 不要无限制入队（设置 maxsize 防止内存爆炸）
"""
import threading
import queue
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from ..camera.af_control import AFController
from ..camera.cam_a import get_clarity_score
from ..store.file_store import FileStore, get_file_store
from ..store.repo import get_profile_repo
from ..utils.logger import get_logger
from ..utils.time_id import generate_time_id

logger = get_logger(__name__)


class CaptureLoop:
    """
    巡检采集循环

    功能：
    - 后台线程循环拍照
    - 保存图片到 data/images/{date}/{ts}_cam_a.jpg
    - 保存元数据（JSON + SQLite）
    - 入队到推理队列（可选）
    """

    def __init__(
        self,
        af_controller: Optional[AFController] = None,
        file_store: Optional[FileStore] = None,
        interval_sec: float = 1.5,
        inference_queue: Optional[queue.Queue] = None
    ):
        """
        初始化采集循环

        Args:
            af_controller: 对焦控制器
            file_store: 文件存储
            interval_sec: 采集间隔（秒）
            inference_queue: 推理队列（可选）
        """
        self.af_controller = af_controller
        self.file_store = file_store or get_file_store()
        self.interval_sec = interval_sec
        self.inference_queue = inference_queue or queue.Queue(maxsize=50)

        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 统计信息
        self._total_count = 0
        self._last_capture_time: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._errors = 0

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running

    @property
    def total_count(self) -> int:
        """总拍摄数量"""
        return self._total_count

    @property
    def last_capture_time(self) -> Optional[str]:
        """最后一次拍摄时间"""
        return self._last_capture_time

    @property
    def status(self) -> Dict[str, Any]:
        """获取状态信息"""
        uptime = 0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            "is_running": self._is_running,
            "total_count": self._total_count,
            "last_capture_time": self._last_capture_time,
            "interval_sec": self.interval_sec,
            "uptime_seconds": round(uptime, 2),
            "errors": self._errors,
            "queue_size": self.inference_queue.qsize()
        }

    def start(self, interval_sec: Optional[float] = None) -> bool:
        """
        启动采集循环

        Args:
            interval_sec: 采集间隔（可选，覆盖初始化值）

        Returns:
            bool: 是否启动成功
        """
        with self._lock:
            if self._is_running:
                logger.warning("采集循环已在运行")
                return False

            if interval_sec is not None:
                self.interval_sec = interval_sec

            self._is_running = True
            self._start_time = datetime.now(timezone.utc)
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            logger.info(f"采集循环已启动: interval={self.interval_sec}s")
            return True

    def stop(self) -> bool:
        """
        停止采集循环

        Returns:
            bool: 是否停止成功
        """
        with self._lock:
            if not self._is_running:
                logger.warning("采集循环未在运行")
                return False

            self._is_running = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)

            logger.info(f"采集循环已停止: total_count={self._total_count}")
            return True

    def _capture_loop(self):
        """采集循环主函数"""
        logger.info("采集循环线程启动")

        while self._is_running:
            try:
                self._capture_one()
                time.sleep(self.interval_sec)

            except Exception as e:
                self._errors += 1
                logger.error(f"采集错误: {e}")
                time.sleep(1)  # 错误后短暂休眠

        logger.info("采集循环线程退出")

    def _capture_one(self):
        """拍摄一张照片"""
        # 生成时间戳和路径
        now = datetime.now(timezone.utc)
        ts = now.isoformat()
        date_str = now.strftime("%Y-%m-%d")
        image_id = generate_time_id("img")

        # 确保目录存在
        img_dir = self.file_store.get_image_dir(now)
        file_name = f"{now.strftime('%H%M%S')}_{image_id[-6:]}_cam_a.jpg"
        file_path = str(img_dir / file_name)

        # 获取当前 Profile
        profile_id = "unknown"
        focus_state = "unknown"

        try:
            repo = get_profile_repo()
            current_profile = repo.get_current_profile()
            if current_profile:
                profile_id = current_profile.profile_id
                focus_state = current_profile.cam_a_config.af_mode
        except Exception as e:
            logger.warning(f"获取当前 Profile 失败: {e}")

        # 拍照
        capture_success = False
        quality_score = 0.0

        if self.af_controller and self.af_controller.is_initialized:
            capture_success, quality_score = self.af_controller.capture_and_get_clarity(file_path)
        else:
            # Mock 模式：创建占位文件
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).touch()
            capture_success = True
            # Mock 清晰度
            import random
            quality_score = random.uniform(80, 200)

        if not capture_success:
            logger.warning(f"拍照失败: {file_path}")
            return

        # 构建元数据
        metadata = {
            "image_id": image_id,
            "profile_id": profile_id,
            "camera_id": "cam_a",
            "ts": ts,
            "distance_bucket": "unknown",  # 阶段 1A 固定
            "focus_state": focus_state,
            "quality_score": round(quality_score, 2),
            "file_path": file_path
        }

        # 保存元数据（双写 JSON + SQLite）
        self.file_store.save_image_metadata(metadata)

        # 更新统计
        self._total_count += 1
        self._last_capture_time = ts

        # 入推理队列（如果有）
        if self.inference_queue and not self.inference_queue.full():
            try:
                self.inference_queue.put_nowait((file_path, metadata))
            except queue.Full:
                logger.warning("推理队列已满，跳过入队")

        logger.debug(f"采集完成: {image_id}, quality={quality_score:.1f}")


# 全局采集循环实例
_capture_loop: Optional[CaptureLoop] = None


def get_capture_loop() -> CaptureLoop:
    """获取全局 CaptureLoop 实例"""
    global _capture_loop

    if _capture_loop is None:
        _capture_loop = CaptureLoop()

    return _capture_loop


def set_capture_loop(loop: CaptureLoop) -> None:
    """设置全局 CaptureLoop 实例"""
    global _capture_loop
    _capture_loop = loop
