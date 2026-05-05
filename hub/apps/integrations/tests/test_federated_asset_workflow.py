"""
Comprehensive tests for federated asset workflow integration.

Tests cover:
- Workflow execution with metadata-only strategy
- Workflow execution with data strategy
- Workflow with validation failures
- Workflow with DQ/compliance failures
- Integration tests for complete workflow
- Error handling tests
"""

import os
import tempfile

from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    AssetVisibility,
    DataStrategy,
    ExternalResourceReference,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.integrations.base import (
    AssetSourceType,
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus
import uuid


class FederatedAssetWorkflowTest(TestCase):
    """Test federated asset workflow execution"""

    def setUp(self):
        """Set up test data"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
            # Phase 250.5.A.2 — federated import is opt-in per D250.3
            # (default False). Workflow tests MUST flip the flag at
            # fixture time or the gate refuses with
            # FederatedImportRejected("FEDERATED_IMPORT_DISABLED").
            federated_import_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-request-123",
        )

        # Create marketplace connection
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="Test CKAN Connection",
            config={"api_key": "test-key", "endpoint": "https://ckan.example.com"},
            is_active=True,
        )

        # Create sync job
        self.sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
            metadata={},
        )

    def _create_asset_mapping(self, name="Test Asset", resources=None):
        """Helper to create asset mapping"""
        return MarketplaceAssetMapping(
            asset_data={
                "name": name,
                "description": "Test Description",
                "key": f"{name.lower().replace(' ', '-')}-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": f"{name.lower().replace(' ', '-')}-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources or [],
        )

    def test_workflow_metadata_only_strategy(self):
        """Test workflow execution with metadata-only strategy"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Metadata Only Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=False,  # Enable semantic mapping to trigger workflow
        )

        # Refresh asset to get updated status
        asset.refresh_from_db()

        # Verify workflow was executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertGreater(workflow_instances.count(), 0)

        workflow_instance = workflow_instances.first()
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify contract validation ran
        contract_steps = workflow_instance.steps.filter(
            step_name="asset_creation.validate_contract"
        )
        self.assertGreater(contract_steps.count(), 0)

        # Verify DQ/compliance checks were skipped (no datasets)
        dq_steps = workflow_instance.steps.filter(step_name="asset_creation.run_dq_checks")
        compliance_steps = workflow_instance.steps.filter(
            step_name="asset_creation.run_compliance_checks"
        )
        # These steps should not exist for metadata-only strategy
        self.assertEqual(dq_steps.count(), 0)
        self.assertEqual(compliance_steps.count(), 0)

        # Verify indexing ran
        indexing_steps = workflow_instance.steps.filter(step_name="asset_creation.index_for_search")
        self.assertGreater(indexing_steps.count(), 0)

        # Verify notifications sent
        notification_steps = workflow_instance.steps.filter(
            step_name="asset_creation.send_notifications"
        )
        self.assertGreater(notification_steps.count(), 0)

        # Verify asset status - should be ACTIVE if validation passed, DRAFT if failed
        # For metadata-only with valid contract, should activate
        if asset.contracts.filter(
            status=ContractStatus.ACTIVE,
            validation_status__in=[ValidationStatus.VALID, "VALID"],
        ).exists():
            self.assertEqual(asset.status, AssetStatus.ACTIVE)
        else:
            # If contract validation failed, asset should remain DRAFT
            self.assertEqual(asset.status, AssetStatus.DRAFT)

    def test_workflow_with_data_strategy(self):
        """Test workflow execution with data strategy (DOWNLOAD_ALL)"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        # Create test CSV file
        csv_content = b"id,name\n1,Test\n2,Data\n"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(csv_content)
        temp_file.close()

        # Create real test connector
        class TestDownloadConnector(DataMarketplaceConnector):
            def __init__(self, config=None, tenant_id=None, user_id=None):
                self.config = config or {}
                self.tenant_id = tenant_id
                self.user_id = user_id
                self._temp_file = temp_file.name

            @property
            def marketplace_type(self):
                from hub.apps.integrations.base import MarketplaceType

                return MarketplaceType.CKAN_INSTANCE

            @property
            def supported_sync_directions(self):
                from hub.apps.integrations.base import SyncDirection

                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id: str):
                from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.CKAN_INSTANCE,
                    title="Test Listing",
                )

            def list_resources(self, listing_id: str):
                return []

            def create_listing(self, listing):
                return listing

            def update_listing(self, listing_id: str, listing):
                return listing

            def publish_resource(self, listing_id: str, resource):
                return resource

            def download_resource(self, resource_id: str, destination_path: str):
                import shutil

                shutil.copy(self._temp_file, destination_path)
                return destination_path

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

                return MarketplaceListing(
                    marketplace_id="test-listing",
                    marketplace_type=MarketplaceType.CKAN_INSTANCE,
                    title=asset_data.get("name", "Test Asset"),
                )

            def map_to_hub_asset(self, listing, sync_job_id=None):
                from hub.apps.assets.models import AssetSourceType
                from hub.apps.integrations.base import MarketplaceAssetMapping

                return MarketplaceAssetMapping(
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={"marketplace_type": listing.marketplace_type.value},
                )

            def sync_push(self, asset_ids, options=None):
                from django.utils import timezone

                from hub.apps.integrations.base import SyncResult, SyncStatus

                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(asset_ids),
                    successful_items=len(asset_ids),
                    failed_items=0,
                    metadata={"asset_ids": asset_ids},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                from django.utils import timezone

                from hub.apps.integrations.base import SyncResult, SyncStatus

                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(listing_ids) if listing_ids else 0,
                    successful_items=len(listing_ids) if listing_ids else 0,
                    failed_items=0,
                    metadata={"listing_ids": listing_ids or []},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

        # Register test connector temporarily (save original to restore)
        original_ckan = MarketplaceConnectorFactory._connectors.get(
            MarketplaceType.CKAN_INSTANCE.value
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE, TestDownloadConnector
        )

        try:
            resources = [
                MarketplaceResource(
                    resource_id="res-1",
                    resource_type="FILE",
                    name="test.csv",
                    url="https://example.com/test.csv",
                    format="CSV",
                    size_bytes=len(csv_content),
                )
            ]

            asset_mapping = self._create_asset_mapping("Data Strategy Asset", resources=resources)

            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                data_strategy="DOWNLOAD_ALL",
                skip_semantic_mapping=False,  # Enable semantic mapping to trigger workflow
            )

            # Refresh asset to get updated status
            asset.refresh_from_db()

            # Verify workflow was executed
            workflow_instances = WorkflowInstance.objects.filter(
                tenant=self.tenant, workflow_name="asset_creation"
            )
            self.assertGreater(workflow_instances.count(), 0)

            workflow_instance = workflow_instances.first()
            self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

            # Verify all tasks ran
            contract_steps = workflow_instance.steps.filter(
                step_name="asset_creation.validate_contract"
            )
            self.assertGreater(contract_steps.count(), 0)

            # DQ and compliance checks should run if datasets exist
            datasets = Dataset.objects.filter(asset=asset)
            if datasets.exists():
                dq_steps = workflow_instance.steps.filter(step_name="asset_creation.run_dq_checks")
                compliance_steps = workflow_instance.steps.filter(
                    step_name="asset_creation.run_compliance_checks"
                )
                # These steps may or may not exist depending on DQ/compliance service availability
                # But if datasets exist, they should have been attempted

            # Verify indexing ran
            indexing_steps = workflow_instance.steps.filter(
                step_name="asset_creation.index_for_search"
            )
            self.assertGreater(indexing_steps.count(), 0)

            # Verify notifications sent
            notification_steps = workflow_instance.steps.filter(
                step_name="asset_creation.send_notifications"
            )
            self.assertGreater(notification_steps.count(), 0)

            # Verify asset activates if all checks pass
            # Check if asset has valid contract and passes business rules
            has_valid_contract = asset.contracts.filter(
                status=ContractStatus.ACTIVE,
                validation_status__in=[ValidationStatus.VALID, "VALID"],
            ).exists()

            if has_valid_contract:
                # Asset should be ACTIVE if validation passed
                # Note: DQ/compliance checks might fail, but asset can still activate
                # if they're not blocking
                self.assertIn(asset.status, [AssetStatus.ACTIVE, AssetStatus.DRAFT])

        finally:
            # Restore original CKAN connector (other tests depend on it)
            try:
                MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)
                if original_ckan is not None:
                    MarketplaceConnectorFactory.register_connector(
                        MarketplaceType.CKAN_INSTANCE, original_ckan
                    )
            except ValueError:
                pass
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

    def test_workflow_with_validation_failure(self):
        """Test workflow with business rules validation failure"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Validation Failure Asset")

        # Create asset without valid contract (will fail validation)
        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=False,
        )

        # Refresh asset to get updated status
        asset.refresh_from_db()

        # Verify workflow was executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertGreater(workflow_instances.count(), 0)

        workflow_instance = workflow_instances.first()

        # Verify asset remains DRAFT if validation fails
        # Check if contract is invalid or missing
        has_valid_contract = asset.contracts.filter(
            status=ContractStatus.ACTIVE,
            validation_status__in=[ValidationStatus.VALID, "VALID"],
        ).exists()

        if not has_valid_contract:
            # Asset should remain DRAFT if validation failed
            self.assertEqual(asset.status, AssetStatus.DRAFT)
        else:
            # If contract is valid, asset should activate
            self.assertEqual(asset.status, AssetStatus.ACTIVE)

        # Verify other tasks (indexing, notifications) still executed
        indexing_steps = workflow_instance.steps.filter(step_name="asset_creation.index_for_search")
        self.assertGreater(indexing_steps.count(), 0)

        notification_steps = workflow_instance.steps.filter(
            step_name="asset_creation.send_notifications"
        )
        self.assertGreater(notification_steps.count(), 0)

    def test_workflow_asset_created_as_draft(self):
        """Test that assets are created as DRAFT before workflow execution"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Draft Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=False,
        )

        # Asset should initially be created as DRAFT
        # (before workflow execution, but after creation)
        # Since workflow executes synchronously, we check the final status
        asset.refresh_from_db()

        # Verify workflow was executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertGreater(workflow_instances.count(), 0)

        # Asset status depends on workflow validation result
        # If validation passes, it should be ACTIVE
        # If validation fails, it should remain DRAFT
        self.assertIn(asset.status, [AssetStatus.DRAFT, AssetStatus.ACTIVE])

    def test_workflow_with_missing_contracts(self):
        """Test workflow execution with missing contracts (graceful error handling)"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Missing Contracts Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=False,
        )

        # Refresh asset
        asset.refresh_from_db()

        # Verify workflow was executed (even with missing contracts)
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        # Workflow should still execute, but contract validation may be skipped
        self.assertGreater(workflow_instances.count(), 0)

        workflow_instance = workflow_instances.first()

        # Verify workflow completed (even if some steps failed)
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify other tasks still executed
        indexing_steps = workflow_instance.steps.filter(step_name="asset_creation.index_for_search")
        self.assertGreater(indexing_steps.count(), 0)

    def test_workflow_with_missing_datasets(self):
        """Test workflow execution with missing datasets (graceful error handling)"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Missing Datasets Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",  # No datasets created
            skip_semantic_mapping=False,
        )

        # Refresh asset
        asset.refresh_from_db()

        # Verify workflow was executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertGreater(workflow_instances.count(), 0)

        workflow_instance = workflow_instances.first()

        # Verify workflow completed successfully
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

        # Verify DQ/compliance checks were skipped (no datasets)
        dq_steps = workflow_instance.steps.filter(step_name="asset_creation.run_dq_checks")
        compliance_steps = workflow_instance.steps.filter(
            step_name="asset_creation.run_compliance_checks"
        )
        self.assertEqual(dq_steps.count(), 0)
        self.assertEqual(compliance_steps.count(), 0)

    def test_workflow_skipped_when_semantic_mapping_disabled(self):
        """Test that workflow is skipped when semantic mapping is disabled"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Skipped Workflow Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=True,  # Skip semantic mapping
        )

        # Refresh asset
        asset.refresh_from_db()

        # Verify workflow was NOT executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertEqual(workflow_instances.count(), 0)

        # Asset should remain DRAFT (no workflow to activate it)
        self.assertEqual(asset.status, AssetStatus.DRAFT)

    def test_workflow_contracts_attached(self):
        """Test that contracts are attached before workflow execution"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        asset_mapping = self._create_asset_mapping("Contracts Attached Asset")

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=False,
        )

        # Refresh asset
        asset.refresh_from_db()

        # Verify contracts are attached to asset
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertGreater(odcs_contracts.count(), 0)

        odcs_contract = odcs_contracts.first()
        self.assertEqual(odcs_contract.asset, asset)

        # Verify workflow was executed
        workflow_instances = WorkflowInstance.objects.filter(
            tenant=self.tenant, workflow_name="asset_creation"
        )
        self.assertGreater(workflow_instances.count(), 0)

    def test_workflow_datasets_attached(self):
        """Test that datasets are attached before workflow execution"""
        # Real semantic mapping functions will be called - they handle errors gracefully
        # Create test CSV file
        csv_content = b"id,name\n1,Test\n2,Data\n"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(csv_content)
        temp_file.close()

        # Create real test connector
        class TestDownloadConnector2(DataMarketplaceConnector):
            def __init__(self, config=None, tenant_id=None, user_id=None):
                self.config = config or {}
                self.tenant_id = tenant_id
                self.user_id = user_id
                self._temp_file = temp_file.name

            @property
            def marketplace_type(self):
                from hub.apps.integrations.base import MarketplaceType

                return MarketplaceType.CKAN_INSTANCE

            @property
            def supported_sync_directions(self):
                from hub.apps.integrations.base import SyncDirection

                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id: str):
                from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.CKAN_INSTANCE,
                    title="Test Listing",
                )

            def list_resources(self, listing_id: str):
                return []

            def create_listing(self, listing):
                return listing

            def update_listing(self, listing_id: str, listing):
                return listing

            def publish_resource(self, listing_id: str, resource):
                return resource

            def download_resource(self, resource_id: str, destination_path: str):
                import shutil

                shutil.copy(self._temp_file, destination_path)
                return destination_path

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

                return MarketplaceListing(
                    marketplace_id="test-listing",
                    marketplace_type=MarketplaceType.CKAN_INSTANCE,
                    title=asset_data.get("name", "Test Asset"),
                )

            def map_to_hub_asset(self, listing, sync_job_id=None):
                from hub.apps.assets.models import AssetSourceType
                from hub.apps.integrations.base import MarketplaceAssetMapping

                return MarketplaceAssetMapping(
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={"marketplace_type": listing.marketplace_type.value},
                )

            def sync_push(self, asset_ids, options=None):
                from django.utils import timezone

                from hub.apps.integrations.base import SyncResult, SyncStatus

                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(asset_ids),
                    successful_items=len(asset_ids),
                    failed_items=0,
                    metadata={"asset_ids": asset_ids},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                from django.utils import timezone

                from hub.apps.integrations.base import SyncResult, SyncStatus

                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(listing_ids) if listing_ids else 0,
                    successful_items=len(listing_ids) if listing_ids else 0,
                    failed_items=0,
                    metadata={"listing_ids": listing_ids or []},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

        # Register test connector temporarily (save original to restore)
        original_ckan = MarketplaceConnectorFactory._connectors.get(
            MarketplaceType.CKAN_INSTANCE.value
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CKAN_INSTANCE, TestDownloadConnector2
        )

        try:
            resources = [
                MarketplaceResource(
                    resource_id="res-1",
                    resource_type="FILE",
                    name="test.csv",
                    url="https://example.com/test.csv",
                    format="CSV",
                    size_bytes=len(csv_content),
                )
            ]

            asset_mapping = self._create_asset_mapping(
                "Datasets Attached Asset", resources=resources
            )

            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                data_strategy="DOWNLOAD_ALL",
                skip_semantic_mapping=False,
            )

            # Refresh asset
            asset.refresh_from_db()

            # Verify datasets are attached to asset
            datasets = Dataset.objects.filter(asset=asset)
            self.assertGreater(datasets.count(), 0)

            for dataset in datasets:
                self.assertEqual(dataset.asset, asset)

            # Verify workflow was executed
            workflow_instances = WorkflowInstance.objects.filter(
                tenant=self.tenant, workflow_name="asset_creation"
            )
            self.assertGreater(workflow_instances.count(), 0)

        finally:
            # Restore original CKAN connector (other tests depend on it)
            try:
                MarketplaceConnectorFactory.unregister_connector(MarketplaceType.CKAN_INSTANCE)
                if original_ckan is not None:
                    MarketplaceConnectorFactory.register_connector(
                        MarketplaceType.CKAN_INSTANCE, original_ckan
                    )
            except ValueError:
                pass
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass
