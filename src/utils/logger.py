"""
JSON 格式日志模块
写入 data/logs/app.log
"""
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON 格式的日志 Formatter"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    log_file: str = "data/logs/app.log",
    level: str = "INFO",
    format_type: str = "json"
) -> None:
    """
    初始化日志系统

    Args:
        log_file: 日志文件路径
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 格式类型 ("json" 或 "text")
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    console_handler = logging.StreamHandler()

    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger

    Args:
        name: Logger 名称（通常使用 __name__）

    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """支持额外数据的 Logger 适配器"""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        if "extra_data" not in extra and self.extra:
            extra["extra_data"] = self.extra
            kwargs["extra"] = extra
        return msg, kwargs
