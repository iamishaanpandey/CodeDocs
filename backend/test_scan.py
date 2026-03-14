import asyncio
import uuid
from app.core.database import async_session_maker
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.user import User
from app.workers.tasks import process_repository_task
from sqlalchemy import select

async def run():
    async with async_session_maker() as db:
        # Get existing repo
        res = await db.execute(
            select(Repository).where(Repository.github_repo_name == "typing_extensions")
        )
        repo = res.scalars().first()
        
        if not repo:
            # Fallback to creating if not found (with correct fields)
            res = await db.execute(select(User))
            user = res.scalars().first()
            if not user:
                print("No user found.")
                return
                
            repo = Repository(
                user_id=user.id,
                github_repo_url="https://github.com/python/typing_extensions", 
                github_repo_name="typing_extensions",
                github_repo_owner="python",
                scan_status="pending"
            )
            db.add(repo)
            await db.commit()
            await db.refresh(repo)
            print(f"Created new Repo ID: {repo.id}")
        else:
            print(f"Found existing Repo ID: {repo.id}")

        # Trigger job
        job = ScanJob(
            repository_id=repo.id,
            status="pending",
            triggered_by="manual"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        print(f"Triggered Job ID: {job.id}")
        
        # Trigger task via celery
        print("Triggering celery task...")
        process_repository_task.delay(str(job.id), repo.github_repo_url)
        print("Task triggered. Check celery logs for progress.")

if __name__ == "__main__":
    asyncio.run(run())
