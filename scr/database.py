from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator
from scr.config import settings


database_url = settings.database_url


async_engine = create_async_engine(database_url)


asyncSessionLocal = async_sessionmaker(
    bind=async_engine, _class=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with asyncSessionLocal() as session:
        yield session


async def get_redis_client():
    # Connect directly to the forwarded Docker Desktop port
    client = aioredis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)
    return client
