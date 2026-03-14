import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.redis_client import get_redis_client
from app.core.security import create_access_token, hash_password
from unittest.mock import AsyncMock
from app.models.user import User
from app.models.repository import Repository
import uuid

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
        
    storage = {}
    async def mock_setex(name, time, value):
        storage[name] = value
    async def mock_get(name):
        return storage.get(name)
    async def mock_delete(name):
        storage.pop(name, None)
        
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = mock_get
    mock_redis.setex.side_effect = mock_setex
    mock_redis.delete.side_effect = mock_delete
    
    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def test_user_2(db_session):
    user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        name="Other User",
        hashed_password=hash_password("otherpassword123"),
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    return user

@pytest_asyncio.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def authorized_client(client: AsyncClient, auth_headers: dict):
    client.headers.update(auth_headers)
    return client

@pytest_asyncio.fixture
async def test_repo(db_session, test_user):
    repo = Repository(
        id=uuid.uuid4(),
        user_id=test_user.id,
        github_repo_url="https://github.com/test/repo",
        github_repo_name="repo",
        github_repo_owner="test",
        scan_status="complete"
    )
    db_session.add(repo)
    await db_session.commit()
    return repo

@pytest.fixture
def sample_python_code():
    return '''
import requests
from sqlalchemy import Column, String, Integer
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    password = Column(String)

def process_payment(user_id: int, amount: float, card_number: str) -> dict:
    """Process a payment."""
    validate_card(card_number)
    for i in range(len(transactions)):
        for j in range(len(transactions[i])):
            check_duplicate(transactions[i][j])
    response = requests.post("https://api.stripe.com/v1/charges", data={"amount": amount})
    return {"status": "success"}

def validate_card(card_number: str) -> bool:
    return len(card_number) == 16

def get_user(user_id: int):
    return db.query(User).filter(User.id == user_id).first()
'''

@pytest.fixture
def sample_fastapi_code():
    return '''
from fastapi import APIRouter, Depends
from app.auth import get_current_user

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: int, current_user = Depends(get_current_user)):
    return {"user_id": user_id}

@router.post("/payments")
async def create_payment(payment_data: dict):
    return {"status": "created"}

@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: int):
    return {"deleted": user_id}
'''
