from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, String, Text, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Modern SQLAlchemy base with consistent patterns."""
    pass


class SubscriptionStatus(str, Enum):
    """Modern enum for subscription status."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    PAUSED = "paused"


class BillingCycle(str, Enum):
    """Modern enum for billing cycles."""
    MONTHLY = "monthly"
    YEARLY = "yearly"
    WEEKLY = "weekly"


class PaymentStatus(str, Enum):
    """Modern enum for payment status."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"


class User(Base):
    """Modern user model with proper indexing and validation."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Modern relationship with proper lazy loading
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        lazy="select"
    )


class SubscriptionPlan(Base):
    """Modern subscription plan with flexible pricing."""
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    billing_cycle: Mapped[BillingCycle] = mapped_column(String(20), nullable=False, index=True)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Modern relationship
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="plan",
        lazy="select"
    )


class Subscription(Base):
    """Modern subscription model with audit trail."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(String(20), default=SubscriptionStatus.ACTIVE, index=True)

    # Modern date handling with timezone awareness
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    next_billing_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Modern audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Modern relationships with proper loading
    user: Mapped["User"] = relationship("User", back_populates="subscriptions", lazy="joined")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions", lazy="joined")
    billing_history: Mapped[List["BillingHistory"]] = relationship(
        "BillingHistory",
        back_populates="subscription",
        lazy="select",
        order_by="BillingHistory.processed_at.desc()"
    )


class BillingHistory(Base):
    """Modern billing history with comprehensive tracking."""
    __tablename__ = "billing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriptions.id"),
        nullable=False,
        index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(String(20), nullable=False, index=True)

    # Modern payment tracking
    payment_method_id: Mapped[Optional[str]] = mapped_column(String(255))
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Modern timestamps with processing details
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Modern relationship
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="billing_history",
        lazy="joined"
    )


class BillingJob(Base):
    """Modern job tracking for async billing processing."""
    __tablename__ = "billing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Modern job details
    total_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # Modern error tracking
    error_details: Mapped[Optional[str]] = mapped_column(Text)

    # Modern timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)