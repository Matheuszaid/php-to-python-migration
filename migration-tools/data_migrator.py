"""
Data Migration Tool for Legacy PHP to Modern Python System Migration
"""

import asyncio
import logging
import pandas as pd
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import asyncpg


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    records_processed: int
    records_migrated: int
    errors: List[str]
    processing_time_seconds: float


@dataclass
class MigrationConfig:
    """Configuration for data migration."""
    legacy_db_url: str
    modern_db_url: str
    batch_size: int = 1000
    validate_data: bool = True
    dry_run: bool = False


class DataMigrator:
    """Main data migration orchestrator."""

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.legacy_engine = create_engine(config.legacy_db_url)
        self.modern_engine = create_async_engine(config.modern_db_url)
        self.migration_log = []

    async def migrate_all_data(self) -> Dict[str, MigrationResult]:
        """Execute complete data migration pipeline."""
        logger.info("Starting complete data migration")
        start_time = datetime.now()

        results = {}

        try:
            # Migration order is important due to foreign key constraints
            migration_steps = [
                ("users", self.migrate_users),
                ("subscription_plans", self.migrate_subscription_plans),
                ("subscriptions", self.migrate_subscriptions),
                ("billing_history", self.migrate_billing_history)
            ]

            for step_name, step_function in migration_steps:
                logger.info(f"Starting migration step: {step_name}")
                result = await step_function()
                results[step_name] = result

                if not result.success:
                    logger.error(f"Migration step {step_name} failed")
                    break

                logger.info(f"Completed {step_name}: {result.records_migrated} records migrated")

            # Verify data integrity after migration
            if all(result.success for result in results.values()):
                integrity_check = await self.verify_migration_integrity()
                results["integrity_check"] = integrity_check

        except Exception as e:
            logger.error(f"Migration failed with exception: {e}")
            raise

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        logger.info(f"Migration completed in {total_time:.2f} seconds")

        return results

    async def migrate_users(self) -> MigrationResult:
        """Migrate user data from legacy to modern system."""
        start_time = datetime.now()
        errors = []
        records_processed = 0
        records_migrated = 0

        try:
            # Extract from legacy system
            legacy_query = """
                SELECT id, email, full_name, signup_date, active,
                       created_at, updated_at
                FROM users
                ORDER BY id
            """

            legacy_data = pd.read_sql(legacy_query, self.legacy_engine)
            records_processed = len(legacy_data)

            logger.info(f"Extracted {records_processed} users from legacy system")

            # Transform data
            transformed_data = self._transform_user_data(legacy_data)

            # Validate data
            if self.config.validate_data:
                validation_errors = self._validate_user_data(transformed_data)
                if validation_errors:
                    errors.extend(validation_errors)
                    return MigrationResult(
                        success=False,
                        records_processed=records_processed,
                        records_migrated=0,
                        errors=errors,
                        processing_time_seconds=0
                    )

            # Load to modern system in batches
            if not self.config.dry_run:
                records_migrated = await self._batch_insert_users(transformed_data)
            else:
                records_migrated = len(transformed_data)
                logger.info("Dry run: Would have migrated %d users", records_migrated)

        except Exception as e:
            errors.append(f"User migration error: {str(e)}")
            logger.error(f"User migration failed: {e}")

        processing_time = (datetime.now() - start_time).total_seconds()

        return MigrationResult(
            success=len(errors) == 0,
            records_processed=records_processed,
            records_migrated=records_migrated,
            errors=errors,
            processing_time_seconds=processing_time
        )

    def _transform_user_data(self, legacy_df: pd.DataFrame) -> pd.DataFrame:
        """Transform legacy user data to modern format."""
        transformed = legacy_df.copy()

        # Field mapping
        field_mapping = {
            'full_name': 'name',
            'active': 'is_active',
            'signup_date': 'created_at'
        }

        for old_field, new_field in field_mapping.items():
            if old_field in transformed.columns:
                transformed[new_field] = transformed[old_field]
                if old_field != new_field:
                    transformed.drop(columns=[old_field], inplace=True)

        # Convert boolean fields
        if 'is_active' in transformed.columns:
            transformed['is_active'] = transformed['is_active'].astype(bool)

        # Convert datetime fields
        datetime_fields = ['created_at', 'updated_at']
        for field in datetime_fields:
            if field in transformed.columns:
                transformed[field] = pd.to_datetime(transformed[field], utc=True)

        # Add modern system fields
        transformed['updated_at'] = datetime.now(timezone.utc)

        return transformed

    def _validate_user_data(self, df: pd.DataFrame) -> List[str]:
        """Validate user data integrity."""
        errors = []

        # Check required fields
        required_fields = ['id', 'email', 'name']
        for field in required_fields:
            if field not in df.columns:
                errors.append(f"Missing required field: {field}")
            elif df[field].isnull().any():
                errors.append(f"Null values found in required field: {field}")

        # Check email format (basic validation)
        if 'email' in df.columns:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            invalid_emails = df[~df['email'].str.match(email_pattern, na=False)]
            if not invalid_emails.empty:
                errors.append(f"Invalid email formats found: {len(invalid_emails)} records")

        # Check for duplicate emails
        if 'email' in df.columns:
            duplicate_emails = df[df.duplicated(subset=['email'], keep=False)]
            if not duplicate_emails.empty:
                errors.append(f"Duplicate emails found: {len(duplicate_emails)} records")

        return errors

    async def _batch_insert_users(self, df: pd.DataFrame) -> int:
        """Insert user data in batches."""
        records_inserted = 0

        async with self.modern_engine.begin() as conn:
            for i in range(0, len(df), self.config.batch_size):
                batch = df[i:i + self.config.batch_size]

                # Convert to list of dicts for insertion
                records = batch.to_dict('records')

                insert_query = """
                    INSERT INTO users (id, email, name, is_active, created_at, updated_at)
                    VALUES (:id, :email, :name, :is_active, :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        name = EXCLUDED.name,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                """

                await conn.execute(text(insert_query), records)
                records_inserted += len(records)

                logger.info(f"Inserted batch of {len(records)} users")

        return records_inserted

    async def migrate_subscriptions(self) -> MigrationResult:
        """Migrate subscription data from legacy to modern system."""
        start_time = datetime.now()
        errors = []
        records_processed = 0
        records_migrated = 0

        try:
            # Extract subscriptions with related data
            legacy_query = """
                SELECT s.id, s.user_id, s.plan_id, s.status,
                       s.next_billing_date, s.trial_ends_at, s.cancelled_at,
                       s.created_at, s.updated_at,
                       sp.name as plan_name, sp.price as plan_price
                FROM subscriptions s
                LEFT JOIN subscription_plans sp ON s.plan_id = sp.id
                ORDER BY s.id
            """

            legacy_data = pd.read_sql(legacy_query, self.legacy_engine)
            records_processed = len(legacy_data)

            logger.info(f"Extracted {records_processed} subscriptions from legacy system")

            # Transform data
            transformed_data = self._transform_subscription_data(legacy_data)

            # Validate data
            if self.config.validate_data:
                validation_errors = self._validate_subscription_data(transformed_data)
                if validation_errors:
                    errors.extend(validation_errors)
                    return MigrationResult(
                        success=False,
                        records_processed=records_processed,
                        records_migrated=0,
                        errors=errors,
                        processing_time_seconds=0
                    )

            # Load to modern system
            if not self.config.dry_run:
                records_migrated = await self._batch_insert_subscriptions(transformed_data)
            else:
                records_migrated = len(transformed_data)
                logger.info("Dry run: Would have migrated %d subscriptions", records_migrated)

        except Exception as e:
            errors.append(f"Subscription migration error: {str(e)}")
            logger.error(f"Subscription migration failed: {e}")

        processing_time = (datetime.now() - start_time).total_seconds()

        return MigrationResult(
            success=len(errors) == 0,
            records_processed=records_processed,
            records_migrated=records_migrated,
            errors=errors,
            processing_time_seconds=processing_time
        )

    def _transform_subscription_data(self, legacy_df: pd.DataFrame) -> pd.DataFrame:
        """Transform legacy subscription data to modern format."""
        transformed = legacy_df.copy()

        # Convert datetime fields
        datetime_fields = ['next_billing_date', 'trial_ends_at', 'cancelled_at', 'created_at', 'updated_at']
        for field in datetime_fields:
            if field in transformed.columns:
                transformed[field] = pd.to_datetime(transformed[field], utc=True)

        # Add started_at field for modern system
        transformed['started_at'] = transformed.get('created_at', datetime.now(timezone.utc))

        # Update timestamps
        transformed['updated_at'] = datetime.now(timezone.utc)

        # Remove plan details (they'll be joined from plan table in modern system)
        columns_to_drop = ['plan_name', 'plan_price']
        transformed.drop(columns=[col for col in columns_to_drop if col in transformed.columns], inplace=True)

        return transformed

    def _validate_subscription_data(self, df: pd.DataFrame) -> List[str]:
        """Validate subscription data integrity."""
        errors = []

        # Check required fields
        required_fields = ['id', 'user_id', 'plan_id', 'status']
        for field in required_fields:
            if field not in df.columns:
                errors.append(f"Missing required field: {field}")
            elif df[field].isnull().any():
                errors.append(f"Null values found in required field: {field}")

        # Validate status values
        valid_statuses = ['active', 'cancelled', 'past_due', 'trialing', 'incomplete']
        if 'status' in df.columns:
            invalid_statuses = df[~df['status'].isin(valid_statuses)]
            if not invalid_statuses.empty:
                errors.append(f"Invalid status values found: {len(invalid_statuses)} records")

        return errors

    async def _batch_insert_subscriptions(self, df: pd.DataFrame) -> int:
        """Insert subscription data in batches."""
        records_inserted = 0

        async with self.modern_engine.begin() as conn:
            for i in range(0, len(df), self.config.batch_size):
                batch = df[i:i + self.config.batch_size]
                records = batch.to_dict('records')

                insert_query = """
                    INSERT INTO subscriptions (
                        id, user_id, plan_id, status, started_at,
                        next_billing_date, trial_ends_at, cancelled_at,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :user_id, :plan_id, :status, :started_at,
                        :next_billing_date, :trial_ends_at, :cancelled_at,
                        :created_at, :updated_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        next_billing_date = EXCLUDED.next_billing_date,
                        cancelled_at = EXCLUDED.cancelled_at,
                        updated_at = EXCLUDED.updated_at
                """

                await conn.execute(text(insert_query), records)
                records_inserted += len(records)

                logger.info(f"Inserted batch of {len(records)} subscriptions")

        return records_inserted

    async def migrate_billing_history(self) -> MigrationResult:
        """Migrate billing history data."""
        start_time = datetime.now()
        errors = []
        records_processed = 0
        records_migrated = 0

        try:
            legacy_query = """
                SELECT id, subscription_id, amount, status, billing_date,
                       payment_method, transaction_id, failure_reason,
                       created_at, updated_at
                FROM billing_history
                ORDER BY id
            """

            legacy_data = pd.read_sql(legacy_query, self.legacy_engine)
            records_processed = len(legacy_data)

            logger.info(f"Extracted {records_processed} billing records from legacy system")

            # Transform data
            transformed_data = self._transform_billing_data(legacy_data)

            # Load to modern system
            if not self.config.dry_run:
                records_migrated = await self._batch_insert_billing_history(transformed_data)
            else:
                records_migrated = len(transformed_data)

        except Exception as e:
            errors.append(f"Billing history migration error: {str(e)}")

        processing_time = (datetime.now() - start_time).total_seconds()

        return MigrationResult(
            success=len(errors) == 0,
            records_processed=records_processed,
            records_migrated=records_migrated,
            errors=errors,
            processing_time_seconds=processing_time
        )

    def _transform_billing_data(self, legacy_df: pd.DataFrame) -> pd.DataFrame:
        """Transform legacy billing data to modern format."""
        transformed = legacy_df.copy()

        # Convert amount to Decimal
        if 'amount' in transformed.columns:
            transformed['amount'] = transformed['amount'].apply(
                lambda x: float(Decimal(str(x)) if pd.notna(x) else Decimal('0'))
            )

        # Convert datetime fields
        datetime_fields = ['billing_date', 'created_at', 'updated_at']
        for field in datetime_fields:
            if field in transformed.columns:
                transformed[field] = pd.to_datetime(transformed[field], utc=True)

        return transformed

    async def _batch_insert_billing_history(self, df: pd.DataFrame) -> int:
        """Insert billing history data in batches."""
        records_inserted = 0

        async with self.modern_engine.begin() as conn:
            for i in range(0, len(df), self.config.batch_size):
                batch = df[i:i + self.config.batch_size]
                records = batch.to_dict('records')

                insert_query = """
                    INSERT INTO billing_history (
                        id, subscription_id, amount, status, billing_date,
                        payment_method, transaction_id, failure_reason,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :subscription_id, :amount, :status, :billing_date,
                        :payment_method, :transaction_id, :failure_reason,
                        :created_at, :updated_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                """

                await conn.execute(text(insert_query), records)
                records_inserted += len(records)

        return records_inserted

    async def migrate_subscription_plans(self) -> MigrationResult:
        """Migrate subscription plan data."""
        start_time = datetime.now()
        errors = []

        try:
            legacy_query = """
                SELECT id, name, description, price, billing_cycle,
                       active, created_at, updated_at
                FROM subscription_plans
                ORDER BY id
            """

            legacy_data = pd.read_sql(legacy_query, self.legacy_engine)
            transformed_data = self._transform_plan_data(legacy_data)

            records_migrated = 0
            if not self.config.dry_run:
                records_migrated = await self._batch_insert_plans(transformed_data)
            else:
                records_migrated = len(transformed_data)

        except Exception as e:
            errors.append(f"Plan migration error: {str(e)}")

        processing_time = (datetime.now() - start_time).total_seconds()

        return MigrationResult(
            success=len(errors) == 0,
            records_processed=len(legacy_data) if 'legacy_data' in locals() else 0,
            records_migrated=records_migrated,
            errors=errors,
            processing_time_seconds=processing_time
        )

    def _transform_plan_data(self, legacy_df: pd.DataFrame) -> pd.DataFrame:
        """Transform plan data to modern format."""
        transformed = legacy_df.copy()

        # Convert boolean fields
        if 'active' in transformed.columns:
            transformed['is_active'] = transformed['active'].astype(bool)
            transformed.drop(columns=['active'], inplace=True)

        # Convert price to proper format
        if 'price' in transformed.columns:
            transformed['price'] = transformed['price'].apply(
                lambda x: float(Decimal(str(x)) if pd.notna(x) else Decimal('0'))
            )

        return transformed

    async def _batch_insert_plans(self, df: pd.DataFrame) -> int:
        """Insert plan data in batches."""
        records_inserted = 0

        async with self.modern_engine.begin() as conn:
            records = df.to_dict('records')

            insert_query = """
                INSERT INTO subscription_plans (
                    id, name, description, price, billing_cycle, is_active,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :description, :price, :billing_cycle, :is_active,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    price = EXCLUDED.price,
                    is_active = EXCLUDED.is_active,
                    updated_at = EXCLUDED.updated_at
            """

            await conn.execute(text(insert_query), records)
            records_inserted = len(records)

        return records_inserted

    async def verify_migration_integrity(self) -> MigrationResult:
        """Verify data integrity after migration."""
        start_time = datetime.now()
        errors = []

        try:
            # Get counts from legacy system
            legacy_counts = self._get_legacy_counts()

            # Get counts from modern system
            modern_counts = await self._get_modern_counts()

            # Compare counts
            for table, legacy_count in legacy_counts.items():
                modern_count = modern_counts.get(table, 0)
                if legacy_count != modern_count:
                    errors.append(
                        f"Count mismatch in {table}: legacy={legacy_count}, modern={modern_count}"
                    )

            # Additional integrity checks
            await self._verify_foreign_key_integrity()

        except Exception as e:
            errors.append(f"Integrity verification error: {str(e)}")

        processing_time = (datetime.now() - start_time).total_seconds()

        return MigrationResult(
            success=len(errors) == 0,
            records_processed=sum(legacy_counts.values()) if 'legacy_counts' in locals() else 0,
            records_migrated=0,  # No records migrated in verification
            errors=errors,
            processing_time_seconds=processing_time
        )

    def _get_legacy_counts(self) -> Dict[str, int]:
        """Get record counts from legacy system."""
        counts = {}
        tables = ['users', 'subscriptions', 'subscription_plans', 'billing_history']

        for table in tables:
            query = f"SELECT COUNT(*) as count FROM {table}"
            result = pd.read_sql(query, self.legacy_engine)
            counts[table] = result.iloc[0]['count']

        return counts

    async def _get_modern_counts(self) -> Dict[str, int]:
        """Get record counts from modern system."""
        counts = {}
        tables = ['users', 'subscriptions', 'subscription_plans', 'billing_history']

        async with self.modern_engine.begin() as conn:
            for table in tables:
                query = f"SELECT COUNT(*) as count FROM {table}"
                result = await conn.execute(text(query))
                counts[table] = result.fetchone()[0]

        return counts

    async def _verify_foreign_key_integrity(self):
        """Verify foreign key relationships are intact."""
        async with self.modern_engine.begin() as conn:
            # Check subscription -> user relationships
            orphaned_subs = await conn.execute(text("""
                SELECT COUNT(*) FROM subscriptions s
                LEFT JOIN users u ON s.user_id = u.id
                WHERE u.id IS NULL
            """))

            if orphaned_subs.fetchone()[0] > 0:
                raise Exception("Found orphaned subscriptions without valid users")


async def main():
    """Main migration script entry point."""
    config = MigrationConfig(
        legacy_db_url="mysql://billing:billing123@localhost:3306/billing_legacy",
        modern_db_url="postgresql+asyncpg://billing_user:billing_pass@localhost:5432/billing_modern",
        batch_size=1000,
        validate_data=True,
        dry_run=False  # Set to True for testing
    )

    migrator = DataMigrator(config)

    try:
        results = await migrator.migrate_all_data()

        print("\n=== Migration Results ===")
        for step, result in results.items():
            status = "SUCCESS" if result.success else "FAILED"
            print(f"{step}: {status}")
            print(f"  - Records processed: {result.records_processed}")
            print(f"  - Records migrated: {result.records_migrated}")
            print(f"  - Processing time: {result.processing_time_seconds:.2f}s")
            if result.errors:
                print(f"  - Errors: {result.errors}")
            print()

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())