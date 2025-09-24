import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings, settings_dep
from app.database import db_manager, get_db
from app.models import User, SubscriptionPlan, Subscription, BillingHistory, SubscriptionStatus
from app.schemas import (
    UserCreate, User as UserSchema,
    SubscriptionPlanCreate, SubscriptionPlan as SubscriptionPlanSchema,
    SubscriptionCreate, Subscription as SubscriptionSchema,
    BillingProcessResult,
    ErrorResponse, SuccessResponse
)
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern application lifespan manager."""
    settings = get_settings()

    # Log startup with masked config
    logger.info("Starting Modern Billing System", extra=settings.get_masked_config())

    # Create database tables
    await db_manager.create_tables()
    logger.info("Database tables created/verified")

    # Initialize services
    app.state.billing_service = BillingService()
    app.state.payment_service = PaymentService()
    logger.info("Services initialized")

    yield

    # Cleanup
    await db_manager.close()
    logger.info("Modern Billing System shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Modern app factory with dependency injection."""

    app = FastAPI(
        title="Modern Billing System",
        description="Migrated from legacy PHP to modern Python/FastAPI architecture",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Modern CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Modern request logging middleware
    @app.middleware("http")
    async def request_logging_middleware(request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]

        # Add request context
        request.state.request_id = request_id

        response = await call_next(request)

        duration = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration
            }
        )

        return response

    # Override settings if provided (for testing)
    if settings:
        app.dependency_overrides[settings_dep] = lambda: settings

    return app


# Create the main app instance
app = create_app()


# Modern API Routes with proper error handling

@app.get("/")
async def root():
    """Modern API root with system information."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "status": "healthy",
        "timestamp": datetime.utcnow()
    }


@app.get("/health")
async def health_check():
    """Modern health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.post("/users/", response_model=UserSchema)
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user with modern validation."""
    try:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == user.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create new user
        db_user = User(email=user.email, name=user.name)
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        logger.info(f"Created user: {user.email}")
        return db_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/users/", response_model=List[UserSchema])
async def get_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get users with modern pagination."""
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    return result.scalars().all()


@app.post("/subscription-plans/", response_model=SubscriptionPlanSchema)
async def create_subscription_plan(
    plan: SubscriptionPlanCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new subscription plan."""
    try:
        db_plan = SubscriptionPlan(**plan.model_dump())
        db.add(db_plan)
        await db.commit()
        await db.refresh(db_plan)

        logger.info(f"Created subscription plan: {plan.name}")
        return db_plan

    except Exception as e:
        logger.error(f"Error creating subscription plan: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/subscription-plans/", response_model=List[SubscriptionPlanSchema])
async def get_subscription_plans(
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db)
):
    """Get subscription plans with filtering."""
    query = select(SubscriptionPlan)
    if active_only:
        query = query.where(SubscriptionPlan.is_active == True)

    result = await db.execute(query.order_by(SubscriptionPlan.price))
    return result.scalars().all()


@app.post("/subscriptions/", response_model=SubscriptionSchema)
async def create_subscription(
    subscription: SubscriptionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    billing_service: BillingService = Depends(lambda: app.state.billing_service)
):
    """Create a new subscription with modern async processing."""
    try:
        # Validate user exists
        user_result = await db.execute(select(User).where(User.id == subscription.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Validate plan exists
        plan_result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id))
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found")

        # Create subscription
        db_subscription = await billing_service.create_subscription(db, subscription)

        # Schedule initial billing in background
        background_tasks.add_task(
            billing_service.process_initial_billing,
            db_subscription.id
        )

        logger.info(f"Created subscription {db_subscription.id} for user {subscription.user_id}")
        return db_subscription

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/subscriptions/", response_model=List[SubscriptionSchema])
async def get_subscriptions(
    user_id: Optional[int] = Query(default=None),
    status: Optional[SubscriptionStatus] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get subscriptions with modern filtering and eager loading."""
    query = select(Subscription).options(
        selectinload(Subscription.user),
        selectinload(Subscription.plan),
        selectinload(Subscription.billing_history).limit(5)
    )

    # Modern filtering
    if user_id:
        query = query.where(Subscription.user_id == user_id)
    if status:
        query = query.where(Subscription.status == status)

    query = query.offset(skip).limit(limit).order_by(Subscription.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@app.post("/billing/process", response_model=BillingProcessResult)
async def process_billing_cycle(
    background_tasks: BackgroundTasks,
    billing_service: BillingService = Depends(lambda: app.state.billing_service)
):
    """Modern async billing processing with job tracking."""
    try:
        job_id = str(uuid.uuid4())

        # Start billing process in background
        background_tasks.add_task(
            billing_service.process_billing_cycle_async,
            job_id
        )

        logger.info(f"Started billing cycle job: {job_id}")
        return BillingProcessResult(
            job_id=job_id,
            total_processed=0,
            successful=0,
            failed=0,
            duration_seconds=0,
            status="started"
        )

    except Exception as e:
        logger.error(f"Error starting billing process: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/billing/jobs/{job_id}")
async def get_billing_job_status(
    job_id: str,
    billing_service: BillingService = Depends(lambda: app.state.billing_service),
    db: AsyncSession = Depends(get_db)
):
    """Get billing job status with modern tracking."""
    try:
        job_status = await billing_service.get_job_status(db, job_id)
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")

        return job_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.patch("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
    billing_service: BillingService = Depends(lambda: app.state.billing_service)
):
    """Cancel subscription with modern soft-delete pattern."""
    try:
        success = await billing_service.cancel_subscription(db, subscription_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")

        logger.info(f"Cancelled subscription: {subscription_id}")
        return SuccessResponse(message="Subscription cancelled successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Modern error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return ErrorResponse(
        error="not_found",
        message="Resource not found"
    )


@app.exception_handler(422)
async def validation_error_handler(request, exc):
    return ErrorResponse(
        error="validation_error",
        message="Invalid input data",
        details=exc.errors() if hasattr(exc, 'errors') else None
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)