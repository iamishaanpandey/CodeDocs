"""
Zombie Code Detection Service

Performs reverse graph traversal from known entry points in Neo4j to detect
functions that are never reachable from any entry point (API route, CLI
command, Celery task, etc.).

Two detection strategies:
  1. Fast path (DB-only):  Documentation records with is_entry_point=False
     AND callers=[] are immediately flagged as "quick zombies".
  2. Graph path (Neo4j):   For functions with callers, verify those callers
     are themselves reachable from an entry point via reverse traversal.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documentation import Documentation
from app.models.repository import Repository
from app.services.graph.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


async def detect_quick_zombies(repo_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Fast path: functions with no callers and not an entry point.
    Does NOT require Neo4j.
    """
    stmt = select(Documentation).where(
        Documentation.repository_id == repo_id,
        Documentation.is_entry_point == False,
        Documentation.callers == []
    )
    docs = (await db.execute(stmt)).scalars().all()

    return [
        {
            "function_id": str(doc.id),
            "function_name": doc.function_name,
            "file_path": doc.file_path,
            "lines_of_code": doc.lines_of_code or 0,
            "detection_method": "quick_no_callers",
            "cyclomatic_complexity": doc.cyclomatic_complexity or 1
        }
        for doc in docs
    ]


async def detect_graph_zombies(repo_id: str) -> List[Dict[str, Any]]:
    """
    Neo4j-based reverse traversal: finds Function nodes that have no path
    from any entry-point node (depth up to 15 hops).
    """
    try:
        # Find all function IDs that ARE reachable from entry points
        reachable_query = """
        MATCH (ep:Function {repo_id: $repo_id, is_entry_point: true})
        MATCH path = (ep)-[:CALLS*0..15]->(downstream:Function {repo_id: $repo_id})
        RETURN DISTINCT downstream.id AS reachable_id
        """
        reachable_records = await neo4j_service.execute_query(
            reachable_query, {"repo_id": repo_id}
        )
        reachable_ids = {r["reachable_id"] for r in reachable_records}

        # Find ALL function IDs for this repo
        all_query = """
        MATCH (f:Function {repo_id: $repo_id})
        RETURN f.id AS func_id, f.name AS name, f.file_path AS file_path
        """
        all_records = await neo4j_service.execute_query(all_query, {"repo_id": repo_id})

        zombies = []
        for rec in all_records:
            if rec["func_id"] not in reachable_ids:
                zombies.append({
                    "function_id": rec["func_id"],
                    "function_name": rec["name"],
                    "file_path": rec["file_path"],
                    "detection_method": "graph_unreachable",
                })

        return zombies

    except Exception as e:
        logger.error(f"Graph zombie detection failed for repo {repo_id}: {e}")
        return []


async def detect_all_zombies(
    repo_id: str,
    db: AsyncSession,
    update_repo: bool = True
) -> List[Dict[str, Any]]:
    """
    Runs both detection strategies and returns a de-duplicated list of
    zombie functions, sorted by lines of code (biggest savings first).

    Also updates Repository.zombie_code_count in the database.
    """
    quick = await detect_quick_zombies(repo_id, db)
    graph = await detect_graph_zombies(repo_id)

    # Merge and de-duplicate by function_id
    seen = set()
    all_zombies = []
    for z in quick + graph:
        fid = z.get("function_id", z.get("function_name", ""))
        if fid not in seen:
            seen.add(fid)
            all_zombies.append(z)

    all_zombies.sort(key=lambda x: x.get("lines_of_code", 0), reverse=True)

    if update_repo:
        try:
            stmt = select(Repository).where(Repository.id == repo_id)
            repo = (await db.execute(stmt)).scalar_one_or_none()
            if repo:
                repo.zombie_code_count = len(all_zombies)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update zombie_code_count: {e}")

    return all_zombies
