import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import db_manager
from app.models import Subscription, SubscriptionPlan, BillingHistory, BillingJob, SubscriptionStatus, PaymentStatus
from app.schemas import SubscriptionCreate
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class BillingService:
    """Modern billing service with async processing and proper error handling."""

    def __init__(self):
        self.payment_service = PaymentService()

    async def create_subscription(self, db: AsyncSession, subscription_data: SubscriptionCreate) -> Subscription:
        """Create a new subscription with modern business logic."""
        try:
            # Get the plan to determine trial period
            plan_result = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == subscription_data.plan_id)
            )
            plan = plan_result.scalar_one()

            # Calculate dates
            now = datetime.utcnow()
            trial_days = subscription_data.trial_days_override or plan.trial_days

            if trial_days > 0:
                trial_ends_at = now + timedelta(days=trial_days)
                next_billing_date = trial_ends_at
            else:
                # No trial, bill based on plan cycle
                if plan.billing_cycle.value == "monthly":
                    next_billing_date = now + timedelta(days=30)
                elif plan.billing_cycle.value == "yearly":
                    next_billing_date = now + timedelta(days=365)
                else:  # weekly
                    next_billing_date = now + timedelta(days=7)
                trial_ends_at = None

            # Create subscription
            subscription = Subscription(
                user_id=subscription_data.user_id,
                plan_id=subscription_data.plan_id,
                status=subscription_data.status,
                started_at=now,
                next_billing_date=next_billing_date,
                trial_ends_at=trial_ends_at
            )

            db.add(subscription)
            await db.commit()
            await db.refresh(subscription, ['user', 'plan'])

            logger.info(f"Created subscription {subscription.id} with trial until {trial_ends_at}")
            return subscription

        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            await db.rollback()
            raise

    async def process_initial_billing(self, subscription_id: int):
        """Process initial billing for new subscription (background task)."""
        async with db_manager.async_session() as db:
            try:
                # Get subscription with plan
                result = await db.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.plan))
                    .where(Subscription.id == subscription_id)
                )
                subscription = result.scalar_one_or_none()

                if not subscription:
                    logger.error(f"Subscription {subscription_id} not found for initial billing")
                    return

                # If no trial period, process immediate billing
                if not subscription.trial_ends_at:
                    await self._process_subscription_billing(db, subscription)

                logger.info(f"Initial billing processed for subscription {subscription_id}")

            except Exception as e:
                logger.error(f"Error in initial billing for subscription {subscription_id}: {e}")

    async def process_billing_cycle_async(self, job_id: str):
        """Modern async billing cycle processing with job tracking."""
        async with db_manager.async_session() as db:
            try:
                # Create job record
                job = BillingJob(
                    job_id=job_id,
                    job_type="billing_cycle",
                    status="running",
                    started_at=datetime.utcnow()
                )
                db.add(job)
                await db.commit()

                # Get subscriptions due for billing
                today = datetime.utcnow().date()
                result = await db.execute(
                    select(Subscription)
                    .options(selectinload(Subscription.plan), selectinload(Subscription.user))
                    .where(
                        and_(
                            Subscription.status == SubscriptionStatus.ACTIVE,
                            Subscription.next_billing_date <= today
                        )
                    )
                )
                subscriptions = result.scalars().all()

                job.total_subscriptions = len(subscriptions)
                await db.commit()

                # Process subscriptions in batches (modern async pattern)
                batch_size = 10
                for i in range(0, len(subscriptions), batch_size):
                    batch = subscriptions[i:i + batch_size]

                    # Process batch concurrently
                    tasks = [
                        self._process_subscription_billing(db, subscription)
                        for subscription in batch
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Update job progress
                    for result in results:
                        job.processed_count += 1
                        if isinstance(result, Exception):
                            job.failure_count += 1
                            logger.error(f"Billing failed: {result}")
                        else:
                            job.success_count += 1

                    await db.commit()

                    # Small delay between batches to prevent overwhelming
                    await asyncio.sleep(0.1)

                # Complete job
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                await db.commit()

                logger.info(f"Billing cycle job {job_id} completed: {job.success_count} success, {job.failure_count} failed")

            except Exception as e:
                logger.error(f"Error in billing cycle job {job_id}: {e}")
                # Update job status to failed
                await db.execute(
                    update(BillingJob)
                    .where(BillingJob.job_id == job_id)
                    .values(
                        status="failed",
                        error_details=str(e),
                        completed_at=datetime.utcnow()
                    )
                )
                await db.commit()

    async def _process_subscription_billing(self, db: AsyncSession, subscription: Subscription) -> bool:
        """Process billing for a single subscription with modern error handling."""
        try:
            # Simulate payment processing with modern service
            payment_result = await self.payment_service.process_payment(
                subscription.user_id,
                subscription.plan.price,
                f"Subscription {subscription.id} - {subscription.plan.name}"
            )

            # Create billing history record
            billing_record = BillingHistory(
                subscription_id=subscription.id,
                amount=subscription.plan.price,
                status=PaymentStatus.SUCCESS if payment_result.success else PaymentStatus.FAILED,
                transaction_id=payment_result.transaction_id,
                failure_reason=payment_result.failure_reason,
                processed_at=datetime.utcnow()
            )
            db.add(billing_record)

            if payment_result.success:
                # Update next billing date
                next_billing_date = self._calculate_next_billing_date(
                    subscription.next_billing_date,
                    subscription.plan.billing_cycle.value
                )
                subscription.next_billing_date = next_billing_date
                subscription.status = SubscriptionStatus.ACTIVE

                logger.info(f"Billing successful for subscription {subscription.id}")
                return True
            else:
                # Handle failed payment
                subscription.status = SubscriptionStatus.PAST_DUE
                logger.warning(f"Billing failed for subscription {subscription.id}: {payment_result.failure_reason}")
                return False

        except Exception as e:
            logger.error(f"Error processing billing for subscription {subscription.id}: {e}")
            return False

    def _calculate_next_billing_date(self, current_date: datetime, billing_cycle: str) -> datetime:
        """Calculate next billing date based on cycle."""
        if billing_cycle == "monthly":
            return current_date + timedelta(days=30)
        elif billing_cycle == "yearly":
            return current_date + timedelta(days=365)
        elif billing_cycle == "weekly":
            return current_date + timedelta(days=7)
        else:
            return current_date + timedelta(days=30)  # Default to monthly

    async def cancel_subscription(self, db: AsyncSession, subscription_id: int) -> bool:
        """Cancel subscription with modern soft-delete pattern."""
        try:
            result = await db.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                return False

            # Modern soft-delete pattern
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.utcnow()

            await db.commit()
            return True

        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription_id}: {e}")
            await db.rollback()
            return False

    async def get_job_status(self, db: AsyncSession, job_id: str) -> Optional[dict]:
        """Get billing job status with progress information."""
        try:
            result = await db.execute(
                select(BillingJob).where(BillingJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                return None

            return {
                "job_id": job.job_id,
                "status": job.status,
                "total_subscriptions": job.total_subscriptions,
                "processed": job.processed_count,
                "successful": job.success_count,
                "failed": job.failure_count,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error_details": job.error_details
            }

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None