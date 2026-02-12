"""
FastAPI 应用入口
"""
import os
import yaml
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from ..utils.logger import setup_logging, get_logger
from .routes_health import router as health_router
from .routes_camera import router as camera_router, init_camera_controller, close_camera_controller
from .routes_profile import router as profile_router
from .routes_capture import router as capture_router
from ..store.db import init_db, close_db_connection
from ..pipeline.capture_loop import get_capture_loop

load_dotenv()

logger = get_logger(__name__)


def load_config(config_path: str = "configs/device.yaml") -> dict:
    """加载配置文件"""
    path = Path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    config = load_config()
    log_config = config.get("logging", {})
    setup_logging(
        log_file=log_config.get("file_path", "data/logs/app.log"),
        level=log_config.get("level", "INFO"),
        format_type=log_config.get("format", "json")
    )

    logger.info("AgriCam API 服务启动", extra={"extra_data": {"version": "0.1.0"}})

    app.state.config = config

    # 初始化数据库
    db_path = config.get("storage", {}).get("db_path", "data/profiles/profiles.db")
    init_db(db_path)

    # 初始化相机控制器
    # 开发环境使用 mock，生产环境设置 USE_MOCK_CAMERA=false
    use_mock = os.getenv("USE_MOCK_CAMERA", "true").lower() == "true"
    init_camera_controller(use_mock=use_mock)

    yield

    # 停止采集循环
    capture_loop = get_capture_loop()
    if capture_loop.is_running:
        capture_loop.stop()

    # 关闭相机控制器
    close_camera_controller()
    # 关闭数据库连接
    close_db_connection()
    logger.info("AgriCam API 服务关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="AgriCam API",
        description="Agricultural Camera System API for Raspberry Pi",
        version="0.1.0",
        lifespan=lifespan
    )

    app.include_router(health_router)
    app.include_router(camera_router)
    app.include_router(profile_router)
    app.include_router(capture_router)

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
