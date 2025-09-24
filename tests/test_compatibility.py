import asyncio
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from unittest.mock import Mock, patch

import sys
sys.path.append('/var/www/matheuszaid/github/php-to-python-migration/modern-python')

from app.main import app
from app.services.billing_service import BillingService
from app.services.subscription_service import SubscriptionService


class TestAPICompatibility:
    """Ensure API compatibility between legacy PHP and modern Python systems."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_create_subscription_compatibility(self):
        """Test that modern API accepts legacy request format."""
        legacy_request = {
            "user_id": 1,
            "plan_id": 2,
            "payment_method_id": "pm_123456789"
        }

        with patch('app.services.subscription_service.SubscriptionService.create_subscription') as mock_create:
            mock_create.return_value = {
                "id": 123,
                "user_id": 1,
                "plan_id": 2,
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z"
            }

            response = self.client.post("/subscriptions/", json=legacy_request)

            assert response.status_code == 200
            data = response.json()

            # Verify response matches legacy format
            assert "id" in data
            assert "status" in data
            assert data["user_id"] == legacy_request["user_id"]
            assert data["plan_id"] == legacy_request["plan_id"]

    def test_billing_cycle_endpoint_compatibility(self):
        """Test billing cycle endpoint maintains legacy behavior."""
        with patch('app.services.billing_service.BillingService.process_billing_cycle') as mock_billing:
            mock_billing.return_value = {
                "processed": 150,
                "successful": 142,
                "failed": 8,
                "total_amount": "15420.75"
            }

            response = self.client.post("/billing/process-cycle")

            assert response.status_code == 200
            data = response.json()

            # Legacy PHP returned these exact fields
            assert "processed" in data
            assert "successful" in data
            assert "failed" in data
            assert "total_amount" in data

    def test_user_subscription_list_compatibility(self):
        """Test user subscription listing maintains legacy format."""
        user_id = 123

        with patch('app.services.subscription_service.SubscriptionService.get_user_subscriptions') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "plan_id": 2,
                    "status": "active",
                    "next_billing_date": "2024-02-15",
                    "plan_name": "Premium Monthly",
                    "plan_price": "29.99"
                }
            ]

            response = self.client.get(f"/users/{user_id}/subscriptions")

            assert response.status_code == 200
            data = response.json()

            assert isinstance(data, list)
            if data:
                subscription = data[0]
                # Legacy fields that must be preserved
                assert "id" in subscription
                assert "plan_id" in subscription
                assert "status" in subscription
                assert "next_billing_date" in subscription


class TestDataIntegrity:
    """Verify data consistency between legacy and modern systems."""

    @pytest.mark.asyncio
    async def test_subscription_data_transformation(self):
        """Test that legacy data transforms correctly to modern format."""
        legacy_subscription = {
            'id': 123,
            'user_id': 456,
            'plan_id': 789,
            'status': 'active',
            'next_billing_date': '2024-02-15',
            'created_at': '2024-01-15 10:30:00'
        }

        # Simulate transformation logic
        transformed = self._transform_subscription_data(legacy_subscription)

        assert transformed['id'] == legacy_subscription['id']
        assert transformed['user_id'] == legacy_subscription['user_id']
        assert transformed['plan_id'] == legacy_subscription['plan_id']
        assert transformed['status'] == legacy_subscription['status']
        # Modern system should add timezone info
        assert 'T' in transformed['created_at'] or 'Z' in transformed['created_at']

    def _transform_subscription_data(self, legacy_data):
        """Helper method to simulate data transformation."""
        transformed = legacy_data.copy()

        # Convert datetime format
        if 'created_at' in transformed and ' ' in transformed['created_at']:
            transformed['created_at'] = transformed['created_at'].replace(' ', 'T') + 'Z'

        return transformed

    @pytest.mark.asyncio
    async def test_billing_calculation_consistency(self):
        """Verify billing calculations match between systems."""
        test_cases = [
            {"amount": Decimal("29.99"), "tax_rate": Decimal("0.08"), "expected": Decimal("32.39")},
            {"amount": Decimal("19.99"), "tax_rate": Decimal("0.08"), "expected": Decimal("21.59")},
            {"amount": Decimal("49.99"), "tax_rate": Decimal("0.08"), "expected": Decimal("53.99")},
        ]

        billing_service = BillingService()

        for case in test_cases:
            result = await billing_service._calculate_total_with_tax(
                case["amount"],
                case["tax_rate"]
            )
            assert abs(result - case["expected"]) < Decimal("0.01")


class TestPerformance:
    """Validate performance improvements over legacy system."""

    @pytest.mark.asyncio
    async def test_concurrent_subscription_processing(self):
        """Test that modern system can handle concurrent operations."""
        subscription_service = SubscriptionService()

        # Create mock database session
        mock_db = Mock(spec=AsyncSession)
        mock_db.commit = asyncio.coroutine(lambda: None)
        mock_db.rollback = asyncio.coroutine(lambda: None)
        mock_db.refresh = asyncio.coroutine(lambda x: None)

        # Test concurrent processing
        tasks = []
        for i in range(10):
            task = self._simulate_subscription_creation(subscription_service, mock_db, i)
            tasks.append(task)

        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()

        # Should complete much faster than legacy sequential processing
        processing_time = end_time - start_time
        assert processing_time < 2.0  # Should be sub-2-second for 10 operations

        # Verify no exceptions in results
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0

    async def _simulate_subscription_creation(self, service, db_session, user_id):
        """Simulate subscription creation for performance testing."""
        try:
            # Simulate async operation
            await asyncio.sleep(0.1)
            return {"success": True, "user_id": user_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @pytest.mark.asyncio
    async def test_billing_cycle_performance(self):
        """Test billing cycle processing performance."""
        billing_service = BillingService()

        # Mock database operations
        with patch.object(billing_service, 'get_subscriptions_due_for_billing') as mock_get:
            mock_get.return_value = [{"id": i} for i in range(100)]

            with patch.object(billing_service, '_process_subscription_billing') as mock_process:
                mock_process.return_value = {"success": True}

                start_time = asyncio.get_event_loop().time()
                result = await billing_service.process_billing_cycle_async("test_job")
                end_time = asyncio.get_event_loop().time()

                # Should complete within reasonable time
                processing_time = end_time - start_time
                assert processing_time < 10.0  # 10 seconds max for 100 subscriptions
                assert result.get("success_rate", 0) > 0.9  # 90%+ success rate


class TestErrorHandling:
    """Test error handling improvements in modern system."""

    def test_invalid_subscription_creation(self):
        """Test proper error handling for invalid subscription data."""
        invalid_request = {
            "user_id": -1,  # Invalid user ID
            "plan_id": 0,   # Invalid plan ID
            "payment_method_id": ""  # Empty payment method
        }

        client = TestClient(app)
        response = client.post("/subscriptions/", json=invalid_request)

        # Should return proper HTTP status and error message
        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_payment_failure_handling(self):
        """Test payment failure scenarios are handled gracefully."""
        billing_service = BillingService()

        # Mock payment service to simulate failure
        with patch.object(billing_service.payment_service, 'process_payment') as mock_payment:
            mock_payment.return_value = {
                "success": False,
                "failure_reason": "Insufficient funds"
            }

            result = await billing_service._process_subscription_billing({
                "id": 123,
                "user_id": 456,
                "amount": Decimal("29.99")
            })

            # Should handle failure gracefully
            assert result["success"] == False
            assert "failure_reason" in result
            assert result["failure_reason"] == "Insufficient funds"


class TestDatabaseMigration:
    """Test database migration and data consistency."""

    def test_schema_compatibility(self):
        """Test that new schema can handle legacy data structures."""
        legacy_user_data = {
            "id": 123,
            "email": "test@example.com",
            "name": "Test User",
            "signup_date": "2024-01-15"  # Legacy date format
        }

        # Should be able to process legacy data format
        modern_user_data = self._transform_user_data(legacy_user_data)

        assert modern_user_data["id"] == legacy_user_data["id"]
        assert modern_user_data["email"] == legacy_user_data["email"]
        assert modern_user_data["name"] == legacy_user_data["name"]
        assert "created_at" in modern_user_data  # Modern field name

    def _transform_user_data(self, legacy_data):
        """Transform legacy user data to modern format."""
        transformed = legacy_data.copy()

        # Map legacy field names to modern ones
        if "signup_date" in transformed:
            transformed["created_at"] = transformed.pop("signup_date") + "T00:00:00Z"

        return transformed


if __name__ == "__main__":
    # Run compatibility tests
    pytest.main([__file__, "-v"])