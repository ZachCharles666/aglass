"""
test_cam_b.py — MockCamB + burst + 工厂 (7 tests)
"""
from pathlib import Path

from src.camera.cam_b import MockCamB, create_cam_b


class TestMockCamBLifecycle:
    def test_identifier(self):
        cam = MockCamB()
        assert cam.identifier == "imx477_mock"

    def test_resolution(self):
        cam = MockCamB(resolution=(1920, 1080))
        assert cam.resolution == (1920, 1080)

    def test_default_burst_params(self):
        cam = MockCamB()
        assert cam.burst_count == 5
        assert cam.burst_interval_ms == 150


class TestMockCamBBurst:
    def test_burst_capture_count(self, mock_cam_b, tmp_path):
        prefix = str(tmp_path / "burst_test")
        files = mock_cam_b.burst_capture(prefix)
        assert len(files) == 3  # burst_count=3 from fixture

    def test_burst_files_exist(self, mock_cam_b, tmp_path):
        prefix = str(tmp_path / "burst_exist")
        files = mock_cam_b.burst_capture(prefix)
        for f in files:
            assert Path(f).exists()

    def test_burst_file_naming(self, mock_cam_b, tmp_path):
        prefix = str(tmp_path / "b")
        files = mock_cam_b.burst_capture(prefix)
        for i, f in enumerate(files):
            assert f.endswith(f"_{i}.jpg")


class TestCreateCamB:
    def test_factory_mock(self):
        cam = create_cam_b(use_mock=True)
        assert isinstance(cam, MockCamB)

    def test_factory_with_kwargs(self):
        cam = create_cam_b(use_mock=True, burst_count=10)
        assert isinstance(cam, MockCamB)
        assert cam.burst_count == 10
