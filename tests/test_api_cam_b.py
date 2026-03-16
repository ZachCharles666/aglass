"""
test_api_cam_b.py — /camera/cam-b/* (4 tests)
"""
import pytest


class TestCamBEndpoints:
    @pytest.mark.asyncio
    async def test_cam_b_status(self, async_client):
        resp = await async_client.get("/camera/cam-b/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["camera_type"] == "mock"
        assert data["burst_count"] == 2  # 临时 config 中设置的

    @pytest.mark.asyncio
    async def test_manual_burst(self, async_client):
        resp = await async_client.post("/camera/cam-b/burst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["files"]) == 2  # burst_count=2

    @pytest.mark.asyncio
    async def test_burst_status(self, async_client):
        resp = await async_client.get("/camera/cam-b/burst/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_bursting" in data
        assert "total_bursts" in data

    @pytest.mark.asyncio
    async def test_burst_status_after_manual(self, async_client):
        await async_client.post("/camera/cam-b/burst")
        resp = await async_client.get("/camera/cam-b/burst/status")
        assert resp.status_code == 200
        data = resp.json()
        # manual burst 不走 coordinator，total_bursts 仍为 0
        assert data["total_bursts"] == 0
