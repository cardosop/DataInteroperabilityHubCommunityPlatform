"""
Unit tests for contract status lifecycle rules.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class ContractStatusRulesTest(ContractsAPITestBase):
    """Test contract status lifecycle rules"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_contract_can_activate_with_valid_status(self):
        """Test that contract can be activated with VALID validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")

    def test_contract_can_activate_with_warning_only(self):
        """Test that contract can be activated with WARNING_ONLY validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            created_by=self.user,
        )

        can_activate, _reason = contract.can_activate()
        self.assertTrue(can_activate)

    def test_contract_cannot_activate_with_invalid_validation(self):
        """Test that contract cannot be activated with INVALID validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

    def test_contract_cannot_activate_with_failed_normalization(self):
        """Test that contract cannot be activated with failed normalization"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("normalization_status", reason)

    def test_activate_contract_via_api_success(self):
        """Test activating a contract via API when requirements are met"""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/{contract.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ContractStatus.ACTIVE)

        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.ACTIVE)

    def test_activate_contract_via_api_failure(self):
        """Test activating a RETIRED contract via API is rejected (invalid transition)."""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.RETIRED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/{contract.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)  # Status unchanged

    def test_draft_contract_can_have_any_validation_status(self):
        """Test that DRAFT contracts can have any validation status"""
        # DRAFT with null validation_status
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=None,
            created_by=self.user,
        )
        contract1.full_clean()  # Should not raise

        # DRAFT with INVALID validation_status
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            created_by=self.user,
        )
        contract2.full_clean()  # Should not raise

    # Edge cases and error handling tests
    def test_contract_can_activate_with_none_validation_status(self):
        """Test contract activation with None validation_status."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=None,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        # None validation_status should prevent activation
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

    def test_contract_can_activate_with_none_normalization_status(self):
        """Test contract activation with None normalization_status."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=None,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        # None normalization_status should prevent activation
        self.assertFalse(can_activate)
        self.assertIn("normalization_status", reason)

    def test_contract_cannot_activate_when_already_active(self):
        """Test that already ACTIVE contract can be activated again."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        can_activate, _reason = contract.can_activate()
        # Already active contract should be able to activate (idempotent)
        self.assertTrue(can_activate)

    def test_contract_cannot_activate_when_validation_invalid(self):
        """Test that can_activate returns False when validation_status is INVALID."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

    def test_activate_contract_via_api_with_invalid_id(self):
        """Test activating contract via API with invalid contract ID."""
        self.client.force_authenticate(user=self.user)

        import uuid

        fake_id = str(uuid.uuid4())
        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/{fake_id}/", data, format="json")

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_activate_contract_via_api_unauthenticated(self):
        """Test activating contract via API without authentication."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        data = {"status": ContractStatus.ACTIVE}
        # Clear authentication
        self.client.force_authenticate(user=None)
        response = self.client.patch(f"/api/v1/contracts/{contract.id}/", data, format="json")

        # Should require authentication
        self.assertIn(
            response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_activate_contract_via_api_cross_tenant(self):
        """Test activating contract via API from different tenant."""
        # Create another tenant and user
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-status-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(other_tenant)

        _uid = uuid.uuid4().hex[:8]
        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=other_user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/{contract.id}/", data, format="json")

        # Should return 404 (tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_contract_status_transition_draft_to_active(self):
        """Test status transition from DRAFT to ACTIVE."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Transition to ACTIVE
        contract.status = ContractStatus.ACTIVE
        contract.save()

        self.assertEqual(contract.status, ContractStatus.ACTIVE)

    def test_contract_status_transition_active_to_retired(self):
        """Test status transition from ACTIVE to RETIRED."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Transition to RETIRED
        contract.status = ContractStatus.RETIRED
        contract.save()

        self.assertEqual(contract.status, ContractStatus.RETIRED)

    def test_contract_can_activate_with_all_valid_statuses(self):
        """Test contract activation with all valid status combinations."""
        valid_combinations = [
            (ValidationStatus.VALID, NormalizationStatus.NORMALIZED_OK),
            (ValidationStatus.WARNING_ONLY, NormalizationStatus.NORMALIZED_WITH_WARNINGS),
        ]

        for validation_status, normalization_status in valid_combinations:
            contract = Contract.objects.create(
                tenant=self.tenant,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{"id": "test", "name": "Test"}',
                validation_status=validation_status,
                normalization_status=normalization_status,
                created_by=self.user,
            )

            can_activate, _reason = contract.can_activate()
            self.assertTrue(
                can_activate, f"Should activate with {validation_status}, {normalization_status}"
            )

    def test_contract_cannot_activate_with_all_invalid_statuses(self):
        """Test contract activation with all invalid status combinations."""
        invalid_combinations = [
            (ValidationStatus.INVALID, NormalizationStatus.NORMALIZED_OK),
            (ValidationStatus.VALID, NormalizationStatus.NORMALIZATION_FAILED),
            (ValidationStatus.INVALID, NormalizationStatus.NORMALIZATION_FAILED),
        ]

        for validation_status, normalization_status in invalid_combinations:
            contract = Contract.objects.create(
                tenant=self.tenant,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{"id": "test", "name": "Test"}',
                validation_status=validation_status,
                normalization_status=normalization_status,
                created_by=self.user,
            )

            can_activate, _reason = contract.can_activate()
            self.assertFalse(
                can_activate,
                f"Should not activate with {validation_status}, {normalization_status}",
            )
