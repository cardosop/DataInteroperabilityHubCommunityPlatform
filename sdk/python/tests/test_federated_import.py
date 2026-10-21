"""Unit tests for FederatedImportAPI (284.A.3)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.federated_import import FederatedImportAPI


@pytest.fixture
def mock_client():
    client = MagicMock(spec=DataHubClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def api(mock_client):
    return FederatedImportAPI(mock_client)


class TestListProviders:
    @pytest.mark.asyncio
    async def test_returns_provider_list(self, api, mock_client):
        mock_client.get.return_value = {
            "providers": [{"id": "snowflake_marketplace", "name": "Snowflake Marketplace"}],
            "count": 1,
        }
        result = await api.list_providers()
        assert result["count"] == 1
        assert result["providers"][0]["id"] == "snowflake_marketplace"
        mock_client.get.assert_called_once_with("integrations/federated-import/providers/")


class TestCreateImportJob:
    @pytest.mark.asyncio
    async def test_creates_job_with_required_fields(self, api, mock_client):
        mock_client.post.return_value = {
            "id": "job-1",
            "status": "PENDING",
            "provider_id": "snowflake_marketplace",
            "data_strategy": "METADATA_ONLY",
        }
        result = await api.create_import_job(
            provider_id="snowflake_marketplace",
            credential_ref="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
        )
        assert result["id"] == "job-1"
        assert result["status"] == "PENDING"
        mock_client.post.assert_called_once_with(
            "integrations/federated-import/imports/",
            data={
                "provider_id": "snowflake_marketplace",
                "credential_ref": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "data_strategy": "METADATA_ONLY",
            },
        )

    @pytest.mark.asyncio
    async def test_creates_job_with_optional_fields(self, api, mock_client):
        mock_client.post.return_value = {"id": "job-2", "status": "PENDING"}
        result = await api.create_import_job(
            provider_id="aws_data_exchange",
            credential_ref="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            external_listing_id="ext-123",
            data_strategy="DOWNLOAD_ALL",
        )
        assert result["id"] == "job-2"
        mock_client.post.assert_called_once_with(
            "integrations/federated-import/imports/",
            data={
                "provider_id": "aws_data_exchange",
                "credential_ref": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "external_listing_id": "ext-123",
                "data_strategy": "DOWNLOAD_ALL",
            },
        )


class TestGetImportStatus:
    @pytest.mark.asyncio
    async def test_returns_job_status(self, api, mock_client):
        mock_client.get.return_value = {
            "id": "job-1",
            "type": "FEDERATED_IMPORT",
            "status": "RUNNING",
            "created_at": "2026-05-17T10:00:00Z",
        }
        result = await api.get_import_status("job-1")
        assert result["status"] == "RUNNING"
        mock_client.get.assert_called_once_with("integrations/federated-import/imports/job-1/")


class TestCancelImport:
    @pytest.mark.asyncio
    async def test_cancels_job(self, api, mock_client):
        mock_client.post.return_value = {"id": "job-1", "status": "CANCELLED"}
        result = await api.cancel_import("job-1")
        assert result["status"] == "CANCELLED"
        mock_client.post.assert_called_once_with(
            "integrations/federated-import/imports/job-1/cancel/"
        )
