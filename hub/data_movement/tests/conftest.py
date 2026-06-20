"""
Shared fixtures for data_movement tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from hub.apps.scheduled_export.models import ScheduledExport
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.tenants.models import Tenant


@pytest.fixture
def tenant():
    """Create an active test tenant."""
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"DM-Test-{uid}",
        slug=f"dm-test-{uid}",
        status="ACTIVE",
    )


@pytest.fixture
def tenant_dlt_enabled(tenant):
    """Tenant with data_movement_enabled flag turned on."""
    tenant.data_movement_enabled = True
    tenant.save()
    return tenant


@pytest.fixture
def scheduled_ingestion(tenant):
    """Create a minimal ScheduledIngestion for testing."""
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"test-ingestion-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
        schedule_type="DAILY",
        schedule_config={"time": "02:00"},
        file_pattern=".*",
        created_by=None,
    )


@pytest.fixture
def scheduled_export(tenant):
    """Create a minimal ScheduledExport for testing."""
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"test-export-{uuid.uuid4().hex[:8]}",
        destination_type="S3",
        destination_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
        source_scope={"dataset_ids": [str(uuid.uuid4())]},
        schedule_config={"cron": "0 3 * * *"},
    )


@pytest.fixture
def mock_dlt_pipeline():
    """Mock dlt.pipeline() to avoid requiring the dlt package at test time."""
    mock_load = MagicMock()
    mock_load.load_id = "load-1"
    mock_load.status = "completed"
    mock_load.started_at = None
    mock_load.finished_at = None

    mock_info = MagicMock()
    mock_info.loads = [mock_load]

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_info
    mock_pipeline.dataset_name = "test_dataset"
    mock_pipeline.destination = MagicMock()
    mock_pipeline.destination.__name__ = "filesystem"
    mock_pipeline.last_trace = MagicMock()
    mock_pipeline.last_trace.last_trace = None
    mock_pipeline.state = {}

    with (
        patch("dlt.pipeline", return_value=mock_pipeline),
        patch("dlt.destinations.filesystem", MagicMock()),
        patch("dlt.destinations.__dict__", {"filesystem": MagicMock(), "snowflake": MagicMock()}),
    ):
        yield mock_pipeline


@pytest.fixture
def mock_boto3_sm():
    """Mock boto3 secretsmanager client."""
    mock_client = MagicMock()
    mock_client.create_secret.return_value = {
        "ARN": "arn:aws:secretsmanager:us-east-1:123456:secret:test-secret"
    }
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"access_key_id":"AKIATEST","secret_access_key":"test123"}'
    }
    mock_client.delete_secret.return_value = {}

    with patch("boto3.client", return_value=mock_client):
        yield mock_client
