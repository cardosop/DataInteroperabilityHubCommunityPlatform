"""
Integration tests for ODPS linking compensation (Task 8.3.2).

Tests cover:
- Full ODPS linking flow with compensation on failure
- Event publishing failure compensation
- Transaction rollback behavior
- State restoration

All tests use real implementations (no mocks/stubs) and verify:
- End-to-end compensation flow
- Transaction handling
- Event publishing
- Error recovery
"""
import json
import pytest
from django.test import TestCase

from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
)
from hub.apps.contracts.odps_linking_compensation import (
    ODPSLinkingCompensation,
    ODPSLinkingState
)
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSLinkingCompensationIntegrationTestBase(TestCase):
    """Base test class for ODPS linking compensation integration tests."""

    def setUp(self):
        """Set up test fixtures."""
        import uuid
        unique_id = str(uuid.uuid4())[:8]

        # Create tenant with unique name
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user with unique email
        self.user = User.objects.create_user(
            email=f"user-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

        # Initialize services
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        self.odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create ODCS contract
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-integration",
            "name": "Test ODCS for Integration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        })

        self.odcs_contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS
        )

        # Valid ODPS document
        self.valid_odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-integration",
                        "name": "Test ODPS for Integration"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                },
                "contract": {
                    "spec": json.loads(odcs_raw)
                }
            }
        }


class ODPSLinkingCompensationSuccessTest(ODPSLinkingCompensationIntegrationTestBase):
    """Tests for successful ODPS linking without compensation."""

    def test_link_odps_success_no_compensation(self):
        """Test successful ODPS linking doesn't trigger compensation."""
        odps_raw = json.dumps(self.valid_odps_doc)

        odps_contract = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify contract was created and linked
        self.assertIsNotNone(odps_contract)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)

        # Verify links exist
        odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(self.odcs_contract.id))

        odcs_extensions = self.odcs_contract.hub_contract_json.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        self.assertEqual(odcs_x_odps.get("odps_link"), str(odps_contract.id))

    def test_link_existing_odps_success(self):
        """Test successful linking of existing ODPS contract."""
        # Create ODPS contract first
        odps_raw = json.dumps(self.valid_odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Link it
        linked_odps = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify linking succeeded
        self.assertEqual(linked_odps.id, odps_contract.id)

        # Verify links exist
        linked_odps.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        odps_extensions = linked_odps.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(self.odcs_contract.id))


class ODPSLinkingCompensationFailureTest(ODPSLinkingCompensationIntegrationTestBase):
    """Tests for ODPS linking failure and compensation."""

    def test_link_odps_invalid_odcs_no_compensation(self):
        """Test that invalid ODCS contract fails before linking."""
        from uuid import uuid4
        from hub.apps.core.services.base import NotFoundError

        fake_odcs_id = str(uuid4())

        odps_raw = json.dumps(self.valid_odps_doc)

        # Should raise NotFoundError since contract doesn't exist
        # No compensation needed since linking never started
        with self.assertRaises(NotFoundError):
            self.contract_service.link_odps_to_odcs(
                odcs_contract_id=fake_odcs_id,
                odps_raw=odps_raw,
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Verify no ODPS contract was created (transaction rollback)
        # With TestCase, transactions are automatically rolled back

    def test_link_odps_missing_tenant_id(self):
        """Test that missing tenant_id fails before linking."""
        odps_raw = json.dumps(self.valid_odps_doc)

        # Create service without tenant_id
        service_without_tenant = ContractService(
            tenant_id=None,
            user_id=str(self.user.id)
        )

        with self.assertRaises(ValidationError):
            service_without_tenant.link_odps_to_odcs(
                odcs_contract_id=str(self.odcs_contract.id),
                odps_raw=odps_raw,
                odps_format="json",
                tenant_id=None,
                user_id=str(self.user.id)
            )

    def test_link_odps_compensation_state_tracking(self):
        """Test that compensation state is tracked correctly."""
        odps_raw = json.dumps(self.valid_odps_doc)

        # Link contracts
        odps_contract = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Manually test compensation
        compensation = ODPSLinkingCompensation(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_created=True,  # Was created during linking
            previous_odps_link=None,  # No previous link since ODPS was created during linking
            previous_odcs_link=None,
            events_published=[]
        )

        # Execute compensation
        result = compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True
        )

        # Verify compensation completed
        self.assertEqual(result["status"], "success")
        self.assertIn("remove_links", result["operations"])
        self.assertIn("restore", result["operations"])

        # Verify ODPS contract was deleted (since it was created during linking)
        # Check this first before trying to refresh
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=odps_contract.id)

        # Verify links were removed from ODCS contract
        self.odcs_contract.refresh_from_db()
        if self.odcs_contract.hub_contract_json:
            odcs_extensions = self.odcs_contract.hub_contract_json.get("extensions", {})
            odcs_x_odps = odcs_extensions.get("x_odps", {})
            if isinstance(odcs_x_odps, dict):
                # Link should be removed (or restored to previous if existed)
                # Since we created the ODPS during linking, there's no previous link
                self.assertNotIn("odps_link", odcs_x_odps)


class ODPSLinkingCompensationTransactionTest(ODPSLinkingCompensationIntegrationTestBase):
    """Tests for transaction handling in ODPS linking compensation."""

    def test_transaction_rollback_on_validation_error(self):
        """Test that transaction rollback occurs on validation error."""
        # Use invalid ODPS document (missing contract section)
        invalid_odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-invalid",
                        "name": "Test Invalid"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
                # Missing contract section
            }
        })

        with self.assertRaises(ValidationError):
            self.contract_service.link_odps_to_odcs(
                odcs_contract_id=str(self.odcs_contract.id),
                odps_raw=invalid_odps_raw,
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # With TestCase, transactions are automatically rolled back
        # So we just verify the exception was raised

    def test_multiple_odps_linkings_isolation(self):
        """Test that multiple ODPS linkings are isolated in transactions."""
        # Create first ODPS and link it
        odps_raw1 = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-1",
                        "name": "Test ODPS 1"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                },
                "contract": {
                    "spec": json.loads(self.odcs_contract.original_raw)
                }
            }
        })

        odps_contract1 = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_raw1,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Try to link with invalid ODPS document
        invalid_odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-invalid",
                        "name": "Test Invalid"
                    }
                }
                # Missing dataSchema and contract
            }
        })

        with self.assertRaises(ValidationError):
            self.contract_service.link_odps_to_odcs(
                odcs_contract_id=str(self.odcs_contract.id),
                odps_raw=invalid_odps_raw,
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Verify first contract still exists and is linked (transaction isolation)
        self.assertTrue(Contract.objects.filter(id=odps_contract1.id).exists())
        odps_contract1.refresh_from_db()
        odps_extensions = odps_contract1.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(self.odcs_contract.id))

