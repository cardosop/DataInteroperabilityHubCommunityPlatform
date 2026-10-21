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


@pytest.fixture
def w38_catalog_seams(monkeypatch):
    """W3.8 — the catalog-phase seams for suites that run the dlt spine
    to completion: a real in-memory source connector serving CSV content
    (the spine downloads file content through it for catalog-record
    creation), the S3 storage boundary stand-in, and ClamAV disabled
    (the SCAN_UNAVAILABLE branch — no scan-enqueue dependency)."""
    from django.conf import settings

    from hub.apps.orchestration.workflows import scheduled_ingestion as wf

    from .connector_fakes import FakeSourceConnector

    monkeypatch.setattr(settings, "CLAMAV_ENABLED", False)
    connector = FakeSourceConnector()
    monkeypatch.setattr(wf, "_get_source_connector_or_fail", lambda _t: connector)
    # Binding-tolerant: the core calls save_file(tenant_id=...,
    # file_id=..., file_content=...) — all keyword arguments — and the
    # class-attribute patch receives the storage instance positionally.
    monkeypatch.setattr(
        "hub.apps.files.storage.S3StorageClient.save_file",
        lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: (
            f"{tenant_id}/{file_id}/content"
        ),
    )
    return connector


@pytest.fixture
def test_redis_endpoint():
    """Resolve the shared test cache endpoint from the environment.

    In-container batches (``make test-batch-*``) carry
    ``REDIS_URL=redis://redis-cache-test:6379/0`` — the compose stack's
    cache service.  Host-side runs
    (docs/runbooks/HOST_SIDE_VERIFICATION.md) set
    ``REDIS_URL=redis://127.0.0.1:63799/0`` — the ``p313-redis``
    mapping.  Returns ``(host, port)`` after the W16 availability guard:
    CI raises on a missing dependency, local runs keep the graceful
    skip.  Callers pin their own db (db 13 per the runbook convention —
    the app cache lives on db 0 of the same instance).
    """
    import os
    import socket
    from urllib.parse import urlparse

    from envpolicy import environment_guard

    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:63799/0")
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 63799

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((host, port)) != 0:
            # The W16 environment policy: CI RAISES on a missing
            # dependency, local runs keep the graceful skip.
            environment_guard(f"redis ({host}:{port}) unavailable — real Redis required")
            pytest.skip(f"redis ({host}:{port}) unavailable — real Redis required")
    return host, port
