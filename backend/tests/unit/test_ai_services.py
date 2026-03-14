import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai.llm_router import llm_router
from app.services.ai.docstring_agent import generate_docstring
from app.services.ai.architect_agent import analyze_architecture
from app.services.ai.diagram_agent import generate_mermaid_diagram
from app.services.ai.security_agent import deeply_scan_for_vulnerabilities

@pytest.mark.asyncio
async def test_llm_router_groq():
    with patch("app.services.ai.llm_router.httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Groq Response"}}]}
        mock_resp.raise_for_status = lambda: None
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        
        res = await llm_router.generate_completion("Test", provider="groq")
        assert res == "Groq Response"

@pytest.mark.asyncio
async def test_generate_docstring():
    with patch("app.services.ai.docstring_agent.llm_router.generate_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "This is a test docstring"
        res = await generate_docstring("def test(): pass")
        assert res == "This is a test docstring"
        mock_llm.assert_called_once()

@pytest.mark.asyncio
async def test_generate_mermaid_diagram():
    with patch("app.services.ai.diagram_agent.llm_router.generate_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "graph TD\nA-->B"
        res = await generate_mermaid_diagram("description")
        assert res == "graph TD\nA-->B"
        mock_llm.assert_called_once()
