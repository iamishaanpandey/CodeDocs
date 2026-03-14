import pytest
from httpx import AsyncClient
import uuid
import hmac
import hashlib
import json
from app.core.config import settings

@pytest.mark.asyncio
async def test_all_missing_get_routes(authorized_client: AsyncClient):
    repo_id = str(uuid.uuid4())
    
    # 1. repos GET, DELETE, jobs
    resp = await authorized_client.get(f"/api/repos/{repo_id}")
    assert resp.status_code in (200, 404)
    resp = await authorized_client.get(f"/api/repos/{repo_id}/jobs")
    assert resp.status_code in (200, 404, 401)
    
    # 2. docs
    for r in ["overview", "functions", "diagrams", "entry-points", "external-interfaces", "file-tree"]:
        resp = await authorized_client.get(f"/api/docs/{repo_id}/{r}")
        assert resp.status_code in (200, 404)
        
    func_id = str(uuid.uuid4())
    resp = await authorized_client.get(f"/api/docs/{repo_id}/functions/{func_id}")
    assert resp.status_code in (200, 404)
    resp = await authorized_client.get(f"/api/docs/{repo_id}/blast-radius/{func_id}")
    assert resp.status_code == 200
    
    # 3. security
    for r in ["audit", "auth-map", "pii-flow"]:
        resp = await authorized_client.get(f"/api/security/{repo_id}/{r}")
        assert resp.status_code == 200
        
    # 4. search
    resp = await authorized_client.get(f"/api/search/{repo_id}?q=test")
    assert resp.status_code == 200
    
    # 5. export
    resp = await authorized_client.get(f"/api/export/{repo_id}/pdf")
    assert resp.status_code == 200
    # Wait to clean up repo
    resp = await authorized_client.delete(f"/api/repos/{repo_id}")
    assert resp.status_code in (204, 404)

@pytest.mark.asyncio
async def test_webhook_github(client: AsyncClient):
    payload = {"ref": "refs/heads/main"}
    payload_body = json.dumps(payload).encode('utf-8')
    secret = settings.github_webhook_secret or "testsecret"
    settings.github_webhook_secret = secret
    
    mac = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    signature = "sha256=" + mac.hexdigest()
    
    resp = await client.post(
        "/api/webhooks/github", 
        content=payload_body,
        headers={"content-type": "application/json", "x-github-event": "push", "x-hub-signature-256": signature}
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Webhook accepted"}
