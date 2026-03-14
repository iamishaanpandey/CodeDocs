from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.scan_job import ScanJob

router = APIRouter()

class JobResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID | None
    status: str
    processed_files: int
    total_files: int
    error_message: str | None

    class Config:
        from_attributes = True

@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ScanJob).where(ScanJob.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/{job_id}/stream")
async def stream_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify job exists
    stmt = select(ScanJob).where(ScanJob.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            # Re-fetch inside generator requires new session, but for simplicity assuming we can use a fresh query 
            # or passing session. Wait, we should get db session inside the loop or yield.
            from app.core.database import async_session_maker
            async with async_session_maker() as session:
                stmt = select(ScanJob).where(ScanJob.id == job_id)
                current_job = (await session.execute(stmt)).scalar_one_or_none()
                if not current_job:
                    yield "event: error\ndata: job not found\n\n"
                    break
                
                status_str = f"event: message\ndata: {{\"status\": \"{current_job.status}\", \"processed\": {current_job.processed_files}, \"total\": {current_job.total_files}}}\n\n"
                yield status_str
                
                if current_job.status in ("completed", "failed"):
                    break
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
