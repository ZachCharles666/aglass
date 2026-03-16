"""
test_api_camera.py — /camera/cam-a/* (5 tests)
"""
import pytest


class TestCamAEndpoints:
    @pytest.mark.asyncio
    async def test_af_one_shot(self, async_client):
        resp = await async_client.post("/camera/cam-a/af/one-shot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["lens_position"] is not None

    @pytest.mark.asyncio
    async def test_af_lock(self, async_client):
        resp = await async_client.post("/camera/cam-a/af/lock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["locked_position"] is not None

    @pytest.mark.asyncio
    async def test_af_unlock(self, async_client):
        # 先 lock 再 unlock
        await async_client.post("/camera/cam-a/af/lock")
        resp = await async_client.post("/camera/cam-a/af/unlock")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_af_state(self, async_client):
        resp = await async_client.get("/camera/cam-a/af/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "af_mode" in data
        assert "lens_position" in data

    @pytest.mark.asyncio
    async def test_cam_a_status(self, async_client):
        resp = await async_client.get("/camera/cam-a/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "initialized" in data
        assert "af_state" in data
