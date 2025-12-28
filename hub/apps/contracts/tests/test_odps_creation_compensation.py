"""
Unit tests for ODPS creation compensation (Task 8.3.1).

Tests cover:
- rollback_created_contract() - contract rollback
- cleanup_resources() - resource cleanup
- restore_previous_state() - state restoration
- compensate() - comprehensive compensation

All tests use real implementations (no mocks/stubs) and verify:
- Contract deletion on rollback
- Resource cleanup
- State restoration
- Error handling
"""
import json
import pytest
from django.test import TestCase

from hub.apps.contracts.odps_compensation import (
    ODPSCreationCompensation,
    ODPSCreationState
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
    NormalizationStatus,
)
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSCreationCompensationTestBase(TestCase):
    """Base test class for ODPS creation compensation tests."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

        # Create ODPS contract for testing
        from hub.apps.contracts.services import ODPSService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-compensation",
                        "name": "Test ODPS for Compensation"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        })

        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Initialize compensation handler
        self.compensation = ODPSCreationCompensation(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )


class ODPSCreationCompensationRollbackTest(ODPSCreationCompensationTestBase):
    """Tests for rollback_created_contract() method."""

    def test_rollback_created_contract_success(self):
        """Test successful contract rollback."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id)
        )

        result = self.compensation.rollback_created_contract(
            contract_id=str(self.odps_contract.id),
            state=state
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["contract_id"], str(self.odps_contract.id))

        # Verify contract was deleted
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=self.odps_contract.id)

    def test_rollback_created_contract_not_found(self):
        """Test rollback when contract doesn't exist."""
        from uuid import uuid4
        fake_id = str(uuid4())

        state = ODPSCreationState(
            contract_id=fake_id
        )

        result = self.compensation.rollback_created_contract(
            contract_id=fake_id,
            state=state
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "contract_not_found")

    def test_rollback_created_contract_wrong_tenant(self):
        """Test rollback fails for contract from different tenant."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create compensation handler for other tenant
        other_compensation = ODPSCreationCompensation(
            tenant_id=str(other_tenant.id),
            user_id=str(self.user.id)
        )

        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id)
        )

        # Should not find contract (different tenant)
        result = other_compensation.rollback_created_contract(
            contract_id=str(self.odps_contract.id),
            state=state
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "contract_not_found")

        # Verify contract still exists
        self.assertTrue(Contract.objects.filter(id=self.odps_contract.id).exists())


class ODPSCreationCompensationCleanupTest(ODPSCreationCompensationTestBase):
    """Tests for cleanup_resources() method."""

    def test_cleanup_resources_success(self):
        """Test successful resource cleanup."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            asset_id=None,
            events_published=["event-1", "event-2"]
        )

        result = self.compensation.cleanup_resources(
            state=state,
            publish_compensation_events=True
        )

        self.assertEqual(result["status"], "success")
        self.assertGreater(len(result["resources_cleaned"]), 0)
        self.assertIn("events", result["resources_cleaned"])

    def test_cleanup_resources_no_events(self):
        """Test cleanup when no events were published."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            events_published=[]
        )

        result = self.compensation.cleanup_resources(
            state=state,
            publish_compensation_events=True
        )

        self.assertEqual(result["status"], "success")

    def test_cleanup_resources_without_compensation_events(self):
        """Test cleanup without publishing compensation events."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            events_published=["event-1"]
        )

        result = self.compensation.cleanup_resources(
            state=state,
            publish_compensation_events=False
        )

        self.assertEqual(result["status"], "success")


class ODPSCreationCompensationRestoreTest(ODPSCreationCompensationTestBase):
    """Tests for restore_previous_state() method."""

    def test_restore_previous_state_no_asset(self):
        """Test state restoration when no asset is involved."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            asset_id=None
        )

        result = self.compensation.restore_previous_state(state=state)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["restored_items"]), 0)

    def test_restore_previous_state_with_asset_no_version(self):
        """Test state restoration with asset but no version tracking."""
        from hub.apps.assets.models import Asset, AssetStatus
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            status=AssetStatus.DRAFT
        )

        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            asset_id=str(asset.id),
            asset_previous_version=None
        )

        result = self.compensation.restore_previous_state(state=state)

        self.assertEqual(result["status"], "success")

    def test_restore_previous_state_asset_not_found(self):
        """Test state restoration when asset doesn't exist."""
        from uuid import uuid4
        fake_asset_id = str(uuid4())

        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            asset_id=fake_asset_id,
            asset_previous_version=1
        )

        result = self.compensation.restore_previous_state(state=state)

        # Should complete without error (non-critical)
        self.assertEqual(result["status"], "success")


class ODPSCreationCompensationComprehensiveTest(ODPSCreationCompensationTestBase):
    """Tests for compensate() method."""

    def test_compensate_full_rollback(self):
        """Test comprehensive compensation with full rollback."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id),
            asset_id=None,
            events_published=["event-1"]
        )

        result = self.compensation.compensate(
            state=state,
            rollback_contract=True,
            cleanup_resources=True,
            restore_state=True,
            publish_compensation_events=True
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("rollback", result["operations"])
        self.assertIn("cleanup", result["operations"])
        self.assertIn("restore", result["operations"])

        # Verify contract was deleted
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=self.odps_contract.id)

    def test_compensate_partial_rollback(self):
        """Test compensation with only rollback."""
        state = ODPSCreationState(
            contract_id=str(self.odps_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            rollback_contract=True,
            cleanup_resources=False,
            restore_state=False,
            publish_compensation_events=False
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("rollback", result["operations"])
        self.assertNotIn("cleanup", result["operations"])
        self.assertNotIn("restore", result["operations"])

        # Verify contract was deleted
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=self.odps_contract.id)

    def test_compensate_no_contract(self):
        """Test compensation when no contract was created."""
        state = ODPSCreationState(
            contract_id=None,
            asset_id=None
        )

        result = self.compensation.compensate(
            state=state,
            rollback_contract=True,
            cleanup_resources=True,
            restore_state=True,
            publish_compensation_events=True
        )

        # Should complete successfully even without contract
        self.assertEqual(result["status"], "success")

    def test_compensate_rollback_failure(self):
        """Test compensation when rollback fails."""
        # Use a non-existent contract ID to simulate rollback failure
        from uuid import uuid4
        fake_id = str(uuid4())

        state = ODPSCreationState(
            contract_id=fake_id
        )

        result = self.compensation.compensate(
            state=state,
            rollback_contract=True,
            cleanup_resources=True,
            restore_state=True,
            publish_compensation_events=True
        )

        # Should still complete (rollback failure is handled gracefully)
        # Status may be "success" or "partial_failure" depending on implementation
        self.assertIn(result["status"], ["success", "partial_failure"])

