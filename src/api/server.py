"""
FastAPI 应用入口
"""
import os
import yaml
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from ..config import DeviceConfig
from ..utils.logger import setup_logging, get_logger
from .routes_health import router as health_router
from .routes_camera import router as camera_router, init_camera_controller, close_camera_controller
from .routes_profile import router as profile_router
from .routes_capture import router as capture_router
from .routes_cam_b import router as cam_b_router
from .routes_inference import router as inference_router
from ..store.db import init_db, close_db_connection
from ..pipeline.capture_loop import get_capture_loop
from ..pipeline.burst_coordinator import BurstCoordinator, set_burst_coordinator, get_burst_coordinator
from ..inference.runner import InferenceRunner, set_inference_runner, get_inference_runner
from ..camera.cam_b import create_cam_b

load_dotenv()

logger = get_logger(__name__)

# 全局 Cam-B 引用（用于 shutdown 关闭）
_cam_b = None


def load_config(config_path: str = "configs/device.yaml") -> DeviceConfig:
    """加载并校验配置文件，返回 DeviceConfig 对象"""
    path = Path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return DeviceConfig(**raw)
    return DeviceConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _cam_b

    config = load_config()
    setup_logging(
        log_file=config.logging.file_path,
        level=config.logging.level,
        format_type=config.logging.format,
    )

    logger.info("AgriCam API 服务启动", extra={"extra_data": {"version": "0.2.0"}})

    app.state.config = config

    # 初始化数据库
    init_db(config.storage.db_path)

    # 初始化相机控制器
    # 开发环境使用 mock，生产环境设置 USE_MOCK_CAMERA=false
    use_mock = os.getenv("USE_MOCK_CAMERA", "true").lower() == "true"
    init_camera_controller(use_mock=use_mock)

    # 初始化 Cam-B
    cam_b_cfg = config.camera.cam_b
    _cam_b = create_cam_b(
        use_mock=use_mock,
        resolution=tuple(cam_b_cfg.resolution),
        burst_count=cam_b_cfg.burst_count,
        burst_interval_ms=cam_b_cfg.burst_interval_ms,
    )
    _cam_b.initialize()
    _cam_b.start()
    logger.info(f"Cam-B 已初始化: mock={use_mock}")

    # 初始化 BurstCoordinator
    coordinator = BurstCoordinator(cam_b=_cam_b)
    set_burst_coordinator(coordinator)
    logger.info("BurstCoordinator 已初始化")

    # 初始化 InferenceRunner
    capture_loop = get_capture_loop()
    inference_dict = config.inference.model_dump(exclude_none=True)
    runner = InferenceRunner(
        inference_queue=capture_loop.inference_queue,
        config=inference_dict,
        use_mock=use_mock,
        burst_callback=coordinator.on_flower_detected
    )
    set_inference_runner(runner)
    logger.info("InferenceRunner 已初始化")

    yield

    # === Shutdown ===

    # 停止推理
    runner = get_inference_runner()
    if runner and runner.is_running:
        runner.stop()
        logger.info("InferenceRunner 已停止")

    # 停止采集循环
    capture_loop = get_capture_loop()
    if capture_loop.is_running:
        capture_loop.stop()

    # 关闭 Cam-B
    if _cam_b:
        _cam_b.close()
        logger.info("Cam-B 已关闭")

    # 关闭相机控制器 (Cam-A)
    close_camera_controller()
    # 关闭数据库连接
    close_db_connection()
    logger.info("AgriCam API 服务关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="AgriCam API",
        description="Agricultural Camera System API for Raspberry Pi",
        version="0.2.0",
        lifespan=lifespan
    )

    app.include_router(health_router)
    app.include_router(camera_router)
    app.include_router(profile_router)
    app.include_router(capture_router)
    app.include_router(cam_b_router)
    app.include_router(inference_router)

    return app


app = create_app()


def main():
    """命令行入口点"""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=True
    )


if __name__ == "__main__":
    main()
