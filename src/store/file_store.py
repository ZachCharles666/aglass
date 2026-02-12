"""
文件存储模块
双写到 JSON 文件和 SQLite
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from .db import get_db_connection, DEFAULT_DB_PATH
from ..utils.logger import get_logger
from ..utils.time_id import generate_time_id

logger = get_logger(__name__)


class ImageMetadata:
    """图片元数据"""

    def __init__(
        self,
        image_id: str,
        profile_id: str,
        camera_id: str,
        ts: str,
        distance_bucket: str,
        focus_state: str,
        quality_score: float,
        file_path: str,
        metadata_path: Optional[str] = None
    ):
        self.image_id = image_id
        self.profile_id = profile_id
        self.camera_id = camera_id
        self.ts = ts
        self.distance_bucket = distance_bucket
        self.focus_state = focus_state
        self.quality_score = quality_score
        self.file_path = file_path
        self.metadata_path = metadata_path

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "profile_id": self.profile_id,
            "camera_id": self.camera_id,
            "ts": self.ts,
            "distance_bucket": self.distance_bucket,
            "focus_state": self.focus_state,
            "quality_score": self.quality_score,
            "file_path": self.file_path,
            "metadata_path": self.metadata_path
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImageMetadata":
        return cls(**data)


class FileStore:
    """文件存储管理器"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, base_path: str = "data/images"):
        self.db_path = db_path
        self.base_path = Path(base_path)

    @property
    def conn(self):
        return get_db_connection(self.db_path)

    def get_image_dir(self, date: Optional[datetime] = None) -> Path:
        """
        获取图片存储目录（按日期组织）

        Args:
            date: 日期，默认为今天

        Returns:
            Path: 图片目录路径
        """
        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y-%m-%d")
        img_dir = self.base_path / date_str
        img_dir.mkdir(parents=True, exist_ok=True)

        return img_dir

    def save_image_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        保存图片元数据（双写到 JSON 和 SQLite）

        Args:
            metadata: 元数据字典，必须包含：
                - image_id
                - profile_id
                - camera_id
                - ts
                - distance_bucket
                - focus_state
                - quality_score
                - file_path

        Returns:
            bool: 是否保存成功
        """
        try:
            # 1. 保存 JSON 文件
            file_path = Path(metadata["file_path"])
            json_path = file_path.with_suffix(".json")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            metadata["metadata_path"] = str(json_path)

            # 2. 保存到 SQLite
            self.insert_image(metadata)

            logger.debug(f"元数据保存成功: {metadata['image_id']}")
            return True

        except Exception as e:
            logger.error(f"保存元数据失败: {e}")
            return False

    def insert_image(self, metadata: Dict[str, Any]) -> bool:
        """
        插入图片记录到数据库

        Args:
            metadata: 元数据字典

        Returns:
            bool: 是否插入成功
        """
        try:
            self.conn.execute("""
                INSERT INTO images
                (image_id, profile_id, camera_id, ts, distance_bucket,
                 focus_state, quality_score, file_path, metadata_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata["image_id"],
                metadata.get("profile_id", "unknown"),
                metadata["camera_id"],
                metadata["ts"],
                metadata.get("distance_bucket", "unknown"),
                metadata.get("focus_state", "unknown"),
                metadata.get("quality_score", 0.0),
                metadata["file_path"],
                metadata.get("metadata_path")
            ))
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"插入图片记录失败: {e}")
            self.conn.rollback()
            return False

    def query_images_since(self, minutes_ago: int = 30) -> List[Dict[str, Any]]:
        """
        查询指定时间范围内的图片

        Args:
            minutes_ago: 往前查询的分钟数

        Returns:
            List[Dict]: 图片元数据列表
        """
        try:
            # 计算起始时间
            since_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            since_str = since_time.isoformat()

            cursor = self.conn.execute("""
                SELECT image_id, profile_id, camera_id, ts, distance_bucket,
                       focus_state, quality_score, file_path, metadata_path, created_at
                FROM images
                WHERE ts >= ?
                ORDER BY ts DESC
            """, (since_str,))

            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append({
                    "image_id": row[0],
                    "profile_id": row[1],
                    "camera_id": row[2],
                    "ts": row[3],
                    "distance_bucket": row[4],
                    "focus_state": row[5],
                    "quality_score": row[6],
                    "file_path": row[7],
                    "metadata_path": row[8],
                    "created_at": row[9]
                })

            return results

        except Exception as e:
            logger.error(f"查询图片失败: {e}")
            return []

    def count_images(self) -> int:
        """获取图片总数"""
        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM images")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"统计图片数量失败: {e}")
            return 0

    def get_latest_image(self) -> Optional[Dict[str, Any]]:
        """获取最新的一张图片"""
        try:
            cursor = self.conn.execute("""
                SELECT image_id, profile_id, camera_id, ts, distance_bucket,
                       focus_state, quality_score, file_path, metadata_path, created_at
                FROM images
                ORDER BY ts DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return {
                    "image_id": row[0],
                    "profile_id": row[1],
                    "camera_id": row[2],
                    "ts": row[3],
                    "distance_bucket": row[4],
                    "focus_state": row[5],
                    "quality_score": row[6],
                    "file_path": row[7],
                    "metadata_path": row[8],
                    "created_at": row[9]
                }
            return None

        except Exception as e:
            logger.error(f"获取最新图片失败: {e}")
            return None


# 全局 FileStore 实例
_file_store: Optional[FileStore] = None


def get_file_store(db_path: str = DEFAULT_DB_PATH) -> FileStore:
    """获取全局 FileStore 实例"""
    global _file_store

    if _file_store is None:
        _file_store = FileStore(db_path)

    return _file_store
