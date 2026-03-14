import pytest
from unittest.mock import AsyncMock, patch
from app.services.graph.neo4j_service import neo4j_service
from app.services.graph.blast_radius import calculate_blast_radius
from app.services.graph.downstream_analyser import analyze_impact
from app.services.graph.graph_builder import create_function_node, create_calls_relationship

@pytest.mark.asyncio
async def test_blast_radius():
    with patch("app.services.graph.blast_radius.neo4j_service.execute_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {"affected_function": "repo:file.py:funcA", "name": "funcA", "file_path": "file.py"}
        ]
        
        result = await calculate_blast_radius("repo:file.py:target")
        assert len(result) == 1
        assert result[0]["name"] == "funcA"
        mock_query.assert_called_once()

@pytest.mark.asyncio
async def test_analyze_impact():
    with patch("app.services.graph.downstream_analyser.calculate_blast_radius", new_callable=AsyncMock) as mock_blast:
        mock_blast.return_value = [
            {"affected_function": "f1"}, {"affected_function": "f2"}, {"affected_function": "f3"}
        ]
        
        impact = await analyze_impact("repo:target")
        assert impact["affected_count"] == 3
        assert impact["impact_severity"] == "MEDIUM"

@pytest.mark.asyncio
async def test_graph_builder_create_node():
    with patch("app.services.graph.graph_builder.neo4j_service.execute_query", new_callable=AsyncMock) as mock_query:
        await create_function_node("repo1", "main.py", "start", 1)
        mock_query.assert_called_once()
        args, kwargs = mock_query.call_args
        assert args[1]["id"] == "repo1:main.py:start"
