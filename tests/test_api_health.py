"""
test_api_health.py — GET /health (3 tests)
"""
import pytest


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_structure(self, async_client):
        resp = await async_client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"
        assert "system" in data
        assert "cameras" in data
        assert "queue_sizes" in data

    @pytest.mark.asyncio
    async def test_health_system_info(self, async_client):
        data = (await async_client.get("/health")).json()
        sys_info = data["system"]
        assert "cpu" in sys_info
        assert "memory" in sys_info
        assert "disk" in sys_info
        assert "platform" in sys_info
