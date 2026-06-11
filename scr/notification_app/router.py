from fastapi import APIRouter, Depends, HTTPException, status
from redis import asyncio as aioredis
from sqlmodel import Session, select
from arq import create_pool
from arq.connections import RedisSettings
from typing import Annotated
from scr.database import get_redis_client, get_session
from .models import NotificationRequest, NotificationLog, UserNotificationPreference



note_router = APIRouter(prefix="/notifications", tags=["Notifications"])

LIMIT = 3
WINDOW_SECONDS = 60


@note_router.post("/send")
async def trigger_notification(
    payload: NotificationRequest,
    db: Annotated[Session, Depends(get_session)],
    redis: aioredis.Redis = Depends(get_redis_client),
):
    # --- STEP 1: RATE LIMITER ---
    redis_key = f"rate_limit:{payload.user_id}:notification"
    current_requests = await redis.incr(redis_key)
    if current_requests == 1:
        await redis.expire(redis_key, WINDOW_SECONDS)

    if current_requests > LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded."
        )

    # --- STEP 2: CHECK USER PREFERENCES (Core Logic) ---
    statement = select(UserNotificationPreference).where(
        UserNotificationPreference.user_id == payload.user_id
    )
    result = await db.exec(statement)
    preference = result.first()

    # If a preference profile exists, check if their targeted channel is turned off
    if preference:
        if payload.channel == "email" and not preference.email_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has muted email notifications.",
            )
        elif payload.channel == "sms" and not preference.sms_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has muted SMS notifications.",
            )
        elif payload.channel == "push" and not preference.push_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has muted push notifications.",
            )

    # --- STEP 3: PERSIST AS PENDING ---
    db_log = NotificationLog(
        user_id=payload.user_id,
        recipient=payload.recipient_email,
        channel=payload.channel,
        message=payload.message,
        status="pending",
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    # --- STEP 4: OFFLOAD TO ARQ BACKGROUND WORKER ---
    queue = await create_pool(RedisSettings(host="127.0.0.1", port=6379))
    await queue.enqueue_job(
        "send_email_task",
        log_id=str(db_log.id),
        recipient_email=payload.recipient_email,
        message=payload.message,
    )

    return {
        "status": "Accepted",
        "notification_id": db_log.id,
        "message": "Passed preference rules. Dispatched to worker queue.",
    }
