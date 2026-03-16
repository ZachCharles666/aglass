"""
test_utils.py — time_id + sysinfo (7 tests)
"""
import re
from datetime import datetime, timezone

from src.utils.time_id import (
    get_iso_timestamp,
    generate_time_id,
    generate_uuid,
    parse_timestamp,
)
from src.utils.sysinfo import (
    get_cpu_usage,
    get_memory_info,
    get_disk_usage,
    get_system_info,
)


# ─── time_id ──────────────────────────────────────────────────

class TestGetIsoTimestamp:
    def test_returns_iso_string(self):
        ts = get_iso_timestamp()
        # 能被 fromisoformat 解析
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None

    def test_utc_timezone(self):
        ts = get_iso_timestamp()
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo == timezone.utc


class TestGenerateTimeId:
    def test_with_prefix(self):
        tid = generate_time_id("img")
        assert tid.startswith("img_")
        # 格式: img_YYYYMMDDTHHMMSS_6hex
        parts = tid.split("_")
        assert len(parts) == 3
        assert len(parts[2]) == 6

    def test_without_prefix(self):
        tid = generate_time_id()
        # 格式: YYYYMMDDTHHMMSS_6hex
        parts = tid.split("_")
        assert len(parts) == 2

    def test_uniqueness(self):
        ids = {generate_time_id("x") for _ in range(100)}
        assert len(ids) == 100


class TestGenerateUuid:
    def test_format(self):
        uid = generate_uuid()
        # UUID4: 8-4-4-4-12
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            uid,
        )


class TestParseTimestamp:
    def test_round_trip(self):
        ts = get_iso_timestamp()
        dt = parse_timestamp(ts)
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None


# ─── sysinfo ──────────────────────────────────────────────────

class TestSysinfo:
    def test_cpu_usage_returns_float(self):
        val = get_cpu_usage()
        assert isinstance(val, float)

    def test_memory_info_keys(self):
        info = get_memory_info()
        assert set(info.keys()) == {"total_mb", "used_mb", "available_mb", "percent"}

    def test_disk_usage_keys(self):
        info = get_disk_usage("/")
        assert set(info.keys()) == {"total_gb", "used_gb", "free_gb", "percent"}

    def test_system_info_structure(self):
        info = get_system_info()
        assert "cpu" in info
        assert "memory" in info
        assert "disk" in info
        assert "platform" in info
        assert "temperature" in info
        assert info["platform"]["system"]  # non-empty string
