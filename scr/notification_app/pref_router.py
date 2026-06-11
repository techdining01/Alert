from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from scr.database import get_session 
from .models import UserNotificationPreference

# Add a separate preferences router
pref_router = APIRouter(prefix="/users", tags=["User Preferences"])


# Input schema to allow patching specific fields
class UpdatePreferencesRequest(BaseModel):
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None


@pref_router.patch("/{user_id}/preferences")
async def update_user_preferences(
    user_id: str, payload: UpdatePreferencesRequest, db: Session = Depends(get_session)
):
    # 1. Look up existing preferences for this user
    statement = select(UserNotificationPreference).where(
        UserNotificationPreference.user_id == user_id
    )
    preference = db.exec(statement).first()

    # 2. If it doesn't exist, initialize a new record
    if not preference:
        preference = UserNotificationPreference(user_id=user_id)
        db.add(preference)

    # 3. Apply updates dynamically using setattr
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(preference, key, value)

    db.commit()
    db.refresh(preference)

    return {
        "message": "Preferences updated successfully",
        "preferences": {
            "user_id": preference.user_id,
            "email_enabled": preference.email_enabled,
            "sms_enabled": preference.sms_enabled,
            "push_enabled": preference.push_enabled,
        },
    }
