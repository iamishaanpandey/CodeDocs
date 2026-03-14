from app.services.graph.blast_radius import calculate_blast_radius

async def analyze_impact(function_id: str) -> dict:
    """
    Aggregates metrics for the structural impact of a change.
    """
    affected = await calculate_blast_radius(function_id, depth=5)
    
    impact_score = "LOW"
    if len(affected) > 10:
        impact_score = "CRITICAL"
    elif len(affected) > 5:
        impact_score = "HIGH"
    elif len(affected) > 2:
        impact_score = "MEDIUM"

    return {
        "function_id": function_id,
        "affected_count": len(affected),
        "affected_nodes": affected,
        "impact_severity": impact_score
    }
