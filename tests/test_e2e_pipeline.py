"""
端到端集成测试
全 mock 模式跑完整链路：
CaptureLoop → inference_queue → InferenceRunner → (概率触发) BurstCoordinator → CamB burst
"""
import queue
import time
from pathlib import Path

import pytest

from src.store.db import init_db
from src.store.file_store import FileStore
from src.store.repo import ProfileRepository
from src.store.models import FocusProfile, CameraConfig, DistancePolicy
from src.camera.cam_a import MockCamA
from src.camera.cam_b import MockCamB
from src.camera.af_control import AFController
from src.pipeline.capture_loop import CaptureLoop
from src.pipeline.burst_coordinator import BurstCoordinator
from src.inference.runner import InferenceRunner


class TestE2EPipeline:
    """全链路集成测试（mock 模式）"""

    def test_full_pipeline(self, tmp_path: Path):
        """
        完整链路：
        1. 初始化 DB + FileStore + ProfileRepo
        2. MockCamA → AFController → one_shot_af → lock_focus
        3. FocusProfile → save → set_current
        4. MockCamB → BurstCoordinator
        5. CaptureLoop + InferenceRunner
        6. 启动 → sleep → 停止
        7. 断言各环节结果
        """
        # ── 1. 初始化 DB + FileStore + ProfileRepo ──
        db_path = str(tmp_path / "e2e.db")
        conn = init_db(db_path)

        file_store = FileStore(
            db_path=db_path,
            base_path=str(tmp_path / "images"),
        )
        profile_repo = ProfileRepository(db_path=db_path)

        # ── 2. MockCamA → AFController → AF 操作 ──
        cam_a = MockCamA()
        cam_a.initialize()
        cam_a.start()

        af_ctrl = AFController(camera=cam_a)

        # 执行 one-shot AF
        success, duration, lens_pos = cam_a.one_shot_af()
        assert success is True
        assert duration > 0

        # 锁定对焦
        cam_a.lock_focus()
        af_state = cam_a.get_af_state()
        assert af_state["af_mode"] == "locked"

        # ── 3. FocusProfile → save → set_current ──
        profile = FocusProfile(
            operator_id="e2e_test",
            cam_a_config=CameraConfig(
                af_mode="locked",
                lens_position=lens_pos,
                focus_distance_cm=45,
            ),
            distance_policy=DistancePolicy(),
            notes="E2E integration test profile",
        )
        profile_repo.save_profile(profile)
        profile_repo.set_current_profile(profile.profile_id)

        current = profile_repo.get_current_profile()
        assert current is not None
        assert current.is_current is True
        assert current.profile_id == profile.profile_id

        # ── 4. MockCamB → BurstCoordinator ──
        cam_b = MockCamB(burst_count=3, burst_interval_ms=0)
        cam_b.initialize()
        cam_b.start()

        coordinator = BurstCoordinator(cam_b=cam_b, file_store=file_store)

        # ── 5. CaptureLoop + InferenceRunner ──
        inf_queue = queue.Queue(maxsize=50)

        capture_loop = CaptureLoop(
            af_controller=af_ctrl,
            file_store=file_store,
            interval_sec=0.05,
            inference_queue=inf_queue,
        )

        runner = InferenceRunner(
            inference_queue=inf_queue,
            config={},
            use_mock=True,
            burst_callback=coordinator.on_flower_detected,
        )

        # ── 6. 启动 → sleep → 停止 ──
        capture_loop.start()
        runner.start()

        time.sleep(0.5)

        capture_loop.stop()
        runner.stop()

        # ── 7. 断言 ──

        # CaptureLoop 至少拍了 1 张
        assert capture_loop.total_count >= 1, (
            f"CaptureLoop should have captured at least 1 image, got {capture_loop.total_count}"
        )

        # InferenceRunner 至少处理了 1 张
        assert runner.status["total_processed"] >= 1, (
            f"InferenceRunner should have processed at least 1 image, got {runner.status['total_processed']}"
        )

        # FileStore 中有 cam_a 图片
        assert file_store.count_images() >= 1, (
            f"FileStore should have at least 1 image, got {file_store.count_images()}"
        )

        # inference_queue 被消费（qsize 应该比 total_count 小）
        remaining = inf_queue.qsize()
        consumed = capture_loop.total_count - remaining
        assert consumed >= 1, (
            f"At least 1 item should have been consumed from queue, "
            f"total_count={capture_loop.total_count}, remaining={remaining}"
        )

        # DB 中有 profile 且 is_current
        db_profile = profile_repo.get_current_profile()
        assert db_profile is not None
        assert db_profile.is_current is True

        # ── 清理 ──
        cam_b.close()
        cam_a.close()
        conn.close()
