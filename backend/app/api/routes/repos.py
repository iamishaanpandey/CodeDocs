from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.api.deps_rbac import require_role
from app.models.user import User
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.core.celery_app import celery_app
from app.services.github_client import register_webhook, delete_webhook
from pydantic import BaseModel
import httpx

router = APIRouter()

class RepoCreate(BaseModel):
    github_url: str
    connection_type: str = "public"
    git_username: str | None = None
    git_password: str | None = None

class RepoResponse(BaseModel):
    id: uuid.UUID
    github_repo_url: str
    github_repo_name: str
    github_repo_owner: str
    scan_status: str

    class Config:
        from_attributes = True

@router.post("/", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def add_repository(
    data: RepoCreate,
    current_user: User = Depends(require_role("admin", "owner", "member")),
    db: AsyncSession = Depends(get_db)
):
    parts = data.github_url.rstrip("/").split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GitHub URL")
    owner, name = parts[-2], parts[-1]

    stmt = select(Repository).where(Repository.github_repo_url == data.github_url, Repository.user_id == current_user.id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    # Access verification
    if data.connection_type == "github_app":
        if not current_user.github_token:
            raise HTTPException(status_code=400, detail="GitHub account not connected")
        
        async with httpx.AsyncClient() as client:
            verify_response = await client.get(
                f"https://api.github.com/repos/{owner}/{name}",
                headers={"Authorization": f"token {current_user.github_token}"}
            )
            if verify_response.status_code != 200:
                raise HTTPException(status_code=403, detail="Access to repository denied or repository not found")

    repo = Repository(
        user_id=current_user.id,
        github_repo_url=data.github_url,
        github_repo_name=name,
        github_repo_owner=owner,
        scan_status="pending"
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Auto-register GitHub webhook if user has a token
    if current_user.github_token and settings.github_webhook_secret:
        import os
        callback_url = f"{settings.frontend_url.replace('5173', '8000')}/api/webhooks/github"
        webhook_id = await register_webhook(
            owner, name,
            callback_url,
            settings.github_webhook_secret,
            current_user.github_token
        )
        if webhook_id:
            repo.webhook_id = webhook_id
            await db.commit()

    job = ScanJob(repository_id=repo.id, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    celery_app.send_task("process_repository", args=[str(job.id), str(repo.id)])

    return repo

@router.get("/github/list")
async def github_list_repos(
    current_user: User = Depends(get_current_user)
):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")
        
    async with httpx.AsyncClient() as client:
        # Get user repos
        headers = {"Authorization": f"token {current_user.github_token}"}
        user_repos_response = await client.get(
            "https://api.github.com/user/repos?sort=updated&per_page=100&type=all",
            headers=headers
        )
        if user_repos_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user repositories from GitHub")
        
        repos = user_repos_response.json()
        
        # Get org repos
        orgs_response = await client.get("https://api.github.com/user/orgs", headers=headers)
        if orgs_response.status_code == 200:
            orgs = orgs_response.json()
            for org in orgs:
                org_name = org["login"]
                org_repos_response = await client.get(
                    f"https://api.github.com/orgs/{org_name}/repos?per_page=100",
                    headers=headers
                )
                if org_repos_response.status_code == 200:
                    repos.extend(org_repos_response.json())
                    
    formatted_repos = []
    for r in repos:
        formatted_repos.append({
            "github_id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r.get("description"),
            "private": r["private"],
            "html_url": r["html_url"],
            "default_branch": r.get("default_branch", "main"),
            "language": r.get("language"),
            "updated_at": r["updated_at"],
            "stars": r.get("stargazers_count", 0),
            "owner": {
                "login": r["owner"]["login"],
                "avatar_url": r["owner"].get("avatar_url")
            }
        })
        
    return {"repos": formatted_repos, "total": len(formatted_repos)}

@router.get("/", response_model=List[RepoResponse])
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).where(Repository.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "owner")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Clean up GitHub webhook before deleting
    if repo.webhook_id and current_user.github_token:
        await delete_webhook(
            repo.github_repo_owner,
            repo.github_repo_name,
            repo.webhook_id,
            current_user.github_token
        )
    
    await db.delete(repo)
    await db.commit()
    return None

@router.post("/{repo_id}/scan")
async def trigger_scan(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    job = ScanJob(repository_id=repo.id, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    celery_app.send_task("process_repository", args=[str(job.id), str(repo.id)])
    
    return {"message": "Scan triggered", "job_id": job.id}

class JobSummary(BaseModel):
    id: uuid.UUID
    status: str
    processed_files: int
    total_files: int

@router.get("/{repo_id}/jobs", response_model=List[JobSummary])
async def list_repo_jobs(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    stmt = select(ScanJob).where(ScanJob.repository_id == repo_id)
    result = await db.execute(stmt)
    return result.scalars().all()
