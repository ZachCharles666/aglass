"""
test_af_control.py — AFController + 单例 (9 tests)
"""
from src.camera.af_control import (
    AFController,
    get_af_controller,
    set_af_controller,
)
from src.camera.cam_a import MockCamA


class TestAFControllerInit:
    def test_init_with_camera(self, mock_cam_a):
        ctrl = AFController(camera=mock_cam_a)
        assert ctrl.is_initialized is True
        assert ctrl.camera is mock_cam_a

    def test_init_lazy(self):
        ctrl = AFController(use_mock=True)
        assert ctrl.is_initialized is False
        assert ctrl.initialize() is True
        assert ctrl.is_initialized is True

    def test_close(self, mock_cam_a):
        ctrl = AFController(camera=mock_cam_a)
        ctrl.close()
        assert ctrl.is_initialized is False
        assert ctrl.camera is None


class TestAFControllerAF:
    def test_trigger_one_shot(self, af_controller):
        success, dur, pos = af_controller.trigger_one_shot_af(timeout=3.0)
        assert success is True
        assert pos is not None

    def test_lock_focus(self, af_controller):
        pos = af_controller.lock_focus()
        assert pos == 5.0

    def test_unlock_focus(self, af_controller):
        af_controller.lock_focus()
        assert af_controller.unlock_focus() is True

    def test_get_af_state(self, af_controller):
        state = af_controller.get_af_state()
        assert "af_mode" in state
        assert "lens_position" in state

    def test_not_initialized_returns_error(self):
        ctrl = AFController(use_mock=True)
        success, _, _ = ctrl.trigger_one_shot_af()
        assert success is False


class TestAFControllerCapture:
    def test_capture_and_clarity(self, af_controller, tmp_path):
        fp = str(tmp_path / "cap.jpg")
        success, clarity = af_controller.capture_and_get_clarity(fp)
        assert success is True
        # MockCamera touch 创建的空文件，clarity 应为 0
        assert clarity == 0.0


class TestSingleton:
    def test_get_and_set(self):
        ctrl = AFController(use_mock=True)
        set_af_controller(ctrl)
        assert get_af_controller() is ctrl
