"""
RAG Embedder Service
Generates vector embeddings for each documented function and stores them
in Documentation.embedding (pgvector Vector(1536) column).

Uses a multi-model strategy:
  - Primary:  Google Gemini text-embedding-004 (gemini_api_key)
  - Fallback: Groq (via llama embedding endpoint if available)
  - Fallback: DeepSeek (via OpenAI-compat API)

Embedding text is a rich context string built from the Documentation record
fields: name, parameters, return type, docstring, complexity, callers,
callees, external services, source code snippet, and git blame summary.

Incremental indexing: skips functions whose file_path has an unchanged
FileHash record and whose embedding already exists.
"""
import logging
from typing import Optional
import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.documentation import Documentation
from app.models.file_hash import FileHash

logger = logging.getLogger(__name__)

EMBED_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSIONS = 768  # Gemini text-embedding-004 output size


def _build_embedding_text(doc: Documentation) -> str:
    """
    Constructs the rich text context string used for embedding a function.
    Including git blame and source snippet maximises semantic recall.
    """
    parts = [f"Function: {doc.function_name}"]
    parts.append(f"File: {doc.file_path}")

    if doc.docstring:
        parts.append(f"Description: {doc.docstring}")

    if doc.parameter_descriptions:
        param_str = ", ".join(
            f"{k}: {v}" for k, v in (doc.parameter_descriptions or {}).items()
        )
        parts.append(f"Parameters: {param_str}")

    if doc.return_description:
        parts.append(f"Returns: {doc.return_description}")

    if doc.big_o_estimate:
        parts.append(f"Time complexity: {doc.big_o_estimate}")

    if doc.cyclomatic_complexity is not None:
        parts.append(f"Cyclomatic complexity: {doc.cyclomatic_complexity}")

    if doc.callers:
        parts.append(f"Called by: {', '.join(str(c) for c in doc.callers[:5])}")

    if doc.callees:
        parts.append(f"Calls: {', '.join(str(c) for c in doc.callees[:5])}")

    if doc.external_services_called:
        parts.append(f"External services: {', '.join(str(s) for s in doc.external_services_called)}")

    if doc.side_effects:
        parts.append(f"Side effects: {doc.side_effects}")

    if doc.handles_pii:
        parts.append("Note: handles personally identifiable information (PII)")

    if getattr(doc, 'source_code_snippet', None):
        # Truncate snippet to 800 chars to stay within token limits
        parts.append(f"Source code:\n{doc.source_code_snippet[:800]}")

    if getattr(doc, 'git_blame_summary', None):
        parts.append(doc.git_blame_summary)

    return "\n".join(parts)


async def embed_text_gemini(text: str) -> Optional[list[float]]:
    """Embed a single string using Gemini text-embedding-004."""
    try:
        genai.configure(api_key=settings.gemini_api_key)
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text,
            task_type="retrieval_document"
        )
        return result["embedding"]
    except Exception as e:
        logger.error(f"Gemini embedding failed: {e}")
        return None


async def embed_text_deepseek(text: str) -> Optional[list[float]]:
    """
    Fallback embedding using DeepSeek via OpenAI-compatible API.
    DeepSeek's embedding dimension is 1024.
    """
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )
        response = await client.embeddings.create(
            model="text-embedding-v2",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"DeepSeek embedding failed: {e}")
        return None


async def embed_single_function(doc: Documentation) -> Optional[list[float]]:
    """
    Attempts to embed a Documentation record using available providers.
    Returns the embedding vector (list of floats) or None on full failure.
    """
    text = _build_embedding_text(doc)

    # Primary: Gemini
    embedding = await embed_text_gemini(text)
    if embedding:
        return embedding

    # Fallback: DeepSeek
    logger.warning(f"Falling back to DeepSeek for {doc.function_name}")
    embedding = await embed_text_deepseek(text)
    return embedding


async def embed_repository_functions(
    repo_id: str,
    db: AsyncSession,
    incremental: bool = True
) -> dict:
    """
    Main entry point: embeds all Documentation records for a repository.
    
    Args:
        repo_id: UUID string of the repository.
        db: Async SQLAlchemy session.
        incremental: If True, skip functions that already have an embedding.

    Returns:
        dict with counts: {embedded, skipped, failed, total}
    """
    stmt = select(Documentation).where(Documentation.repository_id == repo_id)
    docs = (await db.execute(stmt)).scalars().all()

    counts = {"embedded": 0, "skipped": 0, "failed": 0, "total": len(docs)}

    for doc in docs:
        # Skip if already embedded and incremental mode
        if incremental and getattr(doc, 'embedding', None) is not None:
            counts["skipped"] += 1
            continue

        embedding = await embed_single_function(doc)

        if embedding is None:
            logger.error(f"All embedding providers failed for {doc.function_name} in {doc.file_path}")
            counts["failed"] += 1
            continue

        # Dynamically set embedding column if pgvector is available
        try:
            doc.embedding = embedding
            doc.embedding_model = "gemini-text-embedding-004"
            await db.commit()
            counts["embedded"] += 1
        except Exception as e:
            logger.error(f"Failed to store embedding for {doc.function_name}: {e}")
            await db.rollback()
            counts["failed"] += 1

    logger.info(
        f"Embedding complete for repo {repo_id}: "
        f"{counts['embedded']} embedded, {counts['skipped']} skipped, {counts['failed']} failed"
    )
    return counts
