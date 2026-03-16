"""
test_store_models.py — Pydantic 存储模型 (5 tests)
"""
from datetime import datetime, timezone

from src.store.models import (
    CameraConfig,
    DistancePolicy,
    FocusProfile,
    ProfileCreateRequest,
    ProfileListResponse,
)


class TestCameraConfig:
    def test_defaults(self):
        cfg = CameraConfig()
        assert cfg.af_mode == "auto"
        assert cfg.lens_position is None
        assert cfg.focus_distance_cm is None

    def test_with_values(self):
        cfg = CameraConfig(af_mode="locked", lens_position=5.2, focus_distance_cm=45)
        assert cfg.af_mode == "locked"
        assert cfg.lens_position == 5.2


class TestDistancePolicy:
    def test_default_ranges(self):
        dp = DistancePolicy()
        assert dp.near == [40, 52]
        assert dp.mid == [52, 85]
        assert dp.far == [85, 300]


class TestFocusProfile:
    def test_auto_generated_fields(self):
        p = FocusProfile(
            operator_id="tester",
            cam_a_config=CameraConfig(),
        )
        assert p.profile_id  # UUID auto-generated
        assert isinstance(p.created_at, datetime)
        assert p.is_current is False

    def test_json_round_trip(self):
        p = FocusProfile(
            operator_id="tester",
            cam_a_config=CameraConfig(af_mode="locked", lens_position=5.0),
            notes="hello",
        )
        json_str = p.model_dump_json()
        p2 = FocusProfile.model_validate_json(json_str)
        assert p2.operator_id == "tester"
        assert p2.cam_a_config.lens_position == 5.0
        assert p2.notes == "hello"


class TestProfileCreateRequest:
    def test_defaults(self):
        req = ProfileCreateRequest(operator_id="op1")
        assert req.focus_distance_cm == 45
        assert req.notes is None
