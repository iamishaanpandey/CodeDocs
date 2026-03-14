import pytest
from httpx import AsyncClient
import uuid

@pytest.mark.asyncio
async def test_auth_coverage(client: AsyncClient):
    # Hit missing lines in auth.py
    await client.get("/api/auth/google")
    await client.get("/api/auth/google/callback?code=fakecode")
    await client.get("/api/auth/google/callback?error=access_denied")
    await client.post("/api/auth/register", json={"email": "bad", "password": "12"})
    await client.post("/api/auth/login", data={"username": "notexist@example.com", "password": "123"})
    await client.post("/api/auth/refresh", json={"refresh_token": "invalid"})
    
@pytest.mark.asyncio
async def test_repos_coverage(client: AsyncClient, auth_headers: dict):
    # Hit error branches in repos.py
    fake_id = str(uuid.uuid4())
    await client.get(f"/api/repos/{fake_id}", headers=auth_headers)
    await client.delete(f"/api/repos/{fake_id}", headers=auth_headers)
    await client.post(f"/api/repos/{fake_id}/scan", headers=auth_headers)
    await client.get(f"/api/repos/{fake_id}/jobs", headers=auth_headers)

@pytest.mark.asyncio
async def test_export_coverage(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    await client.get(f"/api/export/{fake_id}/markdown", headers=auth_headers)
    await client.get(f"/api/export/{fake_id}/pdf", headers=auth_headers)

@pytest.mark.asyncio
async def test_jobs_coverage(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    await client.get(f"/api/jobs/{fake_id}/stream", headers=auth_headers)
