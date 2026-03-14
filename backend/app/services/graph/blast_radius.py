from app.services.graph.neo4j_service import neo4j_service
from typing import List, Dict, Any

async def calculate_blast_radius(function_id: str, depth: int = 3) -> List[Dict[str, Any]]:
    """
    Returns the downstream functions affected by changing the given function_id.
    Matches paths up to 'depth' hops where (downstream)-[:CALLS]->(function_id)
    """
    query = f"""
    MATCH path = (downstream:Function)-[:CALLS*1..{depth}]->(target:Function {{id: $function_id}})
    RETURN DISTINCT downstream.id AS affected_function, downstream.name AS name, downstream.file_path AS file_path
    """
    params = {"function_id": function_id}
    records = await neo4j_service.execute_query(query, params)
    return records
