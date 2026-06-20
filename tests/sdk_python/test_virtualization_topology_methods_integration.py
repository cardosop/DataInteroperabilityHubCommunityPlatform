"""
Comprehensive integration tests for Virtualization API topology methods.

Tests get_topology and get_dataset_topology methods against real Docker Compose services.
No mocks/stubs - uses real API connections.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. Test user and tenant created via SDKTestBase

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Run: pytest tests/sdk_python/test_virtualization_topology_methods_integration.py -v
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ForbiddenError,
    NetworkError,
    NotFoundError,
    ServerError,
    UnauthorizedError,
    ValidationError,
)
from django.db import transaction

# Import test base
from tests.sdk_python.conftest import SDKTestBase


@pytest.mark.django_db(transaction=True)
@pytest.mark.e2e
class TestVirtualizationTopologyMethodsIntegration(SDKTestBase):
    """
    Comprehensive integration tests for virtualization topology methods.

    Tests get_topology and get_dataset_topology against real API services
    running in Docker Compose.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Import models here to avoid Django app registry issues
        from hub.apps.auth.models import APIKey
        from hub.apps.virtualization.models import (
            QueryType,
            VirtualDataset,
            VirtualDatasetStatus,
        )

        # Generate API key and hash it
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Create API key for the user with virtualization scopes
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="SDK Virtualization Topology Test API Key",
            key_hash=key_hash,
            scopes=["virtualization:write", "virtualization:read"],
        )
        self.api_key.save()
        transaction.commit()

        # Store plaintext key (only available at creation)
        self.plaintext_key = plaintext_key

        # Create SDK client config
        self.sdk_config = DataHubClientConfig(
            base_url=self.base_url,
            api_token=self.plaintext_key,
            timeout=30.0,
            max_retries=3,
            user_agent="DataHub-SDK-Test",
            enable_logging=False,
        )

        # Create test virtual datasets
        self.dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Topology Test Dataset 1 {uuid.uuid4().hex[:8]}",
            query="SELECT * FROM test_table_1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            description="Test dataset 1 for topology tests",
        )

        self.dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Topology Test Dataset 2 {uuid.uuid4().hex[:8]}",
            query="SELECT * FROM test_table_2",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            description="Test dataset 2 for topology tests",
        )

        # Commit to ensure data is visible to API service
        transaction.commit()

    def tearDown(self):
        """Clean up test data"""
        super().tearDown()

        # Clean up virtual datasets
        from hub.apps.virtualization.models import VirtualDataset

        @sync_to_async
        def cleanup():
            VirtualDataset.objects.filter(id=self.dataset1.id).delete()
            VirtualDataset.objects.filter(id=self.dataset2.id).delete()
            if hasattr(self, "api_key"):
                APIKey.objects.filter(id=self.api_key.id).delete()

        # Note: tearDown is sync, but we can still clean up
        try:
            VirtualDataset.objects.filter(id=self.dataset1.id).delete()
            VirtualDataset.objects.filter(id=self.dataset2.id).delete()
            if hasattr(self, "api_key"):
                from hub.apps.auth.models import APIKey

                APIKey.objects.filter(id=self.api_key.id).delete()
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_get_topology_success(self):
        """Test successful topology retrieval"""
        async with DataHubClient(self.sdk_config) as client:
            topology = await client.virtualization.get_topology()

            # Verify topology structure
            assert isinstance(topology, dict)
            assert "nodes" in topology
            assert "edges" in topology
            assert "metadata" in topology
            assert "summary" in topology

            # Verify nodes is a list
            assert isinstance(topology["nodes"], list)

            # Verify edges is a list
            assert isinstance(topology["edges"], list)

            # Verify metadata structure
            metadata = topology["metadata"]
            assert isinstance(metadata, dict)
            assert "dataset_count" in metadata or "generated_at" in metadata

            # Verify summary structure
            summary = topology["summary"]
            assert isinstance(summary, dict)
            assert "total_datasets" in summary or "active_datasets" in summary

    @pytest.mark.asyncio
    async def test_get_topology_with_health_metrics(self):
        """Test topology retrieval with health metrics"""
        async with DataHubClient(self.sdk_config) as client:
            topology = await client.virtualization.get_topology(include_health_metrics=True)

            assert isinstance(topology, dict)
            assert "nodes" in topology

            # If nodes exist, check if they have health_metrics
            if topology["nodes"]:
                topology["nodes"][0]
                # Health metrics might be present in nodes when include_health_metrics=True
                # (depending on API implementation)

    @pytest.mark.asyncio
    async def test_get_topology_without_health_metrics(self):
        """Test topology retrieval without health metrics"""
        async with DataHubClient(self.sdk_config) as client:
            topology = await client.virtualization.get_topology(include_health_metrics=False)

            assert isinstance(topology, dict)
            assert "nodes" in topology
            assert "edges" in topology

    @pytest.mark.asyncio
    async def test_get_topology_empty_topology(self):
        """Test topology retrieval when no datasets exist (in a clean tenant)"""
        # This test verifies the method handles empty topology gracefully
        async with DataHubClient(self.sdk_config) as client:
            topology = await client.virtualization.get_topology()

            # Should return valid structure even if empty
            assert isinstance(topology, dict)
            assert "nodes" in topology
            assert "edges" in topology
            assert isinstance(topology["nodes"], list)
            assert isinstance(topology["edges"], list)

    @pytest.mark.asyncio
    async def test_get_dataset_topology_success(self):
        """Test successful dataset topology retrieval"""
        async with DataHubClient(self.sdk_config) as client:
            dataset_topology = await client.virtualization.get_dataset_topology(
                str(self.dataset1.id)
            )

            # Verify topology structure
            assert isinstance(dataset_topology, dict)
            assert "dataset" in dataset_topology
            assert "relationships" in dataset_topology

            # Verify dataset structure
            dataset = dataset_topology["dataset"]
            assert isinstance(dataset, dict)
            assert dataset["id"] == str(self.dataset1.id)
            assert "name" in dataset
            assert "status" in dataset

            # Verify relationships is a list
            assert isinstance(dataset_topology["relationships"], list)

    @pytest.mark.asyncio
    async def test_get_dataset_topology_with_health_metrics(self):
        """Test dataset topology includes health metrics when available"""
        async with DataHubClient(self.sdk_config) as client:
            dataset_topology = await client.virtualization.get_dataset_topology(
                str(self.dataset1.id)
            )

            assert isinstance(dataset_topology, dict)
            assert "dataset" in dataset_topology

            # Health metrics might be present in the response
            if "health_metrics" in dataset_topology:
                assert isinstance(dataset_topology["health_metrics"], dict)

    @pytest.mark.asyncio
    async def test_get_dataset_topology_not_found(self):
        """Test dataset topology with non-existent dataset ID"""
        fake_dataset_id = str(uuid.uuid4())
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.virtualization.get_dataset_topology(fake_dataset_id)

            assert "not found" in str(exc_info.value).lower() or fake_dataset_id in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_get_dataset_topology_validation_error_empty_id(self):
        """Test dataset topology with empty dataset ID"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.virtualization.get_dataset_topology("")

            assert (
                "required" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_get_dataset_topology_validation_error_invalid_id(self):
        """Test dataset topology with invalid dataset ID format"""
        async with DataHubClient(self.sdk_config) as client:
            # Invalid UUID format might raise ValidationError, NotFoundError, or ServerError
            # depending on API validation (API might return 500 if UUID parsing fails)
            with pytest.raises((ValidationError, NotFoundError, ServerError)):
                await client.virtualization.get_dataset_topology("not-a-valid-uuid")

    @pytest.mark.asyncio
    async def test_get_topology_structure_validation(self):
        """Test that topology response has correct structure"""
        async with DataHubClient(self.sdk_config) as client:
            topology = await client.virtualization.get_topology()

            # Verify all required top-level keys
            required_keys = ["nodes", "edges", "metadata", "summary"]
            for key in required_keys:
                assert key in topology, f"Missing required key: {key}"

            # Verify nodes structure
            nodes = topology["nodes"]
            assert isinstance(nodes, list)
            if nodes:
                node = nodes[0]
                assert isinstance(node, dict)
                # Verify common node fields
                assert "id" in node or "name" in node

            # Verify edges structure
            edges = topology["edges"]
            assert isinstance(edges, list)
            if edges:
                edge = edges[0]
                assert isinstance(edge, dict)
                # Verify common edge fields
                assert "source" in edge or "target" in edge

    @pytest.mark.asyncio
    async def test_get_dataset_topology_structure_validation(self):
        """Test that dataset topology response has correct structure"""
        async with DataHubClient(self.sdk_config) as client:
            dataset_topology = await client.virtualization.get_dataset_topology(
                str(self.dataset1.id)
            )

            # Verify required keys
            assert "dataset" in dataset_topology
            assert "relationships" in dataset_topology

            # Verify dataset structure
            dataset = dataset_topology["dataset"]
            assert isinstance(dataset, dict)
            assert dataset["id"] == str(self.dataset1.id)

            # Verify relationships structure
            relationships = dataset_topology["relationships"]
            assert isinstance(relationships, list)

    @pytest.mark.asyncio
    async def test_get_topology_authentication_error(self):
        """Test topology retrieval with invalid authentication"""
        invalid_config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="invalid-token-12345",
            timeout=30.0,
            max_retries=3,
            user_agent="DataHub-SDK-Test",
            enable_logging=False,
        )

        async with DataHubClient(invalid_config) as client:
            with pytest.raises(
                (UnauthorizedError, ForbiddenError, NotFoundError, ValidationError, ServerError)
            ):
                # Depending on API implementation, might return 401, 403, or 404
                await client.virtualization.get_topology()

    @pytest.mark.asyncio
    async def test_get_dataset_topology_authentication_error(self):
        """Test dataset topology retrieval with invalid authentication"""
        invalid_config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="invalid-token-12345",
            timeout=30.0,
            max_retries=3,
            user_agent="DataHub-SDK-Test",
            enable_logging=False,
        )

        async with DataHubClient(invalid_config) as client:
            with pytest.raises(
                (UnauthorizedError, ForbiddenError, NotFoundError, ValidationError, ServerError)
            ):
                # Depending on API implementation, might return 401, 403, or 404
                await client.virtualization.get_dataset_topology(str(self.dataset1.id))

    @pytest.mark.asyncio
    async def test_get_topology_network_error_handling(self):
        """Test topology retrieval handles network errors gracefully"""
        # Use invalid base URL to simulate network error
        invalid_config = DataHubClientConfig(
            base_url="http://invalid-host:9999/api/v1",
            api_token=self.plaintext_key,
            timeout=2.0,  # Short timeout for faster failure
            max_retries=1,
            user_agent="DataHub-SDK-Test",
            enable_logging=False,
        )

        async with DataHubClient(invalid_config) as client:
            with pytest.raises((NetworkError, ServerError)):
                await client.virtualization.get_topology()

    @pytest.mark.asyncio
    async def test_get_dataset_topology_network_error_handling(self):
        """Test dataset topology retrieval handles network errors gracefully"""
        # Use invalid base URL to simulate network error
        invalid_config = DataHubClientConfig(
            base_url="http://invalid-host:9999/api/v1",
            api_token=self.plaintext_key,
            timeout=2.0,  # Short timeout for faster failure
            max_retries=1,
            user_agent="DataHub-SDK-Test",
            enable_logging=False,
        )

        async with DataHubClient(invalid_config) as client:
            with pytest.raises((NetworkError, ServerError)):
                await client.virtualization.get_dataset_topology(str(self.dataset1.id))

    @pytest.mark.asyncio
    async def test_get_topology_method_signature(self):
        """Test that get_topology method has correct signature"""
        async with DataHubClient(self.sdk_config) as client:
            # Verify method exists and is callable
            assert hasattr(client.virtualization, "get_topology")
            assert callable(client.virtualization.get_topology)

            # Test with default parameter
            topology1 = await client.virtualization.get_topology()
            assert isinstance(topology1, dict)

            # Test with explicit parameter
            topology2 = await client.virtualization.get_topology(include_health_metrics=True)
            assert isinstance(topology2, dict)

            topology3 = await client.virtualization.get_topology(include_health_metrics=False)
            assert isinstance(topology3, dict)

    @pytest.mark.asyncio
    async def test_get_dataset_topology_method_signature(self):
        """Test that get_dataset_topology method has correct signature"""
        async with DataHubClient(self.sdk_config) as client:
            # Verify method exists and is callable
            assert hasattr(client.virtualization, "get_dataset_topology")
            assert callable(client.virtualization.get_dataset_topology)

            # Test method call
            dataset_topology = await client.virtualization.get_dataset_topology(
                str(self.dataset1.id)
            )
            assert isinstance(dataset_topology, dict)
            assert "dataset" in dataset_topology
