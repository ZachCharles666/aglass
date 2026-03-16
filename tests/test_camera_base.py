"""
test_camera_base.py — MockCamera 基类 (8 tests)
"""
from pathlib import Path

from src.camera.cam_base import MockCamera


class TestMockCameraLifecycle:
    def test_init_state(self):
        cam = MockCamera()
        assert cam.is_initialized is False
        assert cam.is_started is False
        assert cam.camera_id == 0

    def test_initialize(self):
        cam = MockCamera()
        assert cam.initialize() is True
        assert cam.is_initialized is True

    def test_start_auto_initializes(self):
        cam = MockCamera()
        assert cam.start() is True
        assert cam.is_initialized is True
        assert cam.is_started is True

    def test_stop(self):
        cam = MockCamera()
        cam.start()
        cam.stop()
        assert cam.is_started is False
        assert cam.is_initialized is True  # close() 才会重置

    def test_close(self):
        cam = MockCamera()
        cam.start()
        cam.close()
        assert cam.is_started is False
        assert cam.is_initialized is False


class TestMockCameraCapture:
    def test_capture_creates_file(self, tmp_path):
        cam = MockCamera()
        cam.start()
        fp = str(tmp_path / "test.jpg")
        assert cam.capture(fp) is True
        assert Path(fp).exists()

    def test_capture_creates_parent_dirs(self, tmp_path):
        cam = MockCamera()
        cam.start()
        fp = str(tmp_path / "sub" / "dir" / "img.jpg")
        assert cam.capture(fp) is True
        assert Path(fp).exists()


class TestMockCameraMetadata:
    def test_default_metadata(self):
        cam = MockCamera()
        meta = cam.get_metadata()
        assert "LensPosition" in meta
        assert "AfState" in meta
        assert meta["LensPosition"] == 5.0

    def test_set_mock_values(self):
        cam = MockCamera()
        cam.set_mock_lens_position(10.0)
        cam.set_mock_af_state("Scanning")
        meta = cam.get_metadata()
        assert meta["LensPosition"] == 10.0
        assert meta["AfState"] == "Scanning"


class TestContextManager:
    def test_context_manager(self):
        with MockCamera() as cam:
            assert cam.is_started is True
        assert cam.is_started is False
        assert cam.is_initialized is False
