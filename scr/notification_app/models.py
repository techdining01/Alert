from enum import Enum
from pydantic import BaseModel, EmailStr
from typing import Literal
from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field



class NotificationRequest(BaseModel):
    user_id: str
    recipient_email: EmailStr
    message: str
    channel: Literal["email", "sms", "push"]



# 1. Define an explicit Enum class
class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(index=True)
    recipient: str
    channel: str
    message: str

    # 2. Use the Enum class as the type hint
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)

    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))



class UserNotificationPreference(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(index=True, unique=True)
    email_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=True)
    push_enabled: bool = Field(default=True)