"""
Tests for Transaction Utilities
"""
import time
import uuid
from unittest.mock import patch, MagicMock

from django.db import OperationalError, transaction
from django.test import TestCase

from hub.apps.core.bug_prevention.transaction_utils import (
    TransactionManager,
    retry_on_deadlock,
    transaction_atomic,
    with_transaction,
)
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus


def _uid():
    return uuid.uuid4().hex[:8]


class TransactionAtomicTest(TestCase):
    """Test transaction_atomic context manager."""

    def test_transaction_atomic_success(self):
        """Test successful transaction."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        with transaction_atomic():
            asset = Asset.objects.create(
                tenant=tenant,
                key=f"test-asset-success-{uid}",
                name="Test Asset",
                status=AssetStatus.ACTIVE,
            )
            self.assertIsNotNone(asset.id)

        # Asset should still exist after context
        self.assertTrue(Asset.objects.filter(id=asset.id).exists())

    def test_transaction_atomic_rollback(self):
        """Test transaction rollback on error."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        asset_key = f"test-asset-rollback-{uid}"

        with self.assertRaises(ValueError):
            with transaction_atomic():
                Asset.objects.create(
                    tenant=tenant,
                    key=asset_key,
                    name="Test Asset",
                    status=AssetStatus.ACTIVE,
                )
                raise ValueError("Test error")

        # Asset should not exist after rollback
        self.assertFalse(Asset.objects.filter(key=asset_key).exists())


class WithTransactionDecoratorTest(TestCase):
    """Test with_transaction decorator."""

    def test_with_transaction_success(self):
        """Test successful transaction with decorator."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        asset_key = f"test-asset-dec-ok-{uid}"

        @with_transaction()
        def create_asset():
            return Asset.objects.create(
                tenant=tenant,
                key=asset_key,
                name="Test Asset",
                status=AssetStatus.ACTIVE,
            )

        asset = create_asset()

        self.assertIsNotNone(asset.id)
        self.assertTrue(Asset.objects.filter(id=asset.id).exists())

    def test_with_transaction_rollback(self):
        """Test transaction rollback with decorator."""
        uid = _uid()
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        asset_key = f"test-asset-dec-rb-{uid}"

        @with_transaction()
        def create_asset_with_error():
            Asset.objects.create(
                tenant=tenant,
                key=asset_key,
                name="Test Asset",
                status=AssetStatus.ACTIVE,
            )
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            create_asset_with_error()

        # Asset should not exist after rollback
        self.assertFalse(Asset.objects.filter(key=asset_key).exists())


class TransactionManagerTest(TestCase):
    """Test TransactionManager with real DB savepoints."""

    def setUp(self):
        """Set up test fixtures with a single uid for consistency."""
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.manager = TransactionManager()

    def test_savepoint_success(self):
        """Test successful savepoint commits data and subsequent writes persist."""
        uid = _uid()
        asset1_key = f"test-sp-ok-1-{uid}"
        asset2_key = f"test-sp-ok-2-{uid}"

        with transaction.atomic():
            with self.manager.savepoint():
                asset1 = Asset.objects.create(
                    tenant=self.tenant,
                    key=asset1_key,
                    name="Asset Inside Savepoint",
                    status=AssetStatus.ACTIVE,
                )
            # Create a second asset AFTER the savepoint to prove the
            # savepoint committed and did not break the outer transaction.
            asset2 = Asset.objects.create(
                tenant=self.tenant,
                key=asset2_key,
                name="Asset After Savepoint",
                status=AssetStatus.ACTIVE,
            )

        self.assertTrue(Asset.objects.filter(key=asset1_key).exists())
        self.assertTrue(Asset.objects.filter(key=asset2_key).exists())

    def test_savepoint_rollback(self):
        """Test that savepoint rollback undoes inner work but keeps outer work.

        The ValueError is caught INSIDE the outer atomic block but OUTSIDE
        the savepoint, so only the savepoint rolls back -- the outer
        transaction commits normally.
        """
        uid = _uid()
        asset1_key = f"test-sp-rb-1-{uid}"
        asset2_key = f"test-sp-rb-2-{uid}"

        with transaction.atomic():
            # asset1 created BEFORE the savepoint
            Asset.objects.create(
                tenant=self.tenant,
                key=asset1_key,
                name="Asset 1",
                status=AssetStatus.ACTIVE,
            )

            # The savepoint raises ValueError; we catch it here so the
            # outer atomic block is NOT broken.
            with self.assertRaises(ValueError):
                with self.manager.savepoint():
                    Asset.objects.create(
                        tenant=self.tenant,
                        key=asset2_key,
                        name="Asset 2",
                        status=AssetStatus.ACTIVE,
                    )
                    raise ValueError("Test error")

        # asset1 was outside the savepoint -- it should survive
        self.assertTrue(Asset.objects.filter(key=asset1_key).exists())
        # asset2 was inside the rolled-back savepoint -- it should be gone
        self.assertFalse(Asset.objects.filter(key=asset2_key).exists())

    def test_rollback_to_savepoint(self):
        """Test rolling back to a specific savepoint undoes subsequent writes."""
        uid = _uid()
        asset_key = f"test-rb-sp-{uid}"

        with transaction.atomic():
            sid = transaction.savepoint()

            Asset.objects.create(
                tenant=self.tenant,
                key=asset_key,
                name="Test Asset",
                status=AssetStatus.ACTIVE,
            )

            self.manager.rollback_to_savepoint(sid)

            # After rollback, the asset should no longer be visible
            self.assertFalse(Asset.objects.filter(key=asset_key).exists())


class RetryOnDeadlockTest(TestCase):
    """Test retry_on_deadlock decorator."""

    def setUp(self):
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

    @patch("time.sleep", return_value=None)
    def test_success_on_first_attempt(self, mock_sleep):
        """Test function succeeds on first call without any retries."""
        uid = _uid()
        asset_key = f"test-deadlock-ok-{uid}"

        @retry_on_deadlock(max_retries=3)
        def create_asset():
            return Asset.objects.create(
                tenant=self.tenant,
                key=asset_key,
                name="Test Asset",
                status=AssetStatus.ACTIVE,
            )

        asset = create_asset()

        self.assertIsNotNone(asset.id)
        self.assertTrue(Asset.objects.filter(key=asset_key).exists())
        mock_sleep.assert_not_called()

    @patch("time.sleep", return_value=None)
    def test_success_after_retries(self, mock_sleep):
        """Test function succeeds after deadlock retries."""
        call_count = 0

        @retry_on_deadlock(max_retries=3)
        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("deadlock detected")
            return "success"

        result = flaky_operation()

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        # sleep called for attempt 0 and attempt 1 (2 failures before success)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_non_deadlock_operational_error_not_retried(self, mock_sleep):
        """Test that non-deadlock OperationalError is re-raised immediately."""
        call_count = 0

        @retry_on_deadlock(max_retries=3)
        def bad_query():
            nonlocal call_count
            call_count += 1
            raise OperationalError("relation does not exist")

        with self.assertRaises(OperationalError) as ctx:
            bad_query()

        self.assertIn("relation does not exist", str(ctx.exception))
        # Should have been called exactly once -- no retries
        self.assertEqual(call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep", return_value=None)
    def test_all_retries_exhausted(self, mock_sleep):
        """Test that the last exception is raised when all retries fail."""
        call_count = 0

        @retry_on_deadlock(max_retries=3)
        def always_deadlock():
            nonlocal call_count
            call_count += 1
            raise OperationalError("deadlock detected")

        with self.assertRaises(OperationalError) as ctx:
            always_deadlock()

        self.assertIn("deadlock", str(ctx.exception))
        self.assertEqual(call_count, 3)
        # sleep called between attempts 0->1 and 1->2
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_lock_wait_timeout_retried(self, mock_sleep):
        """Test that 'lock wait timeout' errors are also retried."""
        call_count = 0

        @retry_on_deadlock(max_retries=2)
        def timeout_then_ok():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError("Lock wait timeout exceeded")
            return "done"

        result = timeout_then_ok()

        self.assertEqual(result, "done")
        self.assertEqual(call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)
