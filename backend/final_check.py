import asyncio
from app.core.database import async_session_maker
from app.models.scan_job import ScanJob
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        res = await db.execute(select(ScanJob).order_by(ScanJob.created_at.desc()))
        job = res.scalars().first()
        if job:
            print(f"Job ID: {job.id}")
            print(f"Status: {job.status}")
            print(f"Progress: {job.progress_percent}% - {job.progress_message}")
            print(f"Processed Files: {job.processed_files}/{job.total_files}")
            print(f"Error: {job.error_message}")
        else:
            print("No jobs found.")

if __name__ == "__main__":
    asyncio.run(check())
