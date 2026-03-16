"""
test_store_db.py — SQLite WAL 初始化 + schema (7 tests)
"""
import sqlite3
from pathlib import Path

from src.store.db import (
    init_db,
    get_db_connection,
    close_db_connection,
    get_db_session,
    reset_db,
)
from src.store import db as db_mod


class TestInitDb:
    def test_creates_file(self, tmp_path):
        db_path = str(tmp_path / "init_test.db")
        conn = init_db(db_path)
        assert Path(db_path).exists()
        conn.close()

    def test_wal_mode(self, tmp_path):
        db_path = str(tmp_path / "wal.db")
        conn = init_db(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_profiles_table_exists(self, db_conn):
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
        )
        assert cursor.fetchone() is not None

    def test_images_table_exists(self, db_conn):
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='images'"
        )
        assert cursor.fetchone() is not None

    def test_indexes_created(self, db_conn):
        cursor = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        names = {row[0] for row in cursor.fetchall()}
        assert "idx_profiles_is_current" in names
        assert "idx_images_ts" in names


class TestGetDbConnection:
    def test_singleton(self, tmp_db_path):
        conn1 = get_db_connection(tmp_db_path)
        conn2 = get_db_connection(tmp_db_path)
        assert conn1 is conn2

    def test_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "sub" / "dir" / "deep.db")
        conn = get_db_connection(db_path)
        assert Path(db_path).exists()


class TestGetDbSession:
    def test_context_manager_commit(self, tmp_db_path):
        # 确保单例已初始化
        get_db_connection(tmp_db_path)
        with get_db_session(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO profiles (profile_id, operator_id, created_at, cam_a_config, distance_policy) "
                "VALUES (?, ?, ?, ?, ?)",
                ("p1", "op1", "2024-01-01T00:00:00", "{}", "{}"),
            )
        # 验证已提交
        conn2 = get_db_connection(tmp_db_path)
        row = conn2.execute("SELECT * FROM profiles WHERE profile_id='p1'").fetchone()
        assert row is not None


class TestResetDb:
    def test_clears_data(self, tmp_db_path):
        conn = init_db(tmp_db_path)
        db_mod._db_connection = conn
        conn.execute(
            "INSERT INTO profiles (profile_id, operator_id, created_at, cam_a_config, distance_policy) "
            "VALUES (?, ?, ?, ?, ?)",
            ("p1", "op1", "2024-01-01T00:00:00", "{}", "{}"),
        )
        conn.commit()
        # reset 后数据应消失
        reset_db(tmp_db_path)
        new_conn = get_db_connection(tmp_db_path)
        count = new_conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        assert count == 0
