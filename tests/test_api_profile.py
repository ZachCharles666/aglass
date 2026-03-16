"""
test_api_profile.py — /profile/* (5 tests)
"""
import pytest


class TestProfileEndpoints:
    @pytest.mark.asyncio
    async def test_create_profile(self, async_client):
        resp = await async_client.post(
            "/profile/create",
            json={"operator_id": "test_op", "notes": "test run"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["operator_id"] == "test_op"
        assert data["is_current"] is True
        assert data["cam_a_config"]["af_mode"] == "locked"

    @pytest.mark.asyncio
    async def test_get_current_profile(self, async_client):
        # 先创建
        await async_client.post(
            "/profile/create",
            json={"operator_id": "op1"},
        )
        resp = await async_client.get("/profile/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["operator_id"] == "op1"

    @pytest.mark.asyncio
    async def test_list_profiles(self, async_client):
        await async_client.post("/profile/create", json={"operator_id": "a"})
        await async_client.post("/profile/create", json={"operator_id": "b"})
        resp = await async_client.get("/profile/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_profile_by_id(self, async_client):
        create_resp = await async_client.post(
            "/profile/create", json={"operator_id": "x"}
        )
        pid = create_resp.json()["profile_id"]
        resp = await async_client.get(f"/profile/{pid}")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == pid

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile_returns_404(self, async_client):
        resp = await async_client.get("/profile/no-such-id")
        assert resp.status_code == 404
