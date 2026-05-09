from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TransactionType(str, enum.Enum):
    PREDICTION_CHARGE = "prediction_charge"
    PAYMENT_CREDIT = "payment_credit"
    ADJUSTMENT = "adjustment"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    balance_credits: Mapped[int] = mapped_column(Integer, default=0)
    loyalty_tier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("loyalty_tiers.id", ondelete="SET NULL"), nullable=True
    )

    loyalty_tier: Mapped[Optional["LoyaltyTier"]] = relationship(back_populates="users")
    ml_models: Mapped[list["MLModel"]] = relationship(back_populates="owner")
    transactions: Mapped[list["CreditTransaction"]] = relationship(back_populates="user")


class LoyaltyTier(Base):
    __tablename__ = "loyalty_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    min_predictions_monthly: Mapped[int] = mapped_column(Integer, default=0)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    users: Mapped[list["User"]] = relationship(back_populates="loyalty_tier")


class MLModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    storage_filename: Mapped[str] = mapped_column(String(512))

    owner: Mapped["User"] = relationship(back_populates="ml_models")
    jobs: Mapped[list["PredictionJob"]] = relationship(back_populates="model")


class PredictionJob(Base):
    __tablename__ = "prediction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    model_id: Mapped[int] = mapped_column(ForeignKey("ml_models.id", ondelete="CASCADE"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    input_features: Mapped[list[Any]] = mapped_column(JSONB)
    result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    base_cost: Mapped[int] = mapped_column(Integer)
    discount_percent_applied: Mapped[int] = mapped_column(Integer, default=0)
    credits_charged: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship()
    model: Mapped["MLModel"] = relationship(back_populates="jobs")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    tx_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    reference_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint(
            "reference_type",
            "reference_id",
            name="uq_credit_tx_reference",
        ),
    )


class BillingConfig(Base):
    __tablename__ = "billing_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
