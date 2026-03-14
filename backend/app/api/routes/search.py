"""
Semantic Search API Route

Exposes POST /api/search/{repo_id}/semantic for natural-language
codebase querying via the RAG pipeline (pgvector cosine similarity search).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.documentation import Documentation
from app.services.ingestion.rag_embedder import embed_text_gemini, embed_text_deepseek

logger = logging.getLogger(__name__)

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SemanticSearchResult(BaseModel):
    function_name: str
    file_path: str
    docstring: Optional[str]
    cyclomatic_complexity: Optional[int]
    big_o_estimate: Optional[str]
    is_entry_point: bool
    handles_pii: bool
    relevance_score: float
    source_code_snippet: Optional[str] = None
    git_blame_summary: Optional[str] = None


@router.post("/{repo_id}/semantic", response_model=List[SemanticSearchResult])
async def semantic_search(
    repo_id: uuid.UUID,
    body: SemanticSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs a vector similarity search against the embedded function
    documentation for the given repository.

    Returns the top-K most semantically relevant functions for the query.
    """
    if not body.query or len(body.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    # Generate query embedding — try Gemini first, fallback to DeepSeek
    query_embedding = await embed_text_gemini(body.query)
    if not query_embedding:
        query_embedding = await embed_text_deepseek(body.query)

    if not query_embedding:
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable. Please ensure API keys are configured."
        )

    try:
        # pgvector cosine distance (<=>), lower = more similar
        top_k = min(body.top_k, 20)
        sql = text("""
            SELECT
                id,
                function_name,
                file_path,
                docstring,
                cyclomatic_complexity,
                big_o_estimate,
                is_entry_point,
                handles_pii,
                source_code_snippet,
                git_blame_summary,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS relevance_score
            FROM documentations
            WHERE repository_id = :repo_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
        """)

        result = await db.execute(sql, {
            "repo_id": str(repo_id),
            "query_vec": str(query_embedding),
            "top_k": top_k
        })
        rows = result.fetchall()

        return [
            SemanticSearchResult(
                function_name=row.function_name,
                file_path=row.file_path,
                docstring=row.docstring,
                cyclomatic_complexity=row.cyclomatic_complexity,
                big_o_estimate=row.big_o_estimate,
                is_entry_point=row.is_entry_point,
                handles_pii=row.handles_pii,
                relevance_score=round(float(row.relevance_score), 4),
                source_code_snippet=row.source_code_snippet,
                git_blame_summary=row.git_blame_summary
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Semantic search failed for repo {repo_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Semantic search failed. The repository may not have been embedded yet. "
                   "Trigger a scan to index the codebase."
        )
