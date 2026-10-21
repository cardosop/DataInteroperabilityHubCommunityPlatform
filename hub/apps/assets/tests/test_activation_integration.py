"""
Integration tests for asset activation flow.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
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
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetActivationIntegrationTest(TestCase):
    """Integration tests for complete asset activation flow"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        # Active subscription required so TenantSuspensionMiddleware allows writes.
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user with DATA_PROVIDER role (required for asset create/update)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)

        self.client.force_authenticate(user=self.user)

    def test_complete_activation_flow_with_dataset(self):
        """Test complete activation flow: create asset → attach contract → attach dataset → run DQ/compliance → activate"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "test-asset", "name": "Test Asset", "description": "Test description"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        # Get asset from response
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Step 2: Create and attach contract
        Contract.objects.create(
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

        # Step 3: Create file and dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        # Step 4: Simulate DQ and compliance runs (set statuses directly)
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()

        # Step 5: Activate asset
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

    def test_complete_activation_flow_with_dataset_returns_active_status(self):
        """Test complete activation flow returns ACTIVE status in response."""
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "test-asset", "name": "Test Asset", "description": "Test description"},
            format="json",
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        Contract.objects.create(
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

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()

        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)

    def test_complete_activation_flow_with_dataset_updates_database(self):
        """Test complete activation flow updates database status to ACTIVE."""
        self.client.force_authenticate(user=self.user)

        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "test-asset", "name": "Test Asset", "description": "Test description"},
            format="json",
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        Contract.objects.create(
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

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()

        self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_activation_blocked_when_allowed_to_store_false(self):
        """5.4.3: When related compliance run has allowed_to_store=False, activation returns 403 with code compliance_not_allowed_to_store; real DB and flow."""
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "blocked-asset", "name": "Blocked Asset", "description": "Test"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "schema": {"fields": []}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=asset.id,
            details_json={"scan_mode": "internal"},
            created_by=self.user,
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            allowed_to_store=False,
            overall_status="FAIL",
        )

        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(activate_response.data.get("code"), "compliance_not_allowed_to_store")
        self.assertIn("compliance", activate_response.data.get("error", "").lower())

    def test_activation_succeeds_when_allowed_to_store_true(self):
        """5.4.3: When related compliance run has allowed_to_store=True, activation succeeds; real DB and flow."""
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "allowed-asset", "name": "Allowed Asset", "description": "Test"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "schema": {"fields": []}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=asset.id,
            details_json={"scan_mode": "internal"},
            created_by=self.user,
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            allowed_to_store=True,
            overall_status="PASS",
        )

        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data.get("status"), AssetStatus.ACTIVE)

    def test_activation_flow_contract_only(self):
        """Test activation flow for contract-only asset (no dataset)"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "contract-only-asset",
                "name": "Contract Only Asset",
                "description": "Asset with contract but no dataset",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Step 2: Create and attach contract
        Contract.objects.create(
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

        # Step 3: Activate asset (no dataset required)
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertFalse(asset.datasets.exists())  # No dataset

    def test_activation_blocked_until_all_requirements_met(self):
        """Test that activation is blocked until all requirements are met"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/", {"key": "test-asset", "name": "Test Asset"}, format="json"
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Step 2: Try to activate without contract (should fail)
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(activate_response.data["code"], "ASSET_ACTIVATION_BLOCKED")

        # Step 3: Add contract with invalid validation (should still fail)
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

        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)

        # Step 4: Fix contract validation (should succeed for contract-only)
        contract.validation_status = ValidationStatus.VALID
        contract.save()

        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)

    def test_activation_with_warning_statuses_allowed(self):
        """Test that WARN statuses for DQ and compliance are allowed"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"warn-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            dq_status=DQStatus.WARN,
            compliance_status=ComplianceStatus.WARN,
            created_by=self.user,
        )

        # Create valid contract
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            created_by=self.user,
        )

        # Create dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=file_obj, format="CSV", created_by=self.user
        )

        # Activate should succeed with WARN statuses
        activate_response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)

    # ========== EDGE CASES ==========

    def test_activation_integration_edge_case_concurrent_activation(self):
        """Test concurrent activation attempts (edge case)"""
        # Create asset
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "concurrent-asset", "name": "Concurrent Asset"},
            format="json",
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Create contract
        Contract.objects.create(
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

        # Increment version to simulate concurrent modification
        asset.increment_version()

        # Try to activate with old version
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/",
            {"version": 1},
            format="json",  # Old version
        )

        # Version mismatch should return 409 Conflict
        self.assertEqual(activate_response.status_code, status.HTTP_409_CONFLICT)

    def test_activation_integration_edge_case_partial_requirements(self):
        """Test activation with WARNING_ONLY contract validation and no dataset succeeds.

        Business rules allow WARNING_ONLY validation_status and NORMALIZED_OK
        normalization_status. Since there is no dataset, DQ/compliance checks
        are skipped. This is a contract-only asset, so activation should succeed.
        """
        # Create asset
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": f"partial-asset-{uuid.uuid4().hex[:8]}", "name": "Partial Asset"},
            format="json",
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Create contract with WARNING_ONLY validation (allowed by business rules)
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Contract-only asset with WARNING_ONLY validation should activate successfully
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

    # ========== ERROR HANDLING ==========

    def test_activation_integration_contract_only_asset_succeeds(self):
        """Test that a contract-only asset (no dataset) with valid contract activates successfully"""
        # Create asset
        create_response = self.client.post(
            "/api/v1/assets/", {"key": "error-asset", "name": "Error Asset"}, format="json"
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Create valid contract
        Contract.objects.create(
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

        # Contract-only asset with VALID contract should activate successfully
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

    def test_activation_integration_error_handling_missing_contract(self):
        """Test error handling when contract is missing"""
        # Create asset
        create_response = self.client.post(
            "/api/v1/assets/",
            {"key": "no-contract-asset", "name": "No Contract Asset"},
            format="json",
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)

        # Don't create contract

        # Should handle missing contract gracefully
        activate_response = self.client.post(
            f"/api/v1/assets/{asset_id}/activate/", {"version": asset.version}, format="json"
        )

        # Should return error response, not exception
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(activate_response.data["code"], "ASSET_ACTIVATION_BLOCKED")
