from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models import SubscriptionStatus, BillingCycle, PaymentStatus


class UserBase(BaseModel):
    """Base user schema with validation."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Schema for creating users."""
    pass


class User(UserBase):
    """Complete user schema with relationships."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanBase(BaseModel):
    """Base subscription plan schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    billing_cycle: BillingCycle
    trial_days: int = Field(default=0, ge=0)


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Schema for creating subscription plans."""
    pass


class SubscriptionPlan(SubscriptionPlanBase):
    """Complete subscription plan schema."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingHistoryBase(BaseModel):
    """Base billing history schema."""
    amount: Decimal = Field(..., ge=0)
    status: PaymentStatus
    payment_method_id: Optional[str] = None
    transaction_id: Optional[str] = None
    failure_reason: Optional[str] = None


class BillingHistory(BillingHistoryBase):
    """Complete billing history schema."""
    id: int
    subscription_id: int
    processed_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    user_id: int
    plan_id: int
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating subscriptions."""
    trial_days_override: Optional[int] = Field(default=None, ge=0)


class Subscription(SubscriptionBase):
    """Complete subscription schema with relationships."""
    id: int
    started_at: datetime
    next_billing_date: datetime
    cancelled_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Modern relationships
    user: User
    plan: SubscriptionPlan
    billing_history: List[BillingHistory] = []

    model_config = ConfigDict(from_attributes=True)


class SubscriptionUpdate(BaseModel):
    """Schema for updating subscriptions."""
    status: Optional[SubscriptionStatus] = None
    next_billing_date: Optional[datetime] = None


class BillingJobBase(BaseModel):
    """Base billing job schema."""
    job_type: str
    status: str = "pending"


class BillingJob(BillingJobBase):
    """Complete billing job schema."""
    id: int
    job_id: str
    total_subscriptions: int = 0
    processed_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_details: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingProcessResult(BaseModel):
    """Schema for billing process results."""
    job_id: str
    total_processed: int
    successful: int
    failed: int
    duration_seconds: float
    status: str


class ErrorResponse(BaseModel):
    """Modern error response schema."""
    error: str
    message: str
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    """Modern success response schema."""
    message: str
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)