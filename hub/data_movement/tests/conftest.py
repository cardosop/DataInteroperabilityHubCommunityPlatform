"""
Shared fixtures for data_movement tests.
"""

from __future__ import annotations

import uuid

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


