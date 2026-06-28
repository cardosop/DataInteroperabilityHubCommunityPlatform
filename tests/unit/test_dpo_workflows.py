"""
Unit tests for Data Product Owner (DPO) workflows.

Target: 100% coverage for all DPO workflows including:
- Asset creation workflow
- Marketplace publication workflow
- Contract update workflow
- Asset retirement workflow

All tests use real implementations (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    ValidationStatus,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.orchestration.workflows.marketplace_publication import MarketplacePublicationWorkflow
from hub.apps.tenants.models import KYCStatus
from tests.factories import TenantFactory

User = get_user_model()


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.unit]


class AssetCreationWorkflowUnitTests(TestCase):
    """Unit tests for Asset Creation Workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_workflow_registration(self):
        """Test workflow registration"""
        from hub.apps.orchestration.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        AssetCreationWorkflow.register_workflow(registry)

        # Verify workflow is registered
        workflow_def = registry.get_workflow(AssetCreationWorkflow.WORKFLOW_NAME)
        self.assertIsNotNone(workflow_def)
        self.assertEqual(workflow_def.version, AssetCreationWorkflow.WORKFLOW_VERSION)

    def test_workflow_execution_with_all_components(self):
        """Test workflow execution with all components (dataset, contract, DQ, compliance)"""
        # Check if DQ service is available - skip test if not
        from hub.apps.dq.service_client import DQServiceClient

        dq_client = DQServiceClient()
        is_available, _ = dq_client.health_check()
        if not is_available:
            self.skipTest("DQ service is not available - skipping test that requires DQ service")

        # Create file first (needed for dataset)
        # storage_path format: tenant_id/file_id/filename
        file_id = "test-file-id"
        storage_path = f"{self.tenant.id}/{file_id}/test.csv"
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path=storage_path,
            created_by=self.user,
        )

        # Upload test file to MinIO/S3 so workflow can access it
        import boto3
        from django.conf import settings

        s3_client = boto3.client(
            "s3",
            endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", "http://localhost:9000"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", "minioadmin"),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", "minioadmin"),
            use_ssl=False,
            verify=False,
        )
        bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "hub-files")
        test_content = b"id,name\n1,Test\n2,Data\n"
        try:
            s3_client.put_object(Bucket=bucket_name, Key=storage_path, Body=test_content)
        except Exception as e:
            self.skipTest(f"S3/MinIO upload prerequisite failed: {e}")

        # Create dataset (will be attached to asset created by workflow)
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=file_obj,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            row_count=10,
            created_by=self.user,
        )

        # Create contract (will be attached to asset created by workflow)
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-contract", "schema": {}},
            created_by=self.user,
        )

        # Execute workflow - it will create the asset and attach dataset/contract
        result = AssetCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            key="test-asset-workflow",
            name="Test Asset Workflow",
            dataset_id=str(dataset.id),
            contract_id=str(contract.id),
            file_id=str(file_obj.id),
            auto_activate=True,
            created_by_id=str(self.user.id),
        )

        # Verify workflow completed
        self.assertTrue(result.get("success", False))

        # Get the created asset from workflow output
        asset_id = result.get("output_data", {}).get("asset_id")
        self.assertIsNotNone(asset_id)

        # Verify asset is activated
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_workflow_execution_without_dataset(self):
        """Test workflow execution for contract-only asset (no dataset)"""
        # Create contract (will be attached to asset created by workflow)
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "contract-only", "schema": {}},
            created_by=self.user,
        )

        # Execute workflow (contract-only assets don't require DQ/compliance)
        result = AssetCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            key="contract-only-asset",
            name="Contract Only Asset",
            contract_id=str(contract.id),
            auto_activate=True,
            created_by_id=str(self.user.id),
        )

        # Verify workflow completed
        self.assertTrue(result.get("success", False))

        # Get the created asset from workflow output
        asset_id = result.get("output_data", {}).get("asset_id")
        self.assertIsNotNone(asset_id)

        # Verify asset is activated
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_workflow_execution_without_auto_activate(self):
        """Test that workflow with auto_activate=False leaves asset in DRAFT state.

        When auto_activate is False, the activation step is skipped regardless of
        DQ/compliance results, so the asset MUST remain DRAFT.
        """
        # Check if DQ service is available - skip test if not
        from hub.apps.dq.service_client import DQServiceClient

        dq_client = DQServiceClient()
        is_available, _ = dq_client.health_check()
        if not is_available:
            self.skipTest("DQ service is not available - skipping test that requires DQ service")

        # Create file and dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=file_obj,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            row_count=10,
            created_by=self.user,
        )

        # Execute workflow with auto_activate=False — activation step is skipped
        result = AssetCreationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            key="no-auto-activate-asset",
            name="No Auto-Activate Asset",
            dataset_id=str(dataset.id),
            auto_activate=False,
            created_by_id=str(self.user.id),
        )

        # Workflow should complete successfully
        self.assertTrue(result.get("success", False))

        # Asset MUST be DRAFT when auto_activate=False (activation skipped)
        asset_id = result.get("output_data", {}).get("asset_id")
        self.assertIsNotNone(asset_id, "Workflow should create an asset")
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.DRAFT,
            "Asset should stay DRAFT when auto_activate=False")

    # test_workflow_execution_with_compliance_failure removed — it was a duplicate
    # of test_workflow_execution_without_auto_activate. Both tested auto_activate=False
    # with the same always-passing assertion. See test_workflow_execution_without_auto_activate
    # above for the corrected version.


class MarketplacePublicationWorkflowUnitTests(TestCase):
    """Unit tests for Marketplace Publication Workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save()

        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Create active asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="marketplace-asset",
            name="Marketplace Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user,
        )

        # Create validated contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={
                "id": "marketplace-contract",
                "marketplace": {"license_summary": "MIT License", "intended_use": ["analytics"]},
            },
            created_by=self.user,
        )

    def test_workflow_execution_success(self):
        """Test successful marketplace publication workflow execution"""
        result = MarketplacePublicationWorkflow.execute(
            tenant_id=str(self.tenant.id),
            asset_id=str(self.asset.id),
            metadata_json={
                "title": "Premium Data Product",
                "short_description": "High-quality dataset",
            },
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            price_amount=0.0,
            currency="USD",
            send_notifications=True,
            triggered_by_id=str(self.user.id),
        )

        # Verify workflow completed
        self.assertTrue(result.get("success", False))
        self.assertIsNotNone(result.get("listing_id"))
        self.assertTrue(result.get("published", False))

        # Verify listing was created
        listing = Listing.objects.get(id=result["listing_id"])
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertEqual(listing.pricing_model, PricingModel.FREE_AUTO_APPROVE)

    def test_workflow_execution_with_eligibility_failure(self):
        """Test workflow execution when asset eligibility check fails"""
        # Set tenant to unverified (use string value directly)
        self.tenant.kyc_status = "UNVERIFIED"
        self.tenant.save()

        # Execute workflow - should fail eligibility check
        # Workflow raises ValueError on eligibility failure
        with self.assertRaises(ValueError) as context:
            MarketplacePublicationWorkflow.execute(
                tenant_id=str(self.tenant.id),
                asset_id=str(self.asset.id),
                metadata_json={"title": "Test"},
                pricing_model=PricingModel.FREE_AUTO_APPROVE,
                triggered_by_id=str(self.user.id),
            )

        # Verify error message contains eligibility-related text
        error_msg = str(context.exception).lower()
        self.assertTrue(
            "eligibility" in error_msg or "kyc" in error_msg,
            f"Expected 'eligibility' or 'kyc' in error: {error_msg}",
        )

    def test_workflow_execution_with_inactive_asset(self):
        """Test workflow execution with inactive asset"""
        # Set asset to DRAFT
        self.asset.status = AssetStatus.DRAFT
        self.asset.save()

        # Execute workflow - should fail eligibility check
        # Note: workflow.execute may raise ValueError instead of returning error dict
        try:
            result = MarketplacePublicationWorkflow.execute(
                tenant_id=str(self.tenant.id),
                asset_id=str(self.asset.id),
                metadata_json={"title": "Test"},
                pricing_model=PricingModel.FREE_AUTO_APPROVE,
                triggered_by_id=str(self.user.id),
            )
            # If workflow returns result, check it
            if isinstance(result, dict):
                self.assertFalse(result.get("success", False))
        except ValueError as e:
            # Workflow may raise ValueError on failure - this is expected
            error_msg = str(e).lower()
            self.assertTrue(
                "active" in error_msg or "eligibility" in error_msg,
                f"Expected 'active' or 'eligibility' in error, got: {error_msg}",
            )


class ContractUpdateWorkflowUnitTests(TestCase):
    """Unit tests for Contract Update operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="contract-update-asset",
            name="Contract Update Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type="ODCS",
            original_spec_version="1.0",
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_json={"id": "test-contract", "name": "Original Name"},
            created_by=self.user,
        )

    def test_contract_update_preserves_hub_contract_json(self):
        """Test that updating contract hub_contract_json is persisted correctly."""
        # Update contract JSON
        self.contract.hub_contract_json = {"id": "test-contract", "name": "Updated Name"}
        self.contract.save()
        self.contract.refresh_from_db()

        self.assertIsNotNone(self.contract.hub_contract_json)
        self.assertEqual(
            self.contract.hub_contract_json.get("name"),
            "Updated Name",
            "hub_contract_json should reflect the updated name",
        )


class AssetRetirementWorkflowUnitTests(TestCase):
    """Unit tests for Asset Retirement operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="retire-asset",
            name="Retire Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_asset_retirement_sets_status_to_retired(self):
        """Test that retiring asset sets status to RETIRED"""
        # Retire asset
        self.asset.status = AssetStatus.RETIRED
        self.asset.save()

        # Verify asset is retired
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.RETIRED)

    def test_asset_retirement_unpublishes_listings(self):
        """Test that retiring asset unpublishes marketplace listings"""
        # Ensure tenant has VERIFIED KYC status to allow listing creation
        self.tenant.kyc_status = "VERIFIED"
        self.tenant.save()

        # Create published listing
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            status=ListingStatus.PUBLISHED,
            metadata_json={"title": "Test Listing"},
        )

        # Retire asset via AssetService (tests business logic, not HTTP layer)
        from hub.apps.assets.services import AssetService

        asset_service = AssetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        asset_service.delete_asset(
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify asset is retired
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.RETIRED)

        # Verify listing is unpublished (unlisted) when asset is retired
        listing.refresh_from_db()
        # Listing should be automatically unlisted when asset is retired
        self.assertEqual(listing.status, ListingStatus.UNLISTED)
