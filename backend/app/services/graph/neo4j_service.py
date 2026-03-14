from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self):
        self.driver = None

    async def connect(self):
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri, 
                auth=(settings.neo4j_username, settings.neo4j_password)
            )
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        if self.driver:
            await self.driver.close()

    async def execute_query(self, query: str, parameters: dict = None) -> List[Dict[str, Any]]:
        if not self.driver:
            await self.connect()
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

neo4j_service = Neo4jService()
