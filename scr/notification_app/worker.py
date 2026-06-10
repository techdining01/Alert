import asyncio
from arq.connections import RedisSettings


async def send_email_task(ctx, recipient_email: str, message: str):
    """Core simulation logic for an expensive background I/O task."""
    print(f"[Worker] Starting email dispatch to {recipient_email}...")

    # Simulate network latency interacting with SendGrid/Twilio API
    await asyncio.sleep(4)

    print(f"[Worker] Successfully sent message to {recipient_email}!")
    return True


class WorkerSettings:
    # Tell the worker how to find your newly running Redis server
    redis_settings = RedisSettings(host="127.0.0.1", port=6379)
    functions = [send_email_task]


