"""
Unit tests for asset activation requirements.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetActivationTest(TestCase):
    """Test asset activation requirements"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        # Active subscription required so TenantSuspensionMiddleware allows writes.
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_activate_asset_with_all_requirements_met(self):
        """Test activating asset with all requirements met"""
        self.client.force_authenticate(user=self.user)

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Activate asset
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_activate_asset_with_all_requirements_met_returns_active_status(self):
        """Test activating asset with all requirements met returns ACTIVE status in response."""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.data["status"], AssetStatus.ACTIVE)

    def test_activate_asset_with_all_requirements_met_updates_database(self):
        """Test activating asset with all requirements met updates database status."""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_activate_asset_without_valid_contract_fails(self):
        """Test that activation fails without valid contract"""
        self.client.force_authenticate(user=self.user)

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Try to activate without contract
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("details", response.data)
        self.assertIn("ACTIVE contract", response.data["details"][0])

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged

    def test_activate_asset_with_invalid_contract_validation_fails(self):
        """Test that activation fails with invalid contract validation status"""
        self.client.force_authenticate(user=self.user)

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Create contract with invalid validation status
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("validation_status", response.data["details"][0])

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged

    def test_activate_asset_with_failed_dq_fails(self):
        """Test that activation fails with FAIL DQ status"""
        self.client.force_authenticate(user=self.user)

        # Create asset with FAIL DQ status
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Create dataset (DQ check only applies if dataset exists)
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("dq_status", response.data["details"][0])

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged

    def test_activate_asset_with_failed_compliance_fails(self):
        """Test that activation fails with FAIL compliance status"""
        self.client.force_authenticate(user=self.user)

        # Create asset with FAIL compliance status
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.FAIL,
            created_by=self.user,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Create dataset (compliance check only applies if dataset exists)
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("compliance_status", response.data["details"][0])

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged

    def test_activate_contract_only_asset(self):
        """Test that contract-only assets (no dataset) can be activated"""
        self.client.force_authenticate(user=self.user)

        # Create asset without dataset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            # DQ and compliance status are UNKNOWN (not checked for contract-only assets)
            created_by=self.user,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Verify no dataset exists
        self.assertFalse(asset.datasets.exists())

        # Activate asset (should succeed for contract-only)
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AssetStatus.ACTIVE)

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_activate_asset_optimistic_locking(self):
        """Test that activation requires correct version for optimistic locking"""
        self.client.force_authenticate(user=self.user)

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Simulate concurrent update: increment version
        asset.increment_version()

        # Try to activate with old version
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": 1}, format="json"  # Old version
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ASSET_CONCURRENT_MODIFICATION")

    def test_activate_already_active_asset_fails(self):
        """Test that activating an already active asset fails"""
        self.client.force_authenticate(user=self.user)

        # Create asset that's already active
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to activate again
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ALREADY_ACTIVE")

    def test_activate_retired_asset_fails(self):
        """Test that retired assets cannot be reactivated"""
        self.client.force_authenticate(user=self.user)

        # Create retired asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.RETIRED,
            created_by=self.user,
        )

        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_RETIRED")

    # ========== EDGE CASES ==========

    def test_activate_asset_edge_case_already_active_same_version(self):
        """Test activating already active asset with same version (edge case)"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to activate again with same version
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        # Should fail with already active error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ALREADY_ACTIVE")

    def test_activate_asset_edge_case_draft_to_active_transition(self):
        """Test DRAFT to ACTIVE transition (edge case)"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Activate from DRAFT
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_activate_asset_edge_case_version_mismatch(self):
        """Test activation with version mismatch (edge case)"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Use wrong version
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": 999}, format="json"  # Wrong version
        )

        # Should fail with version mismatch
        self.assertIn(response.status_code, [status.HTTP_409_CONFLICT, status.HTTP_400_BAD_REQUEST])

    # ========== ERROR HANDLING ==========

    def test_activate_asset_without_contract_returns_400(self):
        """Test that activating an asset without a valid ACTIVE contract returns 400"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user,
        )

        # No contract created -- activation should be blocked
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activate_asset_error_handling_missing_contract(self):
        """Test error handling when contract is missing"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Don't create contract

        # Should handle missing contract gracefully
        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        # Should return error response, not exception
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_ensure_e2e_activation_prerequisites_sets_dq_compliance_when_dataset_exists(self):
        """
        E2E helper sets dq_status and compliance_status to PASS when asset has dataset.
        Activation requires PASS/WARN when dataset exists; defaults are UNKNOWN.
        """
        from django.test import override_settings

        with override_settings(ENVIRONMENT="test"):
            # Use a test-local email to avoid colliding with E2E users pre-seeded
            # into the shared DB by ensure_e2e_user_roles.
            e2e_user = User.objects.create_user(
                email=f"e2e_test_activation_unit-{uuid.uuid4().hex[:8]}@example.com",
                password="testpass123",
                tenant=self.tenant,
                status=UserStatus.ACTIVE,
            )
            self.client.force_authenticate(user=e2e_user)

            asset = Asset.objects.create(
                tenant=self.tenant,
                key="e2e-asset",
                name="E2E Asset",
                dq_status=DQStatus.UNKNOWN,
                compliance_status=ComplianceStatus.UNKNOWN,
                created_by=e2e_user,
            )

            file_obj = File.objects.create(
                tenant=self.tenant,
                name="test.csv",
                content_type="text/csv",
                size=1024,
                storage_path="test/path/file.csv",
                status=FileStatus.ACTIVE,
                created_by=e2e_user,
            )

            Dataset.objects.create(
                tenant=self.tenant,
                asset=asset,
                file=file_obj,
                format="CSV",
                created_by=e2e_user,
            )

            response = self.client.post(
                f"/api/v1/assets/{asset.id}/ensure-e2e-activation-prerequisites/",
                {},
                format="json",
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)

            asset.refresh_from_db()
            self.assertEqual(asset.dq_status, DQStatus.PASS)
            self.assertEqual(asset.compliance_status, ComplianceStatus.PASS)

            # Activation should now succeed
            act_response = self.client.post(
                f"/api/v1/assets/{asset.id}/activate/",
                {"version": asset.version},
                format="json",
            )
            self.assertEqual(act_response.status_code, status.HTTP_200_OK)

    def test_ensure_e2e_activation_prerequisites_unblocks_latest_compliance_run(self):
        """
        5.4.3: activation returns 403 when latest ComplianceRun does not allow storage.
        The E2E helper must repair a FAILED / allowed_to_store=False run after real async compliance.
        """
        from django.test import override_settings

        with override_settings(ENVIRONMENT="test"):
            e2e_user = User.objects.create_user(
                email=f"e2e_compliance_unblock-{uuid.uuid4().hex[:8]}@example.com",
                password="testpass123",
                tenant=self.tenant,
                status=UserStatus.ACTIVE,
            )
            self.client.force_authenticate(user=e2e_user)

            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"e2e-comp-{uuid.uuid4().hex[:8]}",
                name="E2E Asset",
                dq_status=DQStatus.PASS,
                compliance_status=ComplianceStatus.PASS,
                created_by=e2e_user,
            )

            Contract.objects.create(
                tenant=self.tenant,
                asset=asset,
                version=1,
                status=ContractStatus.ACTIVE,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{"id": "x", "schema": {"fields": []}}',
                validation_status=ValidationStatus.VALID,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=e2e_user,
            )

            file_obj = File.objects.create(
                tenant=self.tenant,
                name="test.csv",
                content_type="text/csv",
                size=1024,
                storage_path="test/path/file.csv",
                status=FileStatus.ACTIVE,
                created_by=e2e_user,
            )

            dataset = Dataset.objects.create(
                tenant=self.tenant,
                asset=asset,
                file=file_obj,
                format="CSV",
                created_by=e2e_user,
            )

            job = create_job(
                tenant=self.tenant,
                user=e2e_user,
                job_type=JobType.COMPLIANCE_RUN,
                resource_type="DATASET",
                resource_id=str(dataset.id),
                executed_by_prefect=True,
            )
            ComplianceRun.objects.create(
                tenant=self.tenant,
                asset=asset,
                dataset=dataset,
                job=job,
                status=ComplianceRunStatus.FAILED,
                allowed_to_store=False,
                completed_at=timezone.now(),
            )

            blocked = self.client.post(
                f"/api/v1/assets/{asset.id}/activate/",
                {"version": asset.version},
                format="json",
            )
            self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(blocked.data.get("code"), "compliance_not_allowed_to_store")

            helper = self.client.post(
                f"/api/v1/assets/{asset.id}/ensure-e2e-activation-prerequisites/",
                {},
                format="json",
            )
            self.assertEqual(helper.status_code, status.HTTP_200_OK)

            act_response = self.client.post(
                f"/api/v1/assets/{asset.id}/activate/",
                {"version": asset.version},
                format="json",
            )
            self.assertEqual(act_response.status_code, status.HTTP_200_OK)

    def test_ensure_e2e_activation_prerequisites_idempotent_syncs_dq_when_active_contract_exists(self):
        """
        When an ACTIVE VALID+NORMALIZED contract already exists (e.g. ODPS journey), the helper
        must not create a second contract; it should only set dq_status / compliance_status
        when a dataset is present so can_activate() passes.
        """
        from django.test import override_settings

        with override_settings(ENVIRONMENT="test"):
            e2e_user = User.objects.create_user(
                email=f"e2e_idempotent-{uuid.uuid4().hex[:8]}@example.com",
                password="testpass123",
                tenant=self.tenant,
                status=UserStatus.ACTIVE,
            )
            self.client.force_authenticate(user=e2e_user)

            asset = Asset.objects.create(
                tenant=self.tenant,
                key="e2e-idem-asset",
                name="E2E Idempotent Asset",
                dq_status=DQStatus.UNKNOWN,
                compliance_status=ComplianceStatus.UNKNOWN,
                created_by=e2e_user,
            )

            Contract.objects.create(
                tenant=self.tenant,
                asset=asset,
                version=1,
                status=ContractStatus.ACTIVE,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.0",
                original_format=OriginalFormat.JSON,
                original_raw='{"id": "x", "schema": {"fields": []}}',
                validation_status=ValidationStatus.VALID,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=e2e_user,
            )

            file_obj = File.objects.create(
                tenant=self.tenant,
                name="test.csv",
                content_type="text/csv",
                size=1024,
                storage_path="test/path/file.csv",
                status=FileStatus.ACTIVE,
                created_by=e2e_user,
            )

            Dataset.objects.create(
                tenant=self.tenant,
                asset=asset,
                file=file_obj,
                format="CSV",
                created_by=e2e_user,
            )

            contract_count_before = asset.contracts.count()
            response = self.client.post(
                f"/api/v1/assets/{asset.id}/ensure-e2e-activation-prerequisites/",
                {},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(asset.contracts.count(), contract_count_before)

            asset.refresh_from_db()
            self.assertEqual(asset.dq_status, DQStatus.PASS)
            self.assertEqual(asset.compliance_status, ComplianceStatus.PASS)

            act_response = self.client.post(
                f"/api/v1/assets/{asset.id}/activate/",
                {"version": asset.version},
                format="json",
            )
            self.assertEqual(act_response.status_code, status.HTTP_200_OK)
