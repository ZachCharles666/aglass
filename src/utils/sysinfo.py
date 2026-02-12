"""
系统信息读取模块
读取 CPU/RAM/温度/存储空间
"""
import os
import platform
from pathlib import Path
from typing import Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_cpu_usage() -> float:
    """
    获取 CPU 使用率

    Returns:
        float: CPU 使用率百分比 (0-100)
    """
    if PSUTIL_AVAILABLE:
        return psutil.cpu_percent(interval=0.1)
    return -1.0


def get_memory_info() -> dict:
    """
    获取内存使用信息

    Returns:
        dict: 包含 total_mb, used_mb, available_mb, percent 的字典
    """
    if PSUTIL_AVAILABLE:
        mem = psutil.virtual_memory()
        return {
            "total_mb": round(mem.total / (1024 * 1024), 2),
            "used_mb": round(mem.used / (1024 * 1024), 2),
            "available_mb": round(mem.available / (1024 * 1024), 2),
            "percent": mem.percent
        }
    return {
        "total_mb": -1,
        "used_mb": -1,
        "available_mb": -1,
        "percent": -1
    }


def get_cpu_temperature() -> Optional[float]:
    """
    获取 CPU 温度（仅适用于树莓派）

    Returns:
        float: CPU 温度（摄氏度），如果无法读取则返回 None
    """
    temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_file.exists():
        try:
            with open(temp_file) as f:
                temp = int(f.read().strip()) / 1000.0
                return round(temp, 1)
        except (IOError, ValueError):
            pass

    if PSUTIL_AVAILABLE:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return round(entries[0].current, 1)
        except Exception:
            pass

    return None


def get_disk_usage(path: str = "/") -> dict:
    """
    获取磁盘使用信息

    Args:
        path: 要检查的路径

    Returns:
        dict: 包含 total_gb, used_gb, free_gb, percent 的字典
    """
    if PSUTIL_AVAILABLE:
        usage = psutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "percent": usage.percent
        }
    return {
        "total_gb": -1,
        "used_gb": -1,
        "free_gb": -1,
        "percent": -1
    }


def get_system_info() -> dict:
    """
    获取完整的系统信息

    Returns:
        dict: 包含 cpu, memory, temperature, disk, platform 的系统信息
    """
    return {
        "cpu": {
            "usage_percent": get_cpu_usage(),
            "count": os.cpu_count() or 0
        },
        "memory": get_memory_info(),
        "temperature": {
            "cpu_celsius": get_cpu_temperature()
        },
        "disk": get_disk_usage("/"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version()
        }
    }
