"""
推理运行器
后台线程消费 inference_queue，运行 YOLO 模型推理

Mock 模式：不加载 YOLO，返回空/随机检测结果
Real 模式：加载 .pt 模型，调用 model() 推理
"""
import random
import threading
import time
import queue
from typing import Optional, Callable, Dict, Any, List

from .models import Detection, DetectionResult
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入 ultralytics
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logger.info("ultralytics 不可用，推理将使用 mock 模式")


# Mock 模式的随机类别
_MOCK_PLANT_CLASSES = [
    "Apple", "Blueberry", "Cherry", "Corn", "Grape",
    "Peach", "Pepper_bell", "Potato", "Raspberry",
    "Soybean", "Squash", "Strawberry", "Tomato"
]


class InferenceRunner:
    """
    推理运行器

    从 inference_queue 消费图片，依次运行 plant_detector 和 flower_detector，
    检测到花朵时调用 burst_callback。
    """

    def __init__(
        self,
        inference_queue: queue.Queue,
        config: Optional[dict] = None,
        use_mock: bool = True,
        burst_callback: Optional[Callable[[DetectionResult], None]] = None
    ):
        """
        Args:
            inference_queue: 推理队列（来自 CaptureLoop）
            config: device.yaml 中的 inference 配置段
            use_mock: 是否使用 mock 模式
            burst_callback: 检测到花朵时的回调函数
        """
        self.inference_queue = inference_queue
        self.config = config or {}
        self.use_mock = use_mock or not ULTRALYTICS_AVAILABLE
        self.burst_callback = burst_callback

        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 模型实例（real 模式）
        self._plant_model = None
        self._flower_model = None

        # 统计
        self._total_processed = 0
        self._total_detections = 0
        self._total_bursts_triggered = 0
        self._errors = 0
        self._last_result: Optional[DetectionResult] = None
        self._start_time: Optional[float] = None

    def _load_models(self) -> bool:
        """加载 YOLO 模型（仅 real 模式）"""
        if self.use_mock:
            logger.info("Mock 模式，跳过模型加载")
            return True

        try:
            plant_cfg = self.config.get("plant_detector", {})
            flower_cfg = self.config.get("flower_detector", {})

            plant_path = plant_cfg.get("model_path", "models/plant_detector_v1.pt")
            flower_path = flower_cfg.get("model_path", "models/flower_detector_v1.pt")

            logger.info(f"加载 plant_detector: {plant_path}")
            self._plant_model = YOLO(plant_path)

            logger.info(f"加载 flower_detector: {flower_path}")
            self._flower_model = YOLO(flower_path)

            logger.info("模型加载完成")
            return True
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False

    def start(self) -> bool:
        """启动推理线程"""
        with self._lock:
            if self._is_running:
                logger.warning("推理线程已在运行")
                return False

            if not self._load_models():
                return False

            self._is_running = True
            self._start_time = time.time()
            self._thread = threading.Thread(target=self._inference_loop, daemon=True)
            self._thread.start()

            logger.info(f"推理线程已启动: mock={self.use_mock}")
            return True

    def stop(self) -> bool:
        """停止推理线程"""
        with self._lock:
            if not self._is_running:
                logger.warning("推理线程未在运行")
                return False

            self._is_running = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)

            logger.info(f"推理线程已停止: total_processed={self._total_processed}")
            return True

    def _inference_loop(self):
        """推理循环主函数"""
        logger.info("推理循环线程启动")

        while self._is_running:
            try:
                # 从队列取数据，超时 1 秒
                item = self.inference_queue.get(timeout=1.0)
                file_path, metadata = item

                # 运行推理
                self._process_one(file_path, metadata)

            except queue.Empty:
                continue
            except Exception as e:
                self._errors += 1
                logger.error(f"推理错误: {e}")

        logger.info("推理循环线程退出")

    def _process_one(self, file_path: str, metadata: dict):
        """处理一张图片"""
        if self.use_mock:
            result = self._mock_inference(file_path)
        else:
            result = self._real_inference(file_path)

        self._total_processed += 1
        self._total_detections += len(result.detections)
        self._last_result = result

        # 如果触发 burst，调用回调
        if result.trigger_burst:
            self._total_bursts_triggered += 1
            logger.info(f"花朵检测触发 burst: {file_path}")
            if self.burst_callback:
                try:
                    self.burst_callback(result)
                except Exception as e:
                    logger.error(f"Burst 回调失败: {e}")

        logger.debug(
            f"推理完成: {file_path}, "
            f"detections={len(result.detections)}, "
            f"trigger_burst={result.trigger_burst}, "
            f"time={result.inference_time_ms:.1f}ms"
        )

    def _mock_inference(self, file_path: str) -> DetectionResult:
        """Mock 推理：返回随机检测结果"""
        start = time.time()

        detections: List[Detection] = []

        # plant_detector: 随机生成 0-3 个检测
        num_plants = random.randint(0, 3)
        for _ in range(num_plants):
            cls_name = random.choice(_MOCK_PLANT_CLASSES)
            detections.append(Detection(
                class_name=cls_name,
                confidence=round(random.uniform(0.3, 0.95), 3),
                bbox=(
                    round(random.uniform(0, 500), 1),
                    round(random.uniform(0, 500), 1),
                    round(random.uniform(500, 1000), 1),
                    round(random.uniform(500, 1000), 1)
                ),
                class_id=_MOCK_PLANT_CLASSES.index(cls_name)
            ))

        # flower_detector: 10% 概率触发
        trigger_burst = random.random() < 0.1
        if trigger_burst:
            detections.append(Detection(
                class_name="flower",
                confidence=round(random.uniform(0.5, 0.95), 3),
                bbox=(
                    round(random.uniform(200, 400), 1),
                    round(random.uniform(200, 400), 1),
                    round(random.uniform(600, 800), 1),
                    round(random.uniform(600, 800), 1)
                ),
                class_id=0
            ))

        elapsed_ms = (time.time() - start) * 1000

        return DetectionResult(
            file_path=file_path,
            detections=detections,
            inference_time_ms=round(elapsed_ms, 2),
            model_name="mock",
            trigger_burst=trigger_burst
        )

    def _real_inference(self, file_path: str) -> DetectionResult:
        """Real 推理：运行 YOLO 模型"""
        start = time.time()
        detections: List[Detection] = []
        trigger_burst = False

        plant_cfg = self.config.get("plant_detector", {})
        flower_cfg = self.config.get("flower_detector", {})

        # 运行 plant_detector
        if self._plant_model:
            try:
                results = self._plant_model(
                    file_path,
                    conf=plant_cfg.get("conf_threshold", 0.3),
                    imgsz=plant_cfg.get("imgsz", 640),
                    verbose=False
                )
                for r in results:
                    for box in r.boxes:
                        detections.append(Detection(
                            class_name=r.names[int(box.cls)],
                            confidence=round(float(box.conf), 3),
                            bbox=tuple(round(float(x), 1) for x in box.xyxy[0]),
                            class_id=int(box.cls)
                        ))
            except Exception as e:
                logger.error(f"plant_detector 推理失败: {e}")

        # 运行 flower_detector
        if self._flower_model:
            try:
                results = self._flower_model(
                    file_path,
                    conf=flower_cfg.get("conf_threshold", 0.4),
                    imgsz=flower_cfg.get("imgsz", 640),
                    verbose=False
                )
                for r in results:
                    for box in r.boxes:
                        cls_name = r.names[int(box.cls)]
                        detections.append(Detection(
                            class_name=cls_name,
                            confidence=round(float(box.conf), 3),
                            bbox=tuple(round(float(x), 1) for x in box.xyxy[0]),
                            class_id=int(box.cls)
                        ))
                        # 检测到花朵类别时触发 burst
                        if cls_name.lower() in ("flower", "hortensia", "malvavicus"):
                            trigger_burst = True
            except Exception as e:
                logger.error(f"flower_detector 推理失败: {e}")

        elapsed_ms = (time.time() - start) * 1000

        return DetectionResult(
            file_path=file_path,
            detections=detections,
            inference_time_ms=round(elapsed_ms, 2),
            model_name="yolov8n",
            trigger_burst=trigger_burst
        )

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def status(self) -> Dict[str, Any]:
        """获取推理状态"""
        uptime = 0.0
        if self._start_time:
            uptime = time.time() - self._start_time

        return {
            "is_running": self._is_running,
            "use_mock": self.use_mock,
            "total_processed": self._total_processed,
            "total_detections": self._total_detections,
            "total_bursts_triggered": self._total_bursts_triggered,
            "errors": self._errors,
            "uptime_seconds": round(uptime, 2),
            "queue_size": self.inference_queue.qsize()
        }

    @property
    def latest_result(self) -> Optional[DetectionResult]:
        return self._last_result


# 全局 InferenceRunner 实例
_inference_runner: Optional[InferenceRunner] = None


def get_inference_runner() -> Optional[InferenceRunner]:
    """获取全局 InferenceRunner 实例"""
    return _inference_runner


def set_inference_runner(runner: InferenceRunner) -> None:
    """设置全局 InferenceRunner 实例"""
    global _inference_runner
    _inference_runner = runner
