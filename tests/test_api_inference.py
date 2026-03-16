"""
test_api_inference.py — /inference/* (5 tests)
"""
import pytest


class TestInferenceEndpoints:
    @pytest.mark.asyncio
    async def test_inference_status(self, async_client):
        resp = await async_client.get("/inference/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_running"] is False
        assert data["use_mock"] is True

    @pytest.mark.asyncio
    async def test_inference_latest_no_result(self, async_client):
        resp = await async_client.get("/inference/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_start_inference(self, async_client):
        resp = await async_client.post("/inference/start")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # 停止
        await async_client.post("/inference/stop")

    @pytest.mark.asyncio
    async def test_double_start_returns_400(self, async_client):
        await async_client.post("/inference/start")
        resp = await async_client.post("/inference/start")
        assert resp.status_code == 400
        await async_client.post("/inference/stop")

    @pytest.mark.asyncio
    async def test_stop_when_not_running_returns_400(self, async_client):
        resp = await async_client.post("/inference/stop")
        assert resp.status_code == 400
