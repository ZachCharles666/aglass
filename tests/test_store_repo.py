"""
test_store_repo.py — ProfileRepository CRUD (9 tests)
"""
from src.store.models import FocusProfile, CameraConfig, DistancePolicy
from src.store.repo import ProfileRepository


def _make_profile(operator="tester", is_current=False, **kwargs):
    return FocusProfile(
        operator_id=operator,
        cam_a_config=CameraConfig(af_mode="locked", lens_position=5.0),
        distance_policy=DistancePolicy(),
        is_current=is_current,
        **kwargs,
    )


class TestSaveAndGet:
    def test_save_profile(self, profile_repo):
        p = _make_profile()
        assert profile_repo.save_profile(p) is True

    def test_get_by_id(self, profile_repo):
        p = _make_profile()
        profile_repo.save_profile(p)
        got = profile_repo.get_profile_by_id(p.profile_id)
        assert got is not None
        assert got.operator_id == "tester"

    def test_get_nonexistent(self, profile_repo):
        assert profile_repo.get_profile_by_id("no-such-id") is None


class TestCurrentProfile:
    def test_no_current_initially(self, profile_repo):
        assert profile_repo.get_current_profile() is None

    def test_set_current(self, profile_repo):
        p = _make_profile()
        profile_repo.save_profile(p)
        assert profile_repo.set_current_profile(p.profile_id) is True
        cur = profile_repo.get_current_profile()
        assert cur is not None
        assert cur.profile_id == p.profile_id

    def test_switch_current(self, profile_repo):
        p1 = _make_profile(operator="op1")
        p2 = _make_profile(operator="op2")
        profile_repo.save_profile(p1)
        profile_repo.save_profile(p2)
        profile_repo.set_current_profile(p1.profile_id)
        profile_repo.set_current_profile(p2.profile_id)
        cur = profile_repo.get_current_profile()
        assert cur.profile_id == p2.profile_id


class TestListAndDelete:
    def test_list_profiles(self, profile_repo):
        for i in range(3):
            profile_repo.save_profile(_make_profile(operator=f"op{i}"))
        profiles = profile_repo.list_profiles()
        assert len(profiles) == 3

    def test_count_profiles(self, profile_repo):
        assert profile_repo.count_profiles() == 0
        profile_repo.save_profile(_make_profile())
        assert profile_repo.count_profiles() == 1

    def test_delete_profile(self, profile_repo):
        p = _make_profile()
        profile_repo.save_profile(p)
        assert profile_repo.delete_profile(p.profile_id) is True
        assert profile_repo.get_profile_by_id(p.profile_id) is None
