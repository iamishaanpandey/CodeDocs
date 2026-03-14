import asyncio
from app.core.database import async_session_maker
from app.models.documentation import Documentation
from app.models.security_flag import SecurityFlag
from sqlalchemy import select, func

async def run():
    async with async_session_maker() as db:
        doc_count = await db.scalar(select(func.count()).select_from(Documentation))
        sec_count = await db.scalar(select(func.count()).select_from(SecurityFlag))
        print(f"Documentation entries: {doc_count}")
        print(f"Security flags: {sec_count}")

if __name__ == "__main__":
    asyncio.run(run())
