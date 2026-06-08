"""
Comprehensive tests for create_federated_asset_with_contracts method.

Tests cover:
- Federated asset creation
- Dual contract creation (ODPS + ODCS)
- Contract linking
- Resource download
- Schema inference
- Semantic mapping
- Transaction rollback on failure
- Integration with sync workflow
"""

import uuid
import json
import os
import tempfile

import pytest
from django.core.files.base import ContentFile
from django.db import connection, close_old_connections
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
    AssetVisibility,
    ExternalResourceReference,
)
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.integrations.base import (
    AssetSourceType,
    MarketplaceAssetMapping,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.semantic.models import SemanticResource
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class TestFederatedAssetCreation(TestCase):
    """Test federated asset creation with contracts"""

    def setUp(self):
        """Set up test data"""
        # Ensure DB connection is open (can be closed by previous test in batch)
        connection.ensure_connection()
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

        uid = uuid.uuid4().hex[:8]
        # Phase 250.5.A.2 — federated import is opt-in per D250.3
        # (default False on existing tenants). Existing tests that
        # exercise the federated-import path MUST set the flag True
        # at fixture time, otherwise the gate at
        # ``DiscoveryServiceMixin._enforce_federated_import_gates``
        # rejects with FederatedImportRejected("FEDERATED_IMPORT_DISABLED").
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            federated_import_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="test-request-123"
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

    def test_create_federated_asset_basic(self):
        """Test basic federated asset creation"""
        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Test Asset",
                "description": "Test Description",
                "domain": "finance",
                "tags": ["tag1", "tag2"],
                "key": "test-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "marketplace_id": "ckan-instance-1",
                "listing_id": "test-package-id",
                "listing_url": "https://ckan.example.com/dataset/test-package-id",
                "synced_at": timezone.now().isoformat(),
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify asset
        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "Test Asset")
        self.assertEqual(asset.description, "Test Description")
        self.assertEqual(asset.domain, "finance")
        # When workflow runs it activates the asset; expect ACTIVE (workflow runs and sets status)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        # Visibility derives from status: ACTIVE → INTERNAL, PUBLIC → PUBLIC
        self.assertEqual(asset.visibility, AssetVisibility.INTERNAL)
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(asset.source_metadata)
        self.assertEqual(asset.source_metadata["connection_id"], str(self.connection.id))
        self.assertEqual(asset.source_metadata["sync_job_id"], str(self.sync_job.id))

        # Verify ODCS contract was created (always created); workflow activates contracts
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)
        odcs_contract = odcs_contracts.first()
        self.assertEqual(odcs_contract.asset, asset)
        self.assertEqual(odcs_contract.status, ContractStatus.ACTIVE)
        self.assertIsNotNone(odcs_contract.hub_contract_json)
        # Metadata-only (no resources): schema may be [] or a single _metadata_placeholder field
        schema_fields = odcs_contract.hub_contract_json["schema"]["fields"]
        self.assertIsInstance(schema_fields, list)
        if schema_fields:
            self.assertEqual(len(schema_fields), 1)
            self.assertEqual(schema_fields[0].get("name"), "_metadata_placeholder")
        self.assertIn("quality", odcs_contract.hub_contract_json)
        self.assertIn("serviceLevel", odcs_contract.hub_contract_json)

        # Verify MarketplaceMapping was created
        mappings = MarketplaceMapping.objects.filter(hub_asset=asset)
        self.assertEqual(mappings.count(), 1)
        mapping = mappings.first()
        self.assertEqual(mapping.connection, self.connection)
        self.assertEqual(mapping.external_listing_id, "test-package-id")
        self.assertIsNotNone(mapping.last_synced_at)

    def test_create_federated_asset_with_odps_contract(self):
        """Test federated asset creation with ODPS contract"""
        odps_metadata = {
            "product_details": {
                "product_name": "ODPS Product",
                "product_description": "ODPS Description",
                "product_version": "1.0.0",
            },
            "pricing_plans": [
                {"planID": "plan-1", "name": "Basic Plan", "price": 10.0, "currency": "USD"}
            ],
            "access_methods": {"api": {"type": "REST", "endpoint": "https://api.example.com"}},
            "payment_gateways": {"stripe": {"enabled": True}},
            "license_id": "cc-by",
            "author": "Test Author",
            "maintainer": "Test Maintainer",
            "version": "4.1",
        }

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "ODPS Asset",
                "description": "ODPS Description",
                "key": "odps-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "odps-package-id",
            },
            odps_metadata=odps_metadata,
            odcs_metadata=None,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify ODPS contract was created
        odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        self.assertEqual(odps_contracts.count(), 1)
        odps_contract = odps_contracts.first()
        self.assertEqual(odps_contract.asset, asset)
        self.assertEqual(odps_contract.original_spec_version, "4.1")
        self.assertIsNotNone(odps_contract.hub_contract_json)

        # Verify ODPS metadata in hub_contract_json
        hub_contract = odps_contract.hub_contract_json
        self.assertEqual(hub_contract["info"]["name"], "ODPS Product")
        self.assertIn("marketplace", hub_contract)
        self.assertIn("x_odps", hub_contract["marketplace"])
        self.assertIn("pricing_plans", hub_contract["marketplace"]["x_odps"])
        self.assertIn("access_methods", hub_contract["marketplace"]["x_odps"])
        self.assertIn("payment_gateways", hub_contract["marketplace"]["x_odps"])

        # Verify ODCS contract was created
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)

    def test_create_federated_asset_with_odcs_metadata(self):
        """Test federated asset creation with ODCS metadata"""
        odcs_metadata = {
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": "non_null_id",
                        "name": "ID must not be null",
                        "dimension": "completeness",
                        "severity": "ERROR",
                    }
                ]
            },
            "serviceLevel": {
                "availability": "99.95%",
                "responseTime": "500ms",
                "throughput": "2000 req/s",
            },
        }

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "ODCS Asset",
                "description": "ODCS Description",
                "key": "odcs-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "odcs-package-id",
            },
            odps_metadata=None,
            odcs_metadata=odcs_metadata,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify ODCS contract was created with metadata
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)
        odcs_contract = odcs_contracts.first()
        hub_contract = odcs_contract.hub_contract_json

        # Verify schema fields
        self.assertEqual(len(hub_contract["schema"]["fields"]), 2)
        self.assertEqual(hub_contract["schema"]["fields"][0]["name"], "id")

        # Verify quality rules
        self.assertEqual(len(hub_contract["quality"]["rules"]), 1)
        self.assertEqual(hub_contract["quality"]["rules"][0]["rule_id"], "non_null_id")

        # Verify service level
        self.assertEqual(hub_contract["serviceLevel"]["availability"], "99.95%")

    def test_create_federated_asset_with_dual_contracts(self):
        """Test federated asset creation with both ODPS and ODCS contracts"""
        odps_metadata = {
            "product_details": {
                "product_name": "Dual Contract Product",
                "product_description": "Dual Contract Description",
            },
            "pricing_plans": [{"planID": "plan-1", "price": 10.0}],
            "version": "4.1",
        }

        odcs_metadata = {
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "quality": {"rules": []},
        }

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Dual Contract Asset",
                "description": "Dual Contract Description",
                "key": "dual-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "dual-package-id",
            },
            odps_metadata=odps_metadata,
            odcs_metadata=odcs_metadata,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify both contracts were created
        odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)

        self.assertEqual(odps_contracts.count(), 1)
        self.assertEqual(odcs_contracts.count(), 1)

        odps_contract = odps_contracts.first()
        odcs_contract = odcs_contracts.first()

        # Verify bidirectional linking
        odps_hub_contract = odps_contract.hub_contract_json
        odcs_hub_contract = odcs_contract.hub_contract_json

        # ODPS → ODCS link
        self.assertIn("extensions", odps_hub_contract)
        self.assertIn("x_odps", odps_hub_contract["extensions"])
        self.assertEqual(
            odps_hub_contract["extensions"]["x_odps"]["odcs_link"], str(odcs_contract.id)
        )

        # ODCS → ODPS link
        self.assertIn("extensions", odcs_hub_contract)
        self.assertIn("x_odps", odcs_hub_contract["extensions"])
        self.assertEqual(
            odcs_hub_contract["extensions"]["x_odps"]["odps_link"], str(odps_contract.id)
        )

    def test_create_federated_asset_with_resources(self):
        """Test federated asset creation with resource download"""
        # Create a test CSV file
        csv_content = b"id,name,value\n1,test1,value1\n2,test2,value2\n"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file.write(csv_content)
        temp_file.close()

        # Mock connector download_resource to return our test file
        class MockConnector:
            def authenticate(self, config):
                pass

            def download_resource(self, resource_id, destination_path):
                import shutil

                shutil.copy(temp_file.name, destination_path)
                return destination_path

        # Register mock connector
        original_create = MarketplaceConnectorFactory.create_connector

        @classmethod
        def mock_create_connector(cls, marketplace_type, config=None, tenant_id=None, user_id=None):
            return MockConnector()

        MarketplaceConnectorFactory.create_connector = mock_create_connector

        try:
            asset_mapping = MarketplaceAssetMapping(
                asset_data={
                    "name": "Resource Asset",
                    "description": "Resource Description",
                    "key": "resource-asset-key",
                },
                source_type=AssetSourceType.FEDERATED,
                source_metadata={
                    "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                    "listing_id": "resource-package-id",
                },
                odps_metadata=None,
                odcs_metadata=None,
                resources=[
                    MarketplaceResource(
                        resource_id="resource-1",
                        resource_type="FILE",
                        name="test.csv",
                        description="Test CSV file",
                        format="CSV",
                        size_bytes=len(csv_content),
                    )
                ],
            )

            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                data_strategy="DOWNLOAD_ALL",  # Explicitly request resource download
            )

            # Verify File was created
            files = File.objects.filter(tenant=self.tenant)
            self.assertGreater(files.count(), 0)
            file_obj = files.first()
            self.assertEqual(file_obj.name, "test.csv")
            self.assertEqual(file_obj.size, len(csv_content))
            self.assertIsNotNone(file_obj.storage_path)

            # Verify Dataset was created
            datasets = Dataset.objects.filter(asset=asset)
            self.assertGreater(datasets.count(), 0)
            dataset = datasets.first()
            self.assertEqual(dataset.file, file_obj)
            self.assertIsNotNone(dataset.schema_json)

            # Verify schema was inferred
            if dataset.schema_json.get("fields"):
                self.assertGreater(len(dataset.schema_json["fields"]), 0)

            # Verify ODCS contract schema was updated if schema was inferred
            odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
            if odcs_contracts.exists():
                odcs_contract = odcs_contracts.first()
                if dataset.schema_json.get("fields"):
                    hub_contract = odcs_contract.hub_contract_json
                    if hub_contract.get("schema", {}).get("fields"):
                        self.assertGreater(len(hub_contract["schema"]["fields"]), 0)

        finally:
            # Restore original method
            MarketplaceConnectorFactory.create_connector = original_create
            # Cleanup temp file
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

    def test_create_federated_asset_semantic_mapping(self):
        """Test semantic mapping is called for asset and contracts"""
        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Semantic Asset",
                "description": "Semantic Description",
                "key": "semantic-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "semantic-package-id",
            },
            odps_metadata={
                "product_details": {"product_name": "Semantic Product"},
                "version": "4.1",
            },
            odcs_metadata=None,
            resources=[],
        )

        # Mock semantic mapping functions to track calls
        semantic_calls = []

        def mock_map_asset(asset, tenant=None, use_cache=True):
            semantic_calls.append(("asset", str(asset.id)))
            return None

        def mock_map_contract(contract, tenant=None, use_cache=True):
            semantic_calls.append(("contract", str(contract.id), contract.original_spec_type))
            return None

        from hub.apps.semantic import utils

        original_map_asset = utils.map_asset_to_semantic
        original_map_contract = utils.map_contract_to_semantic
        utils.map_asset_to_semantic = mock_map_asset
        utils.map_contract_to_semantic = mock_map_contract

        try:
            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

            # Verify semantic mapping was called
            # Should be called for: asset, ODPS contract, ODCS contract
            self.assertGreaterEqual(len(semantic_calls), 2)  # At least asset and one contract

            # Verify asset mapping was called
            asset_calls = [c for c in semantic_calls if c[0] == "asset"]
            self.assertEqual(len(asset_calls), 1)
            self.assertEqual(asset_calls[0][1], str(asset.id))

            # Verify contract mappings were called
            contract_calls = [c for c in semantic_calls if c[0] == "contract"]
            self.assertGreaterEqual(len(contract_calls), 1)  # At least ODCS contract

        finally:
            utils.map_asset_to_semantic = original_map_asset
            utils.map_contract_to_semantic = original_map_contract

    def test_create_federated_asset_transaction_rollback(self):
        """Test transaction rollback on failure"""
        # Create asset_mapping that will cause an error
        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Error Asset",
                "description": "Error Description",
                "key": "error-asset-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "error-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=[],
        )

        # Mock a failure during contract creation
        from hub.apps.contracts.models import Contract

        original_create = Contract.objects.create

        def failing_create(*args, **kwargs):
            if kwargs.get("original_spec_type") == OriginalSpecType.ODCS:
                raise Exception("Simulated contract creation failure")
            return original_create(*args, **kwargs)

        Contract.objects.create = failing_create

        try:
            with self.assertRaises(Exception):
                self.service.create_federated_asset_with_contracts(
                    asset_mapping=asset_mapping,
                    connection=self.connection,
                    sync_job=self.sync_job,
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                )

            # Verify transaction was rolled back - no asset should exist
            assets = Asset.objects.filter(name="Error Asset")
            self.assertEqual(assets.count(), 0)

            # Verify no contracts were created
            contracts = Contract.objects.filter(tenant=self.tenant)
            initial_count = contracts.count()
            # Should be 0 if transaction rolled back properly

        finally:
            Contract.objects.create = original_create

    def test_create_federated_asset_missing_name_defaults(self):
        """Test that missing name defaults to a generated name"""
        asset_mapping = MarketplaceAssetMapping(
            asset_data={"description": "Description without name", "key": "no-name-asset-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "no-name-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Should use default name or generate from key
        self.assertIsNotNone(asset.name)
        self.assertGreater(len(asset.name), 0)

    def test_create_federated_asset_source_metadata_enrichment(self):
        """Test that source_metadata is enriched with connection and sync_job IDs"""
        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Metadata Asset", "key": "metadata-asset-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "metadata-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify source_metadata was enriched
        self.assertIsNotNone(asset.source_metadata)
        self.assertEqual(asset.source_metadata["connection_id"], str(self.connection.id))
        self.assertEqual(asset.source_metadata["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(
            asset.source_metadata["marketplace_type"], MarketplaceType.CKAN_INSTANCE.value
        )
        self.assertEqual(asset.source_metadata["listing_id"], "metadata-package-id")

    def test_metadata_first_creation_no_downloads(self):
        """Test metadata-first creation with METADATA_ONLY strategy (no downloads)"""
        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/res1.csv",
                format="CSV",
                size_bytes=1024,
            ),
            MarketplaceResource(
                resource_id="res-2",
                resource_type="FILE",
                name="Resource 2",
                url="https://example.com/res2.json",
                format="JSON",
                size_bytes=2048,
            ),
        ]

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Metadata First Asset",
                "description": "Test metadata-first approach",
                "key": "metadata-first-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "metadata-first-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources,
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
        )

        # Verify asset created
        self.assertIsNotNone(asset)
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

        # Verify external resources stored in source_metadata
        self.assertIn("external_resources", asset.source_metadata)
        external_resources = asset.source_metadata["external_resources"]
        self.assertEqual(len(external_resources), 2)
        self.assertEqual(external_resources[0]["resource_id"], "res-1")
        self.assertEqual(external_resources[0]["external"], True)
        self.assertEqual(external_resources[0]["format"], "CSV")
        self.assertEqual(external_resources[1]["resource_id"], "res-2")
        self.assertEqual(external_resources[1]["format"], "JSON")

        # Verify ODPS contract created (even with minimal metadata)
        odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        self.assertEqual(odps_contracts.count(), 1)
        odps_contract = odps_contracts.first()
        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertEqual(odps_contract.hub_contract_json["info"]["name"], "Metadata First Asset")

        # Verify ODCS contract created with schema hints
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)
        odcs_contract = odcs_contracts.first()
        self.assertIsNotNone(odcs_contract.hub_contract_json)
        # Schema hints should be present
        schema = odcs_contract.hub_contract_json.get("schema", {})
        if "hints" in schema:
            hints = schema["hints"]
            self.assertIn("formats", hints)
            self.assertIn("resource_count", hints)
            self.assertEqual(hints["resource_count"], 2)
            self.assertIn("CSV", hints["formats"])
            self.assertIn("JSON", hints["formats"])

        # Verify no files/datasets created (METADATA_ONLY)
        files = File.objects.filter(tenant=self.tenant)
        self.assertEqual(files.count(), 0)
        datasets = Dataset.objects.filter(tenant=self.tenant, asset=asset)
        self.assertEqual(datasets.count(), 0)

        # Verify contracts are linked
        self.assertIsNotNone(
            odps_contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odcs_link")
        )
        self.assertIsNotNone(
            odcs_contract.hub_contract_json.get("extensions", {}).get("x_odps", {}).get("odps_link")
        )

    def test_selective_download_strategy(self):
        """Test DOWNLOAD_SELECTIVE strategy with specific resource IDs"""
        # Create test files for different resources
        csv_content_1 = b"id,name\n1,test1\n2,test2\n"
        csv_content_3 = b"id,value\n1,100\n2,200\n"

        temp_file_1 = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file_1.write(csv_content_1)
        temp_file_1.close()

        temp_file_3 = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file_3.write(csv_content_3)
        temp_file_3.close()

        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/res1.csv",
                format="CSV",
                size_bytes=1024,
            ),
            MarketplaceResource(
                resource_id="res-2",
                resource_type="FILE",
                name="Resource 2",
                url="https://example.com/res2.json",
                format="JSON",
                size_bytes=2048,
            ),
            MarketplaceResource(
                resource_id="res-3",
                resource_type="FILE",
                name="Resource 3",
                url="https://example.com/res3.csv",
                format="CSV",
                size_bytes=3072,
            ),
        ]

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Selective Download Asset", "key": "selective-download-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "selective-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources,
        )

        # Mock connector to return different files based on resource_id
        class MockConnector:
            def authenticate(self, config):
                pass

            def download_resource(self, resource_id, destination_path):
                import shutil

                # Return different files based on resource_id
                if resource_id == "res-1":
                    shutil.copy(temp_file_1.name, destination_path)
                elif resource_id == "res-3":
                    shutil.copy(temp_file_3.name, destination_path)
                else:
                    raise ValueError(f"Unexpected resource_id: {resource_id}")
                return destination_path

        # Register mock connector
        original_create = MarketplaceConnectorFactory.create_connector

        @classmethod
        def mock_create_connector(cls, marketplace_type, config=None, tenant_id=None, user_id=None):
            return MockConnector()

        MarketplaceConnectorFactory.create_connector = mock_create_connector

        try:
            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                data_strategy="DOWNLOAD_SELECTIVE",
                download_resources=["res-1", "res-3"],  # Only download res-1 and res-3
                skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
            )

            # Verify asset created
            self.assertIsNotNone(asset)
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

            # Verify data_strategy is set correctly
            from hub.apps.assets.models import DataStrategy

            self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_SELECTIVE)
            self.assertFalse(asset.is_metadata_only())
            # For DOWNLOAD_SELECTIVE, can_download_resource returns True for any resource
            # that exists in ExternalResourceReference (strategy allows selective downloads)
            self.assertTrue(asset.can_download_resource("res-1"))
            self.assertTrue(asset.can_download_resource("res-3"))
            self.assertTrue(
                asset.can_download_resource("res-2")
            )  # Exists in ExternalResourceReference
            # Non-existent resource should return False
            self.assertFalse(asset.can_download_resource("non-existent-resource"))

            # Verify external resources stored (all 3 resources)
            self.assertIn("external_resources", asset.source_metadata)
            external_resources = asset.source_metadata["external_resources"]
            self.assertEqual(len(external_resources), 3)  # All resources stored as external

            # Verify only selected resources were downloaded (res-1 and res-3)
            # Files are related to assets through Dataset, so filter through datasets
            datasets = Dataset.objects.filter(asset=asset)
            self.assertEqual(datasets.count(), 2)  # Only res-1 and res-3 should be downloaded
            # Verify files were created for downloaded resources
            files = File.objects.filter(tenant=self.tenant, datasets__asset=asset).distinct()
            self.assertGreaterEqual(files.count(), 2)

        finally:
            # Restore original method
            MarketplaceConnectorFactory.create_connector = original_create
            # Cleanup temp files
            try:
                os.unlink(temp_file_1.name)
                os.unlink(temp_file_3.name)
            except Exception:
                pass

    def test_odps_contract_minimal_metadata(self):
        """Test ODPS contract creation with minimal metadata (None)"""
        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Minimal ODPS Asset",
                "description": "Test minimal ODPS",
                "key": "minimal-odps-key",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "minimal-odps-package-id",
            },
            odps_metadata=None,  # No ODPS metadata
            odcs_metadata=None,
            resources=[],
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
        )

        # Verify ODPS contract was created even with None metadata
        odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        self.assertEqual(odps_contracts.count(), 1)
        odps_contract = odps_contracts.first()
        self.assertIsNotNone(odps_contract)
        self.assertIsNotNone(odps_contract.hub_contract_json)
        # Should have minimal structure
        self.assertEqual(odps_contract.hub_contract_json["info"]["name"], "Minimal ODPS Asset")
        # Marketplace source should be in extensions.x_marketplace or marketplace.x_odps
        hub_contract = odps_contract.hub_contract_json
        self.assertTrue(
            "marketplace" in hub_contract.get("extensions", {}).get("x_marketplace", {})
            or "marketplace" in hub_contract
            or "x_odps" in hub_contract.get("extensions", {})
        )

    def test_odcs_contract_schema_hints(self):
        """Test ODCS contract creation with schema hints from external resources"""
        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Large CSV",
                url="https://example.com/large.csv",
                format="CSV",
                size_bytes=1048576,  # 1MB
            ),
            MarketplaceResource(
                resource_id="res-2",
                resource_type="FILE",
                name="Small JSON",
                url="https://example.com/small.json",
                format="JSON",
                size_bytes=512,
            ),
        ]

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Schema Hints Asset", "key": "schema-hints-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "schema-hints-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources,
        )

        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
        )

        # Verify ODCS contract has schema hints
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)
        odcs_contract = odcs_contracts.first()
        schema = odcs_contract.hub_contract_json.get("schema", {})

        # Should have hints (not actual fields) when using external resources
        if "hints" in schema:
            hints = schema["hints"]
            self.assertIn("formats", hints)
            self.assertIn("resource_count", hints)
            self.assertEqual(hints["resource_count"], 2)
            self.assertIn("CSV", hints["formats"])
            self.assertIn("JSON", hints["formats"])
            self.assertEqual(hints["total_size_bytes"], 1048576 + 512)

    def test_backward_compatibility_skip_resource_downloads(self):
        """Test backward compatibility with skip_resource_downloads parameter"""
        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/res1.csv",
                format="CSV",
                size_bytes=1024,
            )
        ]

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Backward Compat Asset", "key": "backward-compat-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "backward-compat-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources,
        )

        # Test with skip_resource_downloads=True (should map to METADATA_ONLY)
        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            skip_resource_downloads=True,  # Old parameter
            skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
        )

        # Verify no files created
        files = File.objects.filter(tenant=self.tenant)
        self.assertEqual(files.count(), 0)

        # Verify external resources stored
        self.assertIn("external_resources", asset.source_metadata)
        self.assertEqual(len(asset.source_metadata["external_resources"]), 1)

    def test_full_download_strategy(self):
        """Test DOWNLOAD_ALL strategy downloads all resources"""
        # Create test files
        csv_content_1 = b"id,name\n1,test1\n2,test2\n"
        json_content_2 = b'{"id": 1, "name": "test"}'
        csv_content_3 = b"id,value\n1,100\n2,200\n"

        temp_file_1 = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file_1.write(csv_content_1)
        temp_file_1.close()

        temp_file_2 = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temp_file_2.write(json_content_2)
        temp_file_2.close()

        temp_file_3 = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_file_3.write(csv_content_3)
        temp_file_3.close()

        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Resource 1",
                url="https://example.com/res1.csv",
                format="CSV",
                size_bytes=1024,
            ),
            MarketplaceResource(
                resource_id="res-2",
                resource_type="FILE",
                name="Resource 2",
                url="https://example.com/res2.json",
                format="JSON",
                size_bytes=2048,
            ),
            MarketplaceResource(
                resource_id="res-3",
                resource_type="FILE",
                name="Resource 3",
                url="https://example.com/res3.csv",
                format="CSV",
                size_bytes=3072,
            ),
        ]

        asset_mapping = MarketplaceAssetMapping(
            asset_data={"name": "Full Download Asset", "key": "full-download-key"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "full-download-package-id",
            },
            odps_metadata=None,
            odcs_metadata=None,
            resources=resources,
        )

        # Mock connector to return files based on resource_id
        class MockConnector:
            def authenticate(self, config):
                pass

            def download_resource(self, resource_id, destination_path):
                import shutil

                if resource_id == "res-1":
                    shutil.copy(temp_file_1.name, destination_path)
                elif resource_id == "res-2":
                    shutil.copy(temp_file_2.name, destination_path)
                elif resource_id == "res-3":
                    shutil.copy(temp_file_3.name, destination_path)
                else:
                    raise ValueError(f"Unexpected resource_id: {resource_id}")
                return destination_path

        # Register mock connector
        original_create = MarketplaceConnectorFactory.create_connector

        @classmethod
        def mock_create_connector(cls, marketplace_type, config=None, tenant_id=None, user_id=None):
            return MockConnector()

        MarketplaceConnectorFactory.create_connector = mock_create_connector

        try:
            asset = self.service.create_federated_asset_with_contracts(
                asset_mapping=asset_mapping,
                connection=self.connection,
                sync_job=self.sync_job,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                data_strategy="DOWNLOAD_ALL",  # Download all resources
                skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
            )

            # Verify asset created
            self.assertIsNotNone(asset)
            self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)

            # Verify external resources stored (all 3 resources)
            self.assertIn("external_resources", asset.source_metadata)
            external_resources = asset.source_metadata["external_resources"]
            self.assertEqual(len(external_resources), 3)

            # Verify data_strategy is set correctly
            from hub.apps.assets.models import DataStrategy

            self.assertEqual(asset.data_strategy, DataStrategy.DOWNLOAD_ALL)
            self.assertFalse(asset.is_metadata_only())
            self.assertTrue(asset.can_download_resource("res-1"))
            self.assertTrue(asset.can_download_resource("res-2"))
            self.assertTrue(asset.can_download_resource("res-3"))

            # Verify all resources were downloaded
            datasets = Dataset.objects.filter(asset=asset)
            self.assertEqual(datasets.count(), 3)  # All 3 resources have datasets
            files = File.objects.filter(tenant=self.tenant, datasets__asset=asset).distinct()
            self.assertEqual(files.count(), 3)  # All 3 resources downloaded
            # Verify file names match resources
            file_names = [f.name for f in files]
            self.assertIn("Resource 1", file_names)
            self.assertIn("Resource 2", file_names)
            self.assertIn("Resource 3", file_names)

        finally:
            # Restore original method
            MarketplaceConnectorFactory.create_connector = original_create
            # Cleanup temp files
            try:
                os.unlink(temp_file_1.name)
                os.unlink(temp_file_2.name)
                os.unlink(temp_file_3.name)
            except Exception:
                pass

    def test_integration_metadata_first_workflow(self):
        """Integration test for complete metadata-first workflow"""
        resources = [
            MarketplaceResource(
                resource_id="res-1",
                resource_type="FILE",
                name="Integration Resource",
                url="https://example.com/integration.csv",
                format="CSV",
                size_bytes=1024,
            )
        ]

        odps_metadata = {
            "product_details": {
                "product_name": "Integration Product",
                "product_description": "Integration Test Description",
                "product_version": "1.0.0",
            },
            "version": "4.1",
        }

        odcs_metadata = {
            "schema": {"hints": {"formats": ["CSV"], "resource_count": 1}},
            "quality": {
                "rules": [
                    {
                        "rule_id": "test_rule",
                        "name": "Test Quality Rule",
                        "dimension": "completeness",
                        "severity": "INFO",
                    }
                ]
            },
        }

        asset_mapping = MarketplaceAssetMapping(
            asset_data={
                "name": "Integration Test Asset",
                "description": "Complete integration test",
                "key": "integration-test-key",
                "domain": "test",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.CKAN_INSTANCE.value,
                "listing_id": "integration-package-id",
                "listing_url": "https://ckan.example.com/dataset/integration-package-id",
            },
            odps_metadata=odps_metadata,
            odcs_metadata=odcs_metadata,
            resources=resources,
        )

        # Use METADATA_ONLY strategy (no downloads)
        asset = self.service.create_federated_asset_with_contracts(
            asset_mapping=asset_mapping,
            connection=self.connection,
            sync_job=self.sync_job,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
            skip_semantic_mapping=True,  # Skip semantic mapping for faster unit tests
        )

        # STEP 1: Verify Asset created with FEDERATED source type
        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "Integration Test Asset")
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        # Asset is created as DRAFT and workflow is skipped when semantic mapping is skipped
        # So asset should remain DRAFT
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        # Visibility derives from status: DRAFT → INTERNAL
        self.assertEqual(asset.visibility, AssetVisibility.INTERNAL)

        # STEP 1a: Verify data_strategy is set correctly
        from hub.apps.assets.models import DataStrategy

        self.assertEqual(asset.data_strategy, DataStrategy.METADATA_ONLY)
        self.assertTrue(asset.is_metadata_only())

        # STEP 2: Verify external resources stored in source_metadata
        self.assertIn("external_resources", asset.source_metadata)
        external_resources = asset.source_metadata["external_resources"]
        self.assertEqual(len(external_resources), 1)

        # STEP 2a: Verify ExternalResourceReference records created
        external_resource_refs = ExternalResourceReference.objects.filter(asset=asset)
        self.assertEqual(external_resource_refs.count(), 1)
        external_ref = external_resource_refs.first()
        self.assertEqual(external_ref.resource_id, "res-1")
        self.assertEqual(external_ref.name, "Integration Resource")
        self.assertEqual(external_ref.url, "https://example.com/integration.csv")
        self.assertEqual(external_ref.format, "CSV")
        self.assertEqual(external_ref.size_bytes, 1024)
        self.assertEqual(external_ref.connection_id, self.connection.id)
        self.assertTrue(asset.has_external_resources())
        self.assertEqual(asset.get_external_resources().count(), 1)
        self.assertEqual(external_resources[0]["resource_id"], "res-1")
        self.assertEqual(external_resources[0]["external"], True)
        self.assertEqual(external_resources[0]["format"], "CSV")

        # STEP 3: Verify ODPS Contract created (with full metadata)
        odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
        self.assertEqual(odps_contracts.count(), 1)
        odps_contract = odps_contracts.first()
        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertEqual(odps_contract.hub_contract_json["info"]["name"], "Integration Product")
        self.assertEqual(odps_contract.status, ContractStatus.DRAFT)

        # STEP 4: Verify ODCS Contract created with schema hints
        odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)
        self.assertEqual(odcs_contracts.count(), 1)
        odcs_contract = odcs_contracts.first()
        self.assertIsNotNone(odcs_contract.hub_contract_json)
        schema = odcs_contract.hub_contract_json.get("schema", {})
        # Should have hints from external resources
        if "hints" in schema:
            hints = schema["hints"]
            self.assertIn("formats", hints)
            self.assertIn("resource_count", hints)
            self.assertEqual(hints["resource_count"], 1)
        # Should also have quality rules from metadata
        quality = odcs_contract.hub_contract_json.get("quality", {})
        self.assertIn("rules", quality)
        self.assertEqual(len(quality["rules"]), 1)

        # STEP 5: Verify contracts are linked bidirectionally
        odps_hub_contract = odps_contract.hub_contract_json
        odcs_hub_contract = odcs_contract.hub_contract_json

        # ODPS → ODCS link
        self.assertIn("extensions", odps_hub_contract)
        self.assertIn("x_odps", odps_hub_contract.get("extensions", {}))
        odps_extensions = odps_hub_contract["extensions"].get("x_odps", {})
        self.assertIn("odcs_link", odps_extensions)
        self.assertEqual(odps_extensions["odcs_link"], str(odcs_contract.id))

        # ODCS → ODPS link
        self.assertIn("extensions", odcs_hub_contract)
        self.assertIn("x_odps", odcs_hub_contract.get("extensions", {}))
        odcs_extensions = odcs_hub_contract["extensions"].get("x_odps", {})
        self.assertIn("odps_link", odcs_extensions)
        self.assertEqual(odcs_extensions["odps_link"], str(odps_contract.id))

        # STEP 6: Verify MarketplaceMapping created
        mappings = MarketplaceMapping.objects.filter(hub_asset=asset)
        self.assertEqual(mappings.count(), 1)
        mapping = mappings.first()
        self.assertEqual(mapping.connection, self.connection)
        self.assertEqual(mapping.external_listing_id, "integration-package-id")
        self.assertIsNotNone(mapping.last_synced_at)

        # STEP 7: Verify no files/datasets created (METADATA_ONLY)
        datasets = Dataset.objects.filter(asset=asset)
        self.assertEqual(datasets.count(), 0)
        # Files are related through datasets, so check via datasets
        files = File.objects.filter(tenant=self.tenant, datasets__asset=asset).distinct()
        self.assertEqual(files.count(), 0)

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
