import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_job_status_not_found(authorized_client: AsyncClient):
    import uuid
    dummy_id = str(uuid.uuid4())
    response = await authorized_client.get(f"/api/jobs/{dummy_id}")
    assert response.status_code == 404
