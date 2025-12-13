"""
Integration tests for DataHub SDK.

These tests verify that all API modules work together correctly.
"""
import pytest
from datahub_interoperability import DataHubClient, DataHubClientConfig


@pytest.fixture
def config():
    """Create test config."""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )


def test_client_initialization(config):
    """Test that client initializes with all API modules."""
    client = DataHubClient(config)
    
    assert client.contracts is not None
    assert client.lineage is not None
    assert client.scheduled_ingestion is not None
    assert client.versioning is not None
    assert client.governance is not None
    assert client.search is not None
    assert client.observability is not None
    assert client.webhooks is not None


def test_client_api_access(config):
    """Test that all APIs are accessible from client."""
    client = DataHubClient(config)
    
    # Verify all APIs are initialized
    assert hasattr(client, "contracts")
    assert hasattr(client, "lineage")
    assert hasattr(client, "scheduled_ingestion")
    assert hasattr(client, "versioning")
    assert hasattr(client, "governance")
    assert hasattr(client, "search")
    assert hasattr(client, "observability")
    assert hasattr(client, "webhooks")

