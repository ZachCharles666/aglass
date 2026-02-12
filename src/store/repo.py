"""
数据访问层（Repository）
提供 Profile 的 CRUD 操作
"""
import json
from datetime import datetime, timezone
from typing import Optional, List

from .db import get_db_connection, DEFAULT_DB_PATH
from .models import FocusProfile, CameraConfig, DistancePolicy
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProfileRepository:
    """Profile 数据访问类"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        初始化 Repository

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path

    @property
    def conn(self):
        """获取数据库连接"""
        return get_db_connection(self.db_path)

    def save_profile(self, profile: FocusProfile) -> bool:
        """
        保存 Profile

        Args:
            profile: FocusProfile 实例

        Returns:
            bool: 是否保存成功
        """
        try:
            # 序列化嵌套对象
            cam_a_config_json = profile.cam_a_config.model_dump_json()
            distance_policy_json = profile.distance_policy.model_dump_json()

            # 格式化时间
            created_at_str = profile.created_at.isoformat()

            self.conn.execute("""
                INSERT INTO profiles
                (profile_id, operator_id, created_at, cam_a_config, distance_policy, notes, is_current)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.profile_id,
                profile.operator_id,
                created_at_str,
                cam_a_config_json,
                distance_policy_json,
                profile.notes,
                1 if profile.is_current else 0
            ))
            self.conn.commit()

            logger.info(f"Profile 保存成功: {profile.profile_id}")
            return True

        except Exception as e:
            logger.error(f"Profile 保存失败: {e}")
            self.conn.rollback()
            return False

    def get_profile_by_id(self, profile_id: str) -> Optional[FocusProfile]:
        """
        根据 ID 获取 Profile

        Args:
            profile_id: Profile ID

        Returns:
            FocusProfile 或 None
        """
        try:
            cursor = self.conn.execute(
                "SELECT * FROM profiles WHERE profile_id = ?",
                (profile_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_profile(row)
            return None

        except Exception as e:
            logger.error(f"获取 Profile 失败: {e}")
            return None

    def get_current_profile(self) -> Optional[FocusProfile]:
        """
        获取当前激活的 Profile

        Returns:
            FocusProfile 或 None
        """
        try:
            cursor = self.conn.execute(
                "SELECT * FROM profiles WHERE is_current = 1"
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_profile(row)
            return None

        except Exception as e:
            logger.error(f"获取当前 Profile 失败: {e}")
            return None

    def set_current_profile(self, profile_id: str) -> bool:
        """
        设置当前激活的 Profile

        Args:
            profile_id: Profile ID

        Returns:
            bool: 是否设置成功
        """
        try:
            # 先检查 profile 是否存在
            profile = self.get_profile_by_id(profile_id)
            if not profile:
                logger.warning(f"Profile 不存在: {profile_id}")
                return False

            # 清除旧的 current
            self.conn.execute("UPDATE profiles SET is_current = 0")

            # 设置新的 current
            self.conn.execute(
                "UPDATE profiles SET is_current = 1 WHERE profile_id = ?",
                (profile_id,)
            )
            self.conn.commit()

            logger.info(f"当前 Profile 已设置: {profile_id}")
            return True

        except Exception as e:
            logger.error(f"设置当前 Profile 失败: {e}")
            self.conn.rollback()
            return False

    def list_profiles(self, limit: int = 100, offset: int = 0) -> List[FocusProfile]:
        """
        列出所有 Profile

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            FocusProfile 列表
        """
        try:
            cursor = self.conn.execute(
                "SELECT * FROM profiles ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()

            return [self._row_to_profile(row) for row in rows]

        except Exception as e:
            logger.error(f"列出 Profile 失败: {e}")
            return []

    def count_profiles(self) -> int:
        """
        获取 Profile 总数

        Returns:
            int: Profile 数量
        """
        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM profiles")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取 Profile 数量失败: {e}")
            return 0

    def delete_profile(self, profile_id: str) -> bool:
        """
        删除 Profile

        Args:
            profile_id: Profile ID

        Returns:
            bool: 是否删除成功
        """
        try:
            self.conn.execute(
                "DELETE FROM profiles WHERE profile_id = ?",
                (profile_id,)
            )
            self.conn.commit()

            logger.info(f"Profile 已删除: {profile_id}")
            return True

        except Exception as e:
            logger.error(f"删除 Profile 失败: {e}")
            self.conn.rollback()
            return False

    def _row_to_profile(self, row: tuple) -> FocusProfile:
        """
        将数据库行转换为 FocusProfile 对象

        Args:
            row: 数据库行 (profile_id, operator_id, created_at, cam_a_config, distance_policy, notes, is_current)

        Returns:
            FocusProfile 实例
        """
        # 解析 JSON 字段
        cam_a_config = CameraConfig.model_validate_json(row[3])
        distance_policy = DistancePolicy.model_validate_json(row[4])

        # 解析时间
        created_at = datetime.fromisoformat(row[2])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return FocusProfile(
            profile_id=row[0],
            operator_id=row[1],
            created_at=created_at,
            cam_a_config=cam_a_config,
            distance_policy=distance_policy,
            notes=row[5],
            is_current=bool(row[6])
        )


# 全局 Repository 实例
_profile_repo: Optional[ProfileRepository] = None


def get_profile_repo(db_path: str = DEFAULT_DB_PATH) -> ProfileRepository:
    """
    获取全局 ProfileRepository 实例

    Args:
        db_path: 数据库路径

    Returns:
        ProfileRepository 实例
    """
    global _profile_repo

    if _profile_repo is None:
        _profile_repo = ProfileRepository(db_path)

    return _profile_repo
