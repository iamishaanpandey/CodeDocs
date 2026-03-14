from app.services.graph.neo4j_service import neo4j_service
from typing import List, Dict, Any

async def create_function_node(repo_id: str, file_path: str, func_name: str, complexity: int):
    query = """
    MERGE (f:Function {id: $id})
    SET f.repo_id = $repo_id,
        f.file_path = $file_path,
        f.name = $func_name,
        f.complexity = $complexity
    RETURN f
    """
    params = {
        "id": f"{repo_id}:{file_path}:{func_name}",
        "repo_id": repo_id,
        "file_path": file_path,
        "func_name": func_name,
        "complexity": complexity
    }
    await neo4j_service.execute_query(query, params)

async def create_calls_relationship(caller_id: str, callee_id: str):
    query = """
    MATCH (caller:Function {id: $caller_id})
    MATCH (callee:Function {id: $callee_id})
    MERGE (caller)-[:CALLS]->(callee)
    """
    params = {
        "caller_id": caller_id,
        "callee_id": callee_id
    }
    await neo4j_service.execute_query(query, params)
