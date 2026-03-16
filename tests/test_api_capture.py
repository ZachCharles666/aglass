"""
test_api_capture.py — /capture/* (5 tests)
"""
import pytest


class TestCaptureEndpoints:
    @pytest.mark.asyncio
    async def test_capture_status(self, async_client):
        resp = await async_client.get("/capture/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_running"] is False
        assert data["total_count"] == 0

    @pytest.mark.asyncio
    async def test_start_capture(self, async_client):
        resp = await async_client.post(
            "/capture/start",
            json={"interval_sec": 0.1},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 清理
        await async_client.post("/capture/stop")

    @pytest.mark.asyncio
    async def test_stop_when_not_running_returns_400(self, async_client):
        resp = await async_client.post("/capture/stop")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_capture_summary(self, async_client):
        resp = await async_client.get("/capture/summary?minutes=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_count" in data
        assert "average_quality" in data

    @pytest.mark.asyncio
    async def test_capture_latest(self, async_client):
        resp = await async_client.get("/capture/latest")
        assert resp.status_code == 200
        data = resp.json()
        # 初始无数据
        assert "success" in data
