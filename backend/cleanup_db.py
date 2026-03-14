import asyncio
from app.core.database import async_session_maker
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.documentation import Documentation
from app.models.security_flag import SecurityFlag
from sqlalchemy import delete

async def run():
    async with async_session_maker() as db:
        await db.execute(delete(SecurityFlag))
        await db.execute(delete(Documentation))
        await db.execute(delete(ScanJob))
        await db.execute(delete(Repository))
        await db.commit()
        print("Successfully deleted all repositories, scan jobs, documentations, and security flags.")

if __name__ == "__main__":
    asyncio.run(run())
