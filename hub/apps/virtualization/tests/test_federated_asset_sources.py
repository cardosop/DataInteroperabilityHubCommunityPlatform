"""
Unit and integration tests for VirtualDataset federated asset sources.

Tests federated asset and external resource source support in virtual datasets.
Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import pytest
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetSourceType, ExternalResourceReference, DataStrategy
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceType
from hub.apps.users.models import Role, UserRole, UserStatus
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryType,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.virtualization.business_rules import VirtualizationBusinessRules
from hub.apps.core.services.base import ValidationError, NotFoundError

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualDatasetFederatedAssetSourceTest(TestCase):
    """Test VirtualDataset with federated asset sources"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create DATA_PROVIDER role
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        # Assign DATA_PROVIDER role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=self.data_provider_role
        )

        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create marketplace connection
        self.marketplace_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="Test Marketplace Connection",
            config={"api_key": "test-key"}
        )

        # Create federated asset with unique key
        asset_key = f"federated-asset-{uuid.uuid4()}"
        self.federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=asset_key,
            name="Test Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.METADATA_ONLY
        )

        # Create external resource reference
        self.external_resource = ExternalResourceReference.objects.create(
            asset=self.federated_asset,
            resource_id="res-123",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=1024,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.marketplace_connection.id
        )

    def test_create_virtual_dataset_with_federated_asset_source(self):
        """Test creating virtual dataset with federated asset source"""
        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(self.federated_asset.id),
                "query": "SELECT * FROM resource"
            }
        ]

        virtual_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Virtual Dataset",
            query="SELECT * FROM federated_source",
            query_type=QueryType.SQL,
            sources=sources
        )

        self.assertIsNotNone(virtual_dataset)
        self.assertEqual(len(virtual_dataset.sources), 1)
        self.assertEqual(virtual_dataset.sources[0]["type"], "federated_asset")
        self.assertEqual(virtual_dataset.sources[0]["asset_id"], str(self.federated_asset.id))

    def test_create_virtual_dataset_with_external_resource_source(self):
        """Test creating virtual dataset with external resource source"""
        # Set asset to DOWNLOAD_ALL to allow resource download
        self.federated_asset.data_strategy = DataStrategy.DOWNLOAD_ALL
        self.federated_asset.save()

        sources = [
            {
                "type": "external_resource",
                "asset_id": str(self.federated_asset.id),
                "resource_id": "res-123"
            }
        ]

        virtual_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Virtual Dataset",
            query="SELECT * FROM external_resource",
            query_type=QueryType.SQL,
            sources=sources
        )

        self.assertIsNotNone(virtual_dataset)
        self.assertEqual(len(virtual_dataset.sources), 1)
        self.assertEqual(virtual_dataset.sources[0]["type"], "external_resource")
        self.assertEqual(virtual_dataset.sources[0]["asset_id"], str(self.federated_asset.id))
        self.assertEqual(virtual_dataset.sources[0]["resource_id"], "res-123")

    def test_validate_federated_asset_source_missing_asset_id(self):
        """Test validation fails when federated asset source is missing asset_id"""
        sources = [
            {
                "type": "federated_asset",
                "query": "SELECT * FROM resource"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM federated_source",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("asset_id", str(cm.exception).lower())

    def test_validate_federated_asset_source_invalid_asset_id(self):
        """Test validation fails when federated asset source has invalid asset_id"""
        sources = [
            {
                "type": "federated_asset",
                "asset_id": "invalid-uuid",
                "query": "SELECT * FROM resource"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM federated_source",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("asset_id", str(cm.exception).lower())

    def test_validate_federated_asset_source_nonexistent_asset(self):
        """Test validation fails when federated asset source references non-existent asset"""
        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(uuid.uuid4()),
                "query": "SELECT * FROM resource"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM federated_source",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("non-existent", str(cm.exception).lower())

    def test_validate_federated_asset_source_non_federated_asset(self):
        """Test validation fails when federated asset source references non-federated asset"""
        # Create non-federated asset with unique key
        non_federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"non-federated-asset-{uuid.uuid4()}",
            name="Non-Federated Asset",
            source_type=AssetSourceType.HUB_NATIVE
        )

        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(non_federated_asset.id),
                "query": "SELECT * FROM resource"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM federated_source",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("not a federated asset", str(cm.exception).lower())

    def test_validate_external_resource_source_missing_resource_id(self):
        """Test validation fails when external resource source is missing resource_id"""
        sources = [
            {
                "type": "external_resource",
                "asset_id": str(self.federated_asset.id)
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM external_resource",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("resource_id", str(cm.exception).lower())

    def test_validate_external_resource_source_nonexistent_resource(self):
        """Test validation fails when external resource source references non-existent resource"""
        sources = [
            {
                "type": "external_resource",
                "asset_id": str(self.federated_asset.id),
                "resource_id": "nonexistent-resource"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM external_resource",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("not found", str(cm.exception).lower())

    def test_validate_external_resource_source_metadata_only_strategy(self):
        """Test validation fails when external resource source references asset with METADATA_ONLY strategy"""
        # Asset already has METADATA_ONLY strategy
        sources = [
            {
                "type": "external_resource",
                "asset_id": str(self.federated_asset.id),
                "resource_id": "res-123"
            }
        ]

        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Virtual Dataset",
                query="SELECT * FROM external_resource",
                query_type=QueryType.SQL,
                sources=sources
            )

        self.assertIn("cannot be downloaded", str(cm.exception).lower())


class VirtualDatasetFederatedAssetBusinessRulesTest(TestCase):
    """Test business rules validation for federated asset sources"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

        # Create federated asset with unique key
        self.federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"federated-asset-{uuid.uuid4()}",
            name="Test Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL
        )

    def test_validate_federated_asset_source_config_valid(self):
        """Test business rules validation for valid federated asset source"""
        source_config = {
            "type": "federated_asset",
            "asset_id": str(self.federated_asset.id),
            "query": "SELECT * FROM resource"
        }

        errors = self.business_rules._validate_federated_asset_source_config(source_config, 0)
        self.assertEqual(len(errors), 0)

    def test_validate_federated_asset_source_config_missing_asset_id(self):
        """Test business rules validation fails when asset_id is missing"""
        source_config = {
            "type": "federated_asset",
            "query": "SELECT * FROM resource"
        }

        errors = self.business_rules._validate_federated_asset_source_config(source_config, 0)
        self.assertGreater(len(errors), 0)
        self.assertIn("asset_id", errors[0].lower())

    def test_validate_external_resource_source_config_valid(self):
        """Test business rules validation for valid external resource source"""
        # Create external resource reference
        marketplace_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="Test Marketplace Connection",
            config={"api_key": "test-key"}
        )

        external_resource = ExternalResourceReference.objects.create(
            asset=self.federated_asset,
            resource_id="res-123",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=1024,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=marketplace_connection.id
        )

        source_config = {
            "type": "external_resource",
            "asset_id": str(self.federated_asset.id),
            "resource_id": "res-123"
        }

        errors = self.business_rules._validate_external_resource_source_config(source_config, 0)
        self.assertEqual(len(errors), 0)

    def test_validate_external_resource_source_config_missing_resource_id(self):
        """Test business rules validation fails when resource_id is missing"""
        source_config = {
            "type": "external_resource",
            "asset_id": str(self.federated_asset.id)
        }

        errors = self.business_rules._validate_external_resource_source_config(source_config, 0)
        self.assertGreater(len(errors), 0)
        self.assertIn("resource_id", errors[0].lower())


class VirtualDatasetFederatedAssetQueryExecutionTest(TestCase):
    """Test query execution against federated asset sources"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create DATA_PROVIDER role
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        # Assign DATA_PROVIDER role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=self.data_provider_role
        )

        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create marketplace connection
        self.marketplace_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="Test Marketplace Connection",
            config={"api_key": "test-key"}
        )

        # Create federated asset with DOWNLOAD_ALL strategy and unique key
        asset_key = f"federated-asset-{uuid.uuid4()}"
        self.federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=asset_key,
            name="Test Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL
        )

        # Create external resource reference
        self.external_resource = ExternalResourceReference.objects.create(
            asset=self.federated_asset,
            resource_id="res-123",
            name="Test Resource",
            url="https://example.com/resource.csv",
            format="CSV",
            size_bytes=1024,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            connection_id=self.marketplace_connection.id
        )

    def test_execute_query_against_federated_asset_metadata_only(self):
        """Test executing metadata-only query against federated asset (virtual dataset creation)."""
        # Set asset to METADATA_ONLY
        self.federated_asset.data_strategy = DataStrategy.METADATA_ONLY
        self.federated_asset.save()

        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(self.federated_asset.id)
            }
        ]

        virtual_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Virtual Dataset",
            query="SELECT * FROM federated_source",
            query_type=QueryType.SQL,
            sources=sources
        )

        self.assertIsNotNone(virtual_dataset)
        self.assertEqual(len(virtual_dataset.sources), 1)

    def test_execute_query_federated_asset_metadata_only_real_path(self):
        """
        Feat1 2.1.3: Execute query against federated_asset source using real code path.
        Uses METADATA_ONLY strategy and VirtualizationService._execute_query_against_federated_asset
        -> _execute_metadata_only_query; no mocks, no stubs.
        """
        from hub.apps.virtualization.models import QueryExecutionStatus, QueryExecutionMode

        self.federated_asset.data_strategy = DataStrategy.METADATA_ONLY
        self.federated_asset.save()

        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(self.federated_asset.id),
                "query": "SELECT * FROM metadata",
            }
        ]
        virtual_dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Federated Metadata Query Dataset",
            query="SELECT * FROM metadata",
            query_type=QueryType.SQL,
            sources=sources,
        )
        self.assertIsNotNone(virtual_dataset)

        execution = self.service.execute_query(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            timeout_seconds=60,
        )

        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        metrics = execution.metrics or {}
        self.assertIn("data", metrics)
        self.assertIn("columns", metrics)
        self.assertIn("row_count", metrics)
        self.assertIn("source_type", metrics)
        self.assertEqual(metrics.get("source_type"), "federated_asset_metadata")
        self.assertGreaterEqual(metrics.get("row_count", 0), 1)
        data = metrics.get("data", [])
        self.assertGreaterEqual(len(data), 1)
        self.assertEqual(data[0].get("asset_id"), str(self.federated_asset.id))
        self.assertEqual(data[0].get("asset_name"), self.federated_asset.name)


class VirtualDatasetFederatedAssetInMemoryConnectorTest(TestCase):
    """
    Test federated asset query execution using the documented in-memory connector.

    No mocks in critical path: uses InMemoryMarketplaceConnector (real implementation
    of DataMarketplaceConnector interface) so that Asset.download_external_resource
    and VirtualizationService._execute_query_against_federated_asset run against
    real code paths with preloaded in-memory content.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant-inmem",
            kyc_status=KYCStatus.VERIFIED
        )
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        self.user = User.objects.create_user(
            email="inmem@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.get_or_create(user=self.user, role=self.data_provider_role)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Connection using IN_MEMORY_FAKE connector with preloaded CSV content
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.IN_MEMORY_FAKE.value,
            name="In-Memory Test Connection",
            config={
                "resources": {
                    "res-csv-1": b"id,name\n1,Alice\n2,Bob\n3,Carol",
                }
            },
        )
        self.federated_asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key=f"federated-inmem-{uuid.uuid4()}",
            name="In-Memory Federated Asset",
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_ALL,
        )
        ExternalResourceReference.objects.create(
            asset=self.federated_asset,
            resource_id="res-csv-1",
            name="Test CSV",
            url="https://example.com/data.csv",
            format="CSV",
            size_bytes=1024,
            marketplace_type=MarketplaceType.IN_MEMORY_FAKE.value,
            connection_id=self.connection.id,
        )

    def test_execute_query_against_federated_asset_with_in_memory_connector(self):
        """Execute query against federated asset using in-memory connector (no mocks)."""
        source = {
            "type": "federated_asset",
            "asset_id": str(self.federated_asset.id),
            "query": "SELECT * FROM resource",
        }
        result = self.service._execute_query_against_federated_asset(
            query="SELECT * FROM resource",
            query_type=QueryType.SQL,
            source=source,
            parameters={},
            timeout_seconds=300,
            source_index=0,
        )
        self.assertIn("data", result)
        self.assertIn("row_count", result)
        self.assertIn("columns", result)
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["source_type"], "file_csv")
        self.assertEqual(len(result["data"]), 3)
        self.assertEqual(result["columns"], ["id", "name"])

    def test_create_virtual_dataset_and_execute_with_in_memory_connector(self):
        """Create virtual dataset with federated_asset source and run execute_query path."""
        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(self.federated_asset.id),
                "query": "SELECT * FROM resource",
            }
        ]
        vd = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="VD In-Memory",
            query="SELECT * FROM federated_source",
            query_type=QueryType.SQL,
            sources=sources,
        )
        self.assertIsNotNone(vd)
        results = self.service._execute_query_against_sources(
            query=vd.query,
            query_type=vd.query_type,
            sources=vd.sources,
            parameters={},
            timeout_seconds=300,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["row_count"], 3)
        self.assertEqual(len(results[0]["data"]), 3)
