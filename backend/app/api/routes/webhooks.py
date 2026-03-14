"""
Webhook Handler — Extended for Enterprise Use

Handles incoming GitHub webhook events:
  push          → auto-trigger incremental scan (changed files only)
  pull_request  → fetch PR diff, run Blast Radius analysis, post comment
"""
import hmac
import hashlib
import json
import logging
from fastapi import APIRouter, Request, status, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.repository import Repository
from app.models.user import User
from app.models.pr_analysis import PRAnalysis
from app.services.github_client import get_pr_diff, post_pr_comment, update_pr_comment
from app.services.graph.blast_radius_pr import analyze_pr_diff
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_signature(payload_body: bytes, secret_token: str, signature_header: str) -> bool:
    if not signature_header:
        return False
    hash_object = hmac.new(secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


@router.post("/github", status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    payload_bytes = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    event_type = request.headers.get("x-github-event", "")

    if settings.github_webhook_secret and not verify_signature(
        payload_bytes, settings.github_webhook_secret, signature
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # ── PUSH EVENT: Trigger incremental re-scan ─────────────────────────────
    if event_type == "push":
        await _handle_push(data, db)

    # ── PULL REQUEST EVENT: Run blast radius + post comment ─────────────────
    elif event_type == "pull_request":
        action = data.get("action", "")
        if action in ("opened", "synchronize", "reopened"):
            await _handle_pull_request(data, db)

    return {"message": "Webhook accepted", "event": event_type}


async def _handle_push(data: dict, db: AsyncSession):
    """Finds the repo record and triggers an incremental Celery scan."""
    repo_url = data.get("repository", {}).get("html_url", "")
    if not repo_url:
        return

    stmt = select(Repository).where(Repository.github_repo_url == repo_url)
    repo = (await db.execute(stmt)).scalar_one_or_none()

    if not repo:
        logger.debug(f"Webhook push: no repo found for {repo_url}")
        return

    if not repo.auto_scan_on_push:
        logger.info(f"Auto-scan disabled for repo {repo.id}")
        return

    # Trigger scan — the Celery task handles incremental diffing via FileHash
    from app.models.scan_job import ScanJob
    job = ScanJob(repository_id=repo.id, status="pending", triggered_by="webhook_push")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    celery_app.send_task("process_repository", args=[str(job.id), str(repo.id)])
    logger.info(f"Auto-scan triggered for repo {repo.id} via push webhook")


async def _handle_pull_request(data: dict, db: AsyncSession):
    """Fetches PR diff, runs blast radius analysis, posts/updates PR comment."""
    pr_info = data.get("pull_request", {})
    pr_number = pr_info.get("number")
    pr_url = pr_info.get("html_url", "")
    repo_info = data.get("repository", {})
    repo_url = repo_info.get("html_url", "")
    owner = repo_info.get("owner", {}).get("login", "")
    repo_name = repo_info.get("name", "")

    if not all([pr_number, owner, repo_name]):
        logger.warning("PR webhook missing required fields")
        return

    # Find repo record
    stmt = select(Repository).where(Repository.github_repo_url == repo_url)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        logger.debug(f"PR webhook: no repo found for {repo_url}")
        return

    # Get the user's GitHub token
    stmt_user = select(User).where(User.id == repo.user_id)
    user = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user or not user.github_token:
        logger.warning(f"No GitHub token for user {repo.user_id}")
        return

    # Fetch the PR diff from GitHub API
    diff_text = await get_pr_diff(owner, repo_name, pr_number, user.github_token)
    if not diff_text:
        logger.warning(f"Could not fetch diff for PR #{pr_number}")
        return

    # Run the blast radius analysis
    try:
        report = await analyze_pr_diff(str(repo.id), diff_text, db)
    except Exception as e:
        logger.error(f"Blast radius analysis failed for PR #{pr_number}: {e}")
        return

    # Check for existing PR analysis record (re-sync)
    stmt_pr = select(PRAnalysis).where(
        PRAnalysis.repository_id == repo.id,
        PRAnalysis.pr_number == pr_number
    )
    existing_analysis = (await db.execute(stmt_pr)).scalar_one_or_none()

    if existing_analysis and existing_analysis.github_comment_id:
        # Update existing comment
        success = await update_pr_comment(
            owner, repo_name,
            existing_analysis.github_comment_id,
            report.summary_markdown,
            user.github_token
        )
        existing_analysis.risk_level = report.risk_level
        existing_analysis.affected_function_count = report.affected_count
        existing_analysis.untested_function_count = report.untested_count
        existing_analysis.mermaid_markup = report.mermaid_markup
        existing_analysis.summary_markdown = report.summary_markdown
        existing_analysis.diff_text = diff_text[:10000]  # truncate for storage
        await db.commit()
        logger.info(f"Updated PR comment for PR #{pr_number}")
    else:
        # Post new comment
        comment_id = await post_pr_comment(
            owner, repo_name, pr_number, report.summary_markdown, user.github_token
        )

        # Persist analysis
        analysis = PRAnalysis(
            repository_id=repo.id,
            pr_number=pr_number,
            pr_url=pr_url,
            diff_text=diff_text[:10000],
            risk_level=report.risk_level,
            affected_function_count=report.affected_count,
            untested_function_count=report.untested_count,
            mermaid_markup=report.mermaid_markup,
            summary_markdown=report.summary_markdown,
            github_comment_id=comment_id,
            comment_posted=comment_id is not None
        )
        db.add(analysis)
        await db.commit()
        logger.info(f"Stored PR analysis for PR #{pr_number}, risk={report.risk_level}")
