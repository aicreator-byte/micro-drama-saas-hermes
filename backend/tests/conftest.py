import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db, Base
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.models import User, Project, SeriesBible, Character, Location, Episode, Scene, SceneCharacter, Dialogue, Prompt, GoogleAccount, FlowTask, Asset, EpisodeRevision, AuditLog

# Test database URL (SQLite in-memory for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db():
    """Create a fresh database for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_engine():
    """Dispose the test engine after all tests complete."""
    yield
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db):
    """Create a test client with overridden database dependency."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user2(db):
    """Create a second test user for isolation tests."""
    user = User(
        email="test2@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User 2",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user):
    """Create auth headers for test user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers2(test_user2):
    """Create auth headers for test user 2."""
    token = create_access_token(data={"sub": str(test_user2.id)})
    return {"Authorization": f"Bearer {token}"}


@ pytest_asyncio.fixture
async def test_project(db, test_user):
    """Create a test project."""
    project = Project(
        owner_id=test_user.id,
        title="Test Project",
        description="A test project",
        genre="Drama",
        themes=["romance", "family"],
        status="DRAFT",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project