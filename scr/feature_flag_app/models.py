from uuid import UUID, uuid4
from typing import Optional, List
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship


class FlagRule(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    feature_flag_id: UUID = Field(foreign_key="featureflag.id")

    rule_type: str  # "percentage", "user_whitelist", "attribute_match"
    value: str  # e.g., "10" or "premium"

    # Link back to the parent flag
    feature_flag: "FeatureFlag" = Relationship(back_populates="rules")


class FeatureFlag(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    is_enabled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relational link to the rules list
    rules: List[FlagRule] = Relationship(back_populates="feature_flag")
