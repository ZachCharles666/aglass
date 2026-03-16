"""
核心 fixtures：单例重置、临时 DB、mock 相机、API client
"""
import os
import queue
import sqlite3
from pathlib import Path
from typing import Generator

import pytest

from src.store import db as db_mod
from src.store import file_store as fs_mod
from src.store import repo as repo_mod
from src.camera import af_control as af_mod
from src.inference import runner as runner_mod
from src.pipeline import capture_loop as cl_mod
from src.pipeline import burst_coordinator as bc_mod
from src.api import routes_camera as rc_mod


# ─── 单例重置 (autouse) ──────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后清理 8 个全局单例"""
    yield
    # teardown: 关闭 db 连接并置空所有单例
    if db_mod._db_connection is not None:
        try:
            db_mod._db_connection.close()
        except Exception:
            pass
    db_mod._db_connection = None
    fs_mod._file_store = None
    repo_mod._profile_repo = None
    af_mod._global_af_controller = None
    runner_mod._inference_runner = None
    cl_mod._capture_loop = None
    bc_mod._burst_coordinator = None
    rc_mod._af_controller = None


# ─── 数据库 fixtures ─────────────────────────────────────────

@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """返回临时 SQLite 数据库路径"""
    return str(tmp_path / "test.db")


@pytest.fixture
def db_conn(tmp_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """初始化临时 DB 并注入到全局单例，返回连接"""
    conn = db_mod.init_db(tmp_db_path)
    db_mod._db_connection = conn
    yield conn


# ─── 存储 fixtures ───────────────────────────────────────────

@pytest.fixture
def file_store(db_conn, tmp_path: Path):
    """FileStore，使用临时 DB 和临时 images 目录"""
    from src.store.file_store import FileStore
    store = FileStore(
        db_path=str(tmp_path / "test.db"),
        base_path=str(tmp_path / "images"),
    )
    fs_mod._file_store = store
    return store


@pytest.fixture
def profile_repo(db_conn, tmp_db_path: str):
    """ProfileRepository，使用临时 DB"""
    from src.store.repo import ProfileRepository
    repo = ProfileRepository(db_path=tmp_db_path)
    repo_mod._profile_repo = repo
    return repo


# ─── 相机 fixtures ───────────────────────────────────────────

@pytest.fixture
def mock_cam_a():
    """已启动的 MockCamA"""
    from src.camera.cam_a import MockCamA
    cam = MockCamA()
    cam.initialize()
    cam.start()
    yield cam
    cam.close()


@pytest.fixture
def mock_cam_b(tmp_path: Path):
    """已启动的 MockCamB (burst_count=3, interval=0)"""
    from src.camera.cam_b import MockCamB
    cam = MockCamB(burst_count=3, burst_interval_ms=0)
    cam.initialize()
    cam.start()
    yield cam
    cam.close()


@pytest.fixture
def af_controller(mock_cam_a):
    """AFController 包装 mock_cam_a"""
    from src.camera.af_control import AFController
    ctrl = AFController(camera=mock_cam_a)
    return ctrl


# ─── 管道 fixtures ───────────────────────────────────────────

@pytest.fixture
def inference_queue() -> queue.Queue:
    return queue.Queue(maxsize=50)


@pytest.fixture
def capture_loop(af_controller, file_store, inference_queue):
    """interval=0.05s 的快速循环"""
    from src.pipeline.capture_loop import CaptureLoop
    loop = CaptureLoop(
        af_controller=af_controller,
        file_store=file_store,
        interval_sec=0.05,
        inference_queue=inference_queue,
    )
    yield loop
    if loop.is_running:
        loop.stop()


@pytest.fixture
def burst_coordinator(mock_cam_b, file_store):
    """BurstCoordinator，使用 MockCamB + temp FileStore"""
    from src.pipeline.burst_coordinator import BurstCoordinator
    return BurstCoordinator(cam_b=mock_cam_b, file_store=file_store)


@pytest.fixture
def inference_runner(inference_queue, burst_coordinator):
    """mock 模式 InferenceRunner + burst_callback"""
    from src.inference.runner import InferenceRunner
    runner = InferenceRunner(
        inference_queue=inference_queue,
        config={},
        use_mock=True,
        burst_callback=burst_coordinator.on_flower_detected,
    )
    yield runner
    if runner.is_running:
        runner.stop()


# ─── API 集成测试 fixtures ───────────────────────────────────

@pytest.fixture
async def async_client(tmp_path: Path, monkeypatch):
    """httpx AsyncClient + ASGITransport，手动模拟 lifespan 初始化"""
    import yaml
    import httpx

    # 创建临时 configs/device.yaml
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    db_path = str(tmp_path / "api_test.db")
    config = {
        "camera": {
            "cam_a": {"resolution": [640, 480]},
            "cam_b": {
                "resolution": [640, 480],
                "burst_count": 2,
                "burst_interval_ms": 0,
            },
        },
        "storage": {"db_path": db_path},
        "logging": {
            "level": "WARNING",
            "file_path": str(tmp_path / "logs" / "test.log"),
            "format": "text",
        },
        "inference": {},
    }
    with open(config_dir / "device.yaml", "w") as f:
        yaml.dump(config, f)

    monkeypatch.setenv("USE_MOCK_CAMERA", "true")
    monkeypatch.chdir(tmp_path)

    # --- 手动初始化：ASGITransport 不触发 lifespan ---
    from src.store.db import init_db
    from src.api.routes_camera import init_camera_controller, close_camera_controller
    from src.camera.cam_b import create_cam_b
    from src.pipeline.burst_coordinator import BurstCoordinator
    from src.pipeline.capture_loop import get_capture_loop
    from src.inference.runner import InferenceRunner

    conn = init_db(db_path)
    db_mod._db_connection = conn

    init_camera_controller(use_mock=True)

    cam_b = create_cam_b(use_mock=True, burst_count=2, burst_interval_ms=0)
    cam_b.initialize()
    cam_b.start()

    coordinator = BurstCoordinator(cam_b=cam_b)
    bc_mod._burst_coordinator = coordinator

    capture_loop = get_capture_loop()
    runner = InferenceRunner(
        inference_queue=capture_loop.inference_queue,
        config={},
        use_mock=True,
        burst_callback=coordinator.on_flower_detected,
    )
    runner_mod._inference_runner = runner

    # --- 创建 app (无 lifespan 副作用) ---
    from src.api.server import create_app

    app = create_app()
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # --- 清理 ---
    if runner.is_running:
        runner.stop()
    if capture_loop.is_running:
        capture_loop.stop()
    cam_b.close()
    close_camera_controller()
