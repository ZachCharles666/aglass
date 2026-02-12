"""
时间戳 ID 生成模块
生成 ISO 8601 格式的时间戳和唯一标识符
"""
import uuid
from datetime import datetime, timezone


def get_iso_timestamp() -> str:
    """
    获取当前时间的 ISO 8601 格式时间戳

    Returns:
        str: ISO 8601 格式时间戳，例如 "2024-01-15T10:30:45.123456Z"
    """
    return datetime.now(timezone.utc).isoformat()


def generate_time_id(prefix: str = "") -> str:
    """
    生成基于时间戳的唯一标识符

    Args:
        prefix: 可选的前缀字符串

    Returns:
        str: 格式为 "{prefix}_{timestamp}_{short_uuid}" 的唯一标识符
             例如 "img_20240115T103045_a1b2c3"
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]

    if prefix:
        return f"{prefix}_{ts}_{short_uuid}"
    return f"{ts}_{short_uuid}"


def generate_uuid() -> str:
    """
    生成标准 UUID

    Returns:
        str: UUID 字符串
    """
    return str(uuid.uuid4())


def parse_timestamp(iso_str: str) -> datetime:
    """
    解析 ISO 8601 格式时间戳

    Args:
        iso_str: ISO 8601 格式时间戳字符串

    Returns:
        datetime: 解析后的 datetime 对象
    """
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
