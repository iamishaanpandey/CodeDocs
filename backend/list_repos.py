import asyncio
from app.core.database import async_session_maker
from app.models.repository import Repository
from sqlalchemy import select

async def run():
    async with async_session_maker() as db:
        result = await db.execute(select(Repository))
        rows = result.scalars().all()
        for r in rows:
            print(f"Repo: {r.id} {r.github_repo_name}")

if __name__ == "__main__":
    asyncio.run(run())
