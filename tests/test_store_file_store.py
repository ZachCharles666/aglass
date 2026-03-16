"""
test_store_file_store.py — FileStore 双写 + 查询 (9 tests)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from src.store.file_store import FileStore, ImageMetadata
from src.utils.time_id import get_iso_timestamp


class TestImageMetadata:
    def test_to_dict(self):
        m = ImageMetadata(
            image_id="img_001",
            profile_id="p1",
            camera_id="cam_a",
            ts="2024-01-01T00:00:00",
            distance_bucket="near",
            focus_state="locked",
            quality_score=120.5,
            file_path="/tmp/img.jpg",
        )
        d = m.to_dict()
        assert d["image_id"] == "img_001"
        assert d["quality_score"] == 120.5

    def test_from_dict(self):
        data = {
            "image_id": "i2",
            "profile_id": "p2",
            "camera_id": "cam_b",
            "ts": "2024-01-01",
            "distance_bucket": "far",
            "focus_state": "auto",
            "quality_score": 50.0,
            "file_path": "/x.jpg",
        }
        m = ImageMetadata.from_dict(data)
        assert m.camera_id == "cam_b"


class TestFileStoreImageDir:
    def test_creates_date_dir(self, file_store, tmp_path):
        d = datetime(2024, 6, 15, tzinfo=timezone.utc)
        img_dir = file_store.get_image_dir(d)
        assert img_dir.exists()
        assert "2024-06-15" in str(img_dir)

    def test_default_today(self, file_store):
        img_dir = file_store.get_image_dir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert today in str(img_dir)


class TestFileStoreSave:
    def _make_metadata(self, file_store, tmp_path, image_id="img_001"):
        img_dir = file_store.get_image_dir()
        file_path = str(img_dir / f"{image_id}.jpg")
        Path(file_path).touch()
        return {
            "image_id": image_id,
            "profile_id": "p1",
            "camera_id": "cam_a",
            "ts": get_iso_timestamp(),
            "distance_bucket": "near",
            "focus_state": "locked",
            "quality_score": 100.0,
            "file_path": file_path,
        }

    def test_save_creates_json(self, file_store, tmp_path):
        meta = self._make_metadata(file_store, tmp_path)
        ok = file_store.save_image_metadata(meta)
        assert ok is True
        json_path = Path(meta["file_path"]).with_suffix(".json")
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["image_id"] == "img_001"

    def test_save_inserts_db(self, file_store, tmp_path):
        meta = self._make_metadata(file_store, tmp_path, "img_002")
        file_store.save_image_metadata(meta)
        count = file_store.count_images()
        assert count >= 1

    def test_count_images(self, file_store, tmp_path):
        assert file_store.count_images() == 0
        meta = self._make_metadata(file_store, tmp_path, "img_c1")
        file_store.save_image_metadata(meta)
        assert file_store.count_images() == 1

    def test_get_latest_image(self, file_store, tmp_path):
        meta = self._make_metadata(file_store, tmp_path, "img_lat")
        file_store.save_image_metadata(meta)
        latest = file_store.get_latest_image()
        assert latest is not None
        assert latest["image_id"] == "img_lat"

    def test_query_images_since(self, file_store, tmp_path):
        meta = self._make_metadata(file_store, tmp_path, "img_q1")
        file_store.save_image_metadata(meta)
        results = file_store.query_images_since(minutes_ago=5)
        assert len(results) >= 1
        assert results[0]["image_id"] == "img_q1"
