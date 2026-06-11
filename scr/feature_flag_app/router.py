import json
from fastapi import APIRouter, Depends, HTTPException, status
from redis import asyncio as aioredis
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Annotated
from scr.database import get_session, get_redis_client
from .models import FeatureFlag, FlagRule
from .engine import evaluate_flag



flag_router = APIRouter(prefix="/flags", tags=["Feature Flags"])
CACHE_TTL = 300  # Cache for 5 minutes


class EvaluationRequest(BaseModel):
    user_id: str
    attributes: dict = {}


@flag_router.post("/{flag_name}/evaluate")
async def evaluate_feature_toggle(
    flag_name: str,
    payload: EvaluationRequest,
    db: Annotated[Session, Depends(get_session)],
    redis: aioredis.Redis = Depends(get_redis_client),
):
    redis_key = f"flag:cache:{flag_name}"

    # --- 1. REDIS LOOKUP ---
    cached_data = await redis.get(redis_key)

    if cached_data:
        try:
            # Pydantic validates and hydrates the JSON back into a complete object
            flag = FeatureFlag.model_validate_json(cached_data)
        except Exception:
            # Fallback if the cache structure is corrupt or outdated
            flag = None
    else:
        flag = None

    # --- 2. DB FALLBACK ON CACHE MISS ---
    if not flag:
        # Fetch flag and explicitly load its rules relationship from the DB
        statement = select(FeatureFlag).where(FeatureFlag.name == flag_name)
        flag = db.exec(statement).first()

        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature Flag '{flag_name}' not found.",
            )

        # Trigger explicit relationship evaluation so rules are included in our data
        _ = flag.rules

        # Serialize the entire object structure to JSON and save to Redis
        # model_dump_json handles nested relationships automatically
        await redis.setex(redis_key, CACHE_TTL, flag.model_dump_json())

    # --- 3. ALGORITHM EXECUTION ---
    is_enabled = evaluate_flag(
        user_id=payload.user_id, flag=flag, user_attributes=payload.attributes
    )

    return {
        "flag": flag_name,
        "user_id": payload.user_id,
        "enabled": is_enabled,
        "source": "cache" if cached_data else "database",
    }


class CreateRuleRequest(BaseModel):
    rule_type: str
    value: str


@flag_router.post("/{flag_name}/rules")
async def add_flag_rule(
    flag_name: str,
    payload: CreateRuleRequest,
    db: Annotated[Session, Depends(get_session)],
    redis: aioredis.Redis = Depends(get_redis_client),
):
    # 1. Look up the flag
    statement = select(FeatureFlag).where(FeatureFlag.name == flag_name)
    flag = db.exec(statement).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    # 2. Append the new rule
    new_rule = FlagRule(
        feature_flag_id=flag.id, rule_type=payload.rule_type, value=payload.value
    )
    db.add(new_rule)
    db.commit()

    # 3. Evict old cache key
    # On the next evaluation request, the app will rebuild the cache with this new rule included.
    await redis.delete(f"flag:cache:{flag_name}")

    return {
        "status": "success",
        "message": f"Rule added to {flag_name}. Cache cleared.",
    }