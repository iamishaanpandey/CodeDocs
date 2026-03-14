import asyncio
from app.core.database import async_session_maker
from app.models.scan_job import ScanJob
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        res = await db.execute(select(ScanJob).order_by(ScanJob.created_at.desc()))
        jobs = res.scalars().all()
        print(f"Total jobs: {len(jobs)}")
        for job in jobs[:5]:
            print(f"Job ID: {job.id}, Status: {job.status}, Processed: {job.processed_files}/{job.total_files}, Error: {job.error_message}")

if __name__ == "__main__":
    asyncio.run(check())
