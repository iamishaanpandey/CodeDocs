import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_add_repository(client: AsyncClient, authorized_client: AsyncClient):
    response = await authorized_client.post("/api/repos/", json={"github_url": "https://github.com/encode/starlette"})
    assert response.status_code == 201
    data = response.json()
    assert data["github_repo_owner"] == "encode"
    assert data["github_repo_name"] == "starlette"
    assert data["scan_status"] == "pending"

@pytest.mark.asyncio
async def test_add_repository_unauthorized(client: AsyncClient):
    response = await client.post("/api/repos/", json={"github_url": "https://github.com/encode/starlette"})
    assert response.status_code == 401
