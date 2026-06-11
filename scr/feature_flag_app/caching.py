import json
from fastapi import APIRouter, Depends, HTTPException, status
from redis import asyncio as aioredis
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession
from scr.database import get_session, get_redis_client
from scr.feature_flag_app.models import FeatureFlag
from scr.feature_flag_app.engine import evaluate_flag


flag_router = APIRouter(prefix="/flags", tags=["Feature Flags"])

CACHE_TTL_SECONDS = 300  # Cache flags for 5 minutes


class EvaluationRequest(BaseModel):
    user_id: str
    attributes: dict = {}


@flag_router.post("/{flag_name}/evaluate")
async def evaluate_feature_toggle(
    flag_name: str,
    payload: EvaluationRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    redis: aioredis.Redis = Depends(get_redis_client),
):
    redis_key = f"flag:cache:{flag_name}"

    # --- STEP 1: ATTEMPT REDIS CACHE LOOKUP ---
    cached_flag = await redis.get(redis_key)
    flag_data = None

    if cached_flag:
        # Cache Hit! Convert JSON string back to a dictionary
        flag_data = json.loads(cached_flag)
        print(f"[Cache] ⚡ Hit! Retrieved '{flag_name}' from Redis.")
    else:
        # Cache Miss! Go to PostgreSQL
        print(f"[Cache] 🐢 Miss. Fetching '{flag_name}' from PostgreSQL.")
        statement = select(FeatureFlag).where(FeatureFlag.name == flag_name)
        flag_record = db.exec(statement).first()

        if not flag_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature Flag '{flag_name}' does not exist.",
            )

        # Serialize the relational data cleanly into a dictionary structure
        flag_data = {
            "name": flag_record.name,
            "is_enabled": flag_record.is_enabled,
            "rules": [
                {"rule_type": r.rule_type, "value": r.value} for r in flag_record.rules
            ],
        }

        # Save to Redis so the next request hits the cache instantly
        await redis.setex(redis_key, CACHE_TTL_SECONDS, json.dumps(flag_data))

    # --- STEP 2: CONVERT TO AN OBJECT ENGINE CAN UNDERSTAND ---
    # We turn our dictionary back into an object to keep our core logic engine clean
    # or we rewrite engine to read dictionaries directly. Let's pass it smoothly:
    class MockRule:
        def __init__(self, d):
            self.rule_type = d["rule_type"]
            self.value = d["value"]

    class MockFlag:
        def __init__(self, d):
            self.name = d["name"]
            self.is_enabled = d["is_enabled"]
            self.rules = [MockRule(r) for r in d["rules"]]

    flag_object = MockFlag(flag_data)

    # --- STEP 3: RUN THE DETERMINISTIC ALGORITHM ---
    is_variant_enabled = evaluate_flag(
        user_id=payload.user_id, flag=flag_object, user_attributes=payload.attributes
    )

    return {
        "flag": flag_name,
        "user_id": payload.user_id,
        "enabled": is_variant_enabled,
        "cached": cached_flag is not None,
    }


@flag_router.patch("/{flag_name}/toggle")
async def toggle_flag_global(
    flag_name: str,
    is_enabled: bool,
    db: Annotated[AsyncSession, Depends(get_session)],
    redis: aioredis.Redis = Depends(get_redis_client),
):
    # 1. Update SQL Database
    statement = select(FeatureFlag).where(FeatureFlag.name == flag_name)
    flag = db.exec(statement).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    flag.is_enabled = is_enabled
    db.commit()

    # 2. CACHE INVALIDATION: Forcefully drop the old key out of Redis
    redis_key = f"flag:cache:{flag_name}"
    await redis.delete(redis_key)
    print(f"[Cache] 🔥 Evicted key '{redis_key}' due to administrative modification.")

    return {"message": f"Flag status globally updated to {is_enabled}. Cache purged."}