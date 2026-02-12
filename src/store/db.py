"""
SQLite 数据库初始化和管理
支持 WAL 模式，确保并发安全
"""
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from ..utils.logger import get_logger

logger = get_logger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = "data/profiles/profiles.db"

# 全局数据库连接
_db_connection: Optional[sqlite3.Connection] = None


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    初始化 SQLite 数据库

    Args:
        db_path: 数据库文件路径

    Returns:
        sqlite3.Connection: 数据库连接
    """
    # 确保目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)

    # 启用 WAL 模式（提高并发性能）
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # 创建 profiles 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            operator_id TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            cam_a_config TEXT NOT NULL,
            distance_policy TEXT NOT NULL,
            notes TEXT,
            is_current INTEGER DEFAULT 0
        )
    """)

    # 创建 images 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            image_id TEXT PRIMARY KEY,
            profile_id TEXT,
            camera_id TEXT NOT NULL,
            ts TIMESTAMP NOT NULL,
            distance_bucket TEXT DEFAULT 'unknown',
            focus_state TEXT,
            quality_score REAL,
            file_path TEXT NOT NULL,
            metadata_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(profile_id)
        )
    """)

    # 创建索引
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_profiles_is_current
        ON profiles(is_current)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_profiles_created_at
        ON profiles(created_at DESC)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_images_ts
        ON images(ts DESC)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_images_profile_id
        ON images(profile_id)
    """)

    conn.commit()

    logger.info(f"数据库初始化完成: {db_path}")
    return conn


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    获取数据库连接（单例模式）

    Args:
        db_path: 数据库文件路径

    Returns:
        sqlite3.Connection: 数据库连接
    """
    global _db_connection

    if _db_connection is None:
        _db_connection = init_db(db_path)

    return _db_connection


def close_db_connection() -> None:
    """关闭数据库连接"""
    global _db_connection

    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
        logger.info("数据库连接已关闭")


@contextmanager
def get_db_session(db_path: str = DEFAULT_DB_PATH):
    """
    获取数据库会话（上下文管理器）

    用法：
        with get_db_session() as conn:
            conn.execute(...)

    Args:
        db_path: 数据库文件路径

    Yields:
        sqlite3.Connection: 数据库连接
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    else:
        conn.commit()


def reset_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    重置数据库（删除所有数据）

    ⚠️ 警告：此操作不可逆

    Args:
        db_path: 数据库文件路径
    """
    close_db_connection()

    db_file = Path(db_path)
    if db_file.exists():
        db_file.unlink()
        logger.warning(f"数据库已删除: {db_path}")

    # WAL 相关文件
    wal_file = Path(f"{db_path}-wal")
    shm_file = Path(f"{db_path}-shm")
    if wal_file.exists():
        wal_file.unlink()
    if shm_file.exists():
        shm_file.unlink()

    # 重新初始化
    init_db(db_path)
