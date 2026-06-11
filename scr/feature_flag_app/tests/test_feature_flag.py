import pytest
import json
from fastapi.testclient import TestClient
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from scr import app
from scr.database import get_session, get_redis_client

TEST_ASYNC_DB_URL = "sqlite+aiosqlite:///:memory:"
async_test_engine = create_async_engine(TEST_ASYNC_DB_URL)


class MockRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)


# Explicitly tell the fixture to inherit function loop scoping
@pytest.fixture(name="setup_env")
async def setup_env_fixture():
    async with async_test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    mock_redis = MockRedis()

    async def override_get_async_session():
        async_session_maker = sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_async_session
    app.dependency_overrides[get_redis_client] = lambda: mock_redis

    with TestClient(app) as client:
        yield client, mock_redis

    async with async_test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    app.dependency_overrides.clear()


# --- THE LOGIC TESTS ---


# 1. Add the explicit decorator here
@pytest.mark.asyncio
# 2. Add the 'async' keyword right before def
async def test_cache_miss_then_cache_hit_lifecycle(setup_env):
    client, mock_redis = setup_env
    flag_name = "beta-feature"

    async_session_maker = sessionmaker(async_test_engine, class_=AsyncSession)
    async with async_session_maker() as session:
        from scr.feature_flag_app.models import FeatureFlag, FlagRule

        new_flag = FeatureFlag(name=flag_name, is_enabled=True)
        session.add(new_flag)
        await session.commit()
        await session.refresh(new_flag)

        rule = FlagRule(
            feature_flag_id=new_flag.id, rule_type="percentage", value="100"
        )
        session.add(rule)
        await session.commit()

    # Test Client acts as our sync-to-async boundary orchestrator here
    payload = {"user_id": "user_abc", "attributes": {}}
    response_1 = client.post(f"/flags/{flag_name}/evaluate", json=payload)
    assert response_1.status_code == 200
    assert response_1.json()["source"] == "database"

    response_2 = client.post(f"/flags/{flag_name}/evaluate", json=payload)
    assert response_2.status_code == 200
    assert response_2.json()["source"] == "cache"
