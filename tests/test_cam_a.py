"""
test_cam_a.py — MockCamA + 工厂 + clarity (10 tests)
"""
import time
from pathlib import Path

import cv2
import numpy as np

from src.camera.cam_a import MockCamA, create_cam_a, get_clarity_score


class TestMockCamALifecycle:
    def test_identifier(self):
        cam = MockCamA()
        assert cam.identifier == "imx708_mock"

    def test_resolution(self):
        cam = MockCamA(resolution=(1280, 720))
        assert cam.resolution == (1280, 720)


class TestMockCamAAF:
    def test_one_shot_af_success(self, mock_cam_a):
        success, duration, lens_pos = mock_cam_a.one_shot_af(timeout=3.0)
        assert success is True
        assert lens_pos == 5.0
        assert duration > 0

    def test_one_shot_af_timeout(self):
        cam = MockCamA()
        cam.initialize()
        cam.start()
        cam._mock_af_duration = 10.0  # 超过 timeout
        success, duration, lens_pos = cam.one_shot_af(timeout=0.1)
        assert success is False
        assert lens_pos is None
        cam.close()

    def test_one_shot_af_not_started(self):
        cam = MockCamA()
        success, _, _ = cam.one_shot_af()
        assert success is False

    def test_lock_focus(self, mock_cam_a):
        pos = mock_cam_a.lock_focus()
        assert pos == 5.0
        assert mock_cam_a.af_mode == "locked"
        assert mock_cam_a.locked_lens_position == 5.0

    def test_unlock_focus(self, mock_cam_a):
        mock_cam_a.lock_focus()
        assert mock_cam_a.unlock_focus() is True
        assert mock_cam_a.af_mode == "auto"
        assert mock_cam_a.locked_lens_position is None

    def test_get_af_state(self, mock_cam_a):
        state = mock_cam_a.get_af_state()
        assert state["af_mode"] == "auto"
        assert state["af_state"] == "idle"
        mock_cam_a.lock_focus()
        state = mock_cam_a.get_af_state()
        assert state["af_mode"] == "locked"
        assert state["af_state"] == "focused"


class TestClarityScore:
    def test_laplacian_with_real_image(self, tmp_path):
        # 创建一个有纹理的灰度图
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        fp = str(tmp_path / "textured.jpg")
        cv2.imwrite(fp, img)
        score = get_clarity_score(fp, method="laplacian")
        assert score > 0

    def test_tenengrad(self, tmp_path):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        fp = str(tmp_path / "ten.jpg")
        cv2.imwrite(fp, img)
        score = get_clarity_score(fp, method="tenengrad")
        assert score > 0

    def test_invalid_image_returns_zero(self, tmp_path):
        fp = str(tmp_path / "empty.jpg")
        Path(fp).touch()  # 空文件，cv2 无法读取
        score = get_clarity_score(fp)
        assert score == 0.0


class TestCreateCamA:
    def test_factory_mock(self):
        cam = create_cam_a(use_mock=True)
        assert isinstance(cam, MockCamA)

    def test_factory_defaults_to_mock_on_mac(self):
        # 在非 RPi 上应该返回 MockCamA
        cam = create_cam_a(use_mock=False)
        assert isinstance(cam, MockCamA)  # PICAMERA2_AVAILABLE is False
