"""
Security tests: Compliance service (401 unauthenticated, tenant isolation).

Per tasks 29.6.1. Compliance runs API must return 401 when unauthenticated and
enforce tenant isolation for cross-tenant access. Real APIClient; no mocks.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.jobs.models import Job, JobStatus, JobType

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()

# All tests use default django_db (rollback). Run with TEST_DB_SUFFIX=phase13 to avoid deadlock
# when pytest+runserver share hub_test_test_shared (validation script runs this file with phase13).
pytestmark = pytest.mark.django_db(transaction=True)


def test_compliance_runs_list_returns_401_when_unauthenticated():
    """GET /api/v1/compliance/runs/ without auth must return 401 or 403."""
    client = APIClient()
    response = client.get("/api/v1/compliance/runs/")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ), f"Unauthenticated request must return 401 or 403, got {response.status_code}"


def test_compliance_runs_retrieve_returns_401_when_unauthenticated():
    """GET /api/v1/compliance/runs/{id}/ without auth must return 401 or 403."""
    # Use a valid UUID format; object need not exist - unauthenticated returns 401/403 before lookup
    fake_id = uuid.uuid4()
    client = APIClient()
    response = client.get(f"/api/v1/compliance/runs/{fake_id}/")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ), f"Unauthenticated request must return 401 or 403, got {response.status_code}"


@pytest.mark.timeout(60)
def test_compliance_runs_tenant_isolation_cross_tenant_returns_403_or_404():
    """User from tenant A must not access tenant B's compliance run."""
    from .base_idor import IDORTestBase

    t = IDORTestBase()
    t.setUp()
    asset_b = Asset.objects.create(
        tenant=t.tenant_b,
        key=f"comp-asset-b-{uuid.uuid4().hex[:8]}",
        name="Compliance Asset B",
        status=AssetStatus.DRAFT,
        created_by=t.user_b,
    )
    job_b = Job.objects.create(
        tenant=t.tenant_b,
        type=JobType.COMPLIANCE_RUN,
        status=JobStatus.COMPLETED,
        resource_type="ASSET",
        resource_id=str(asset_b.id),
        created_by=t.user_b,
    )
    comp_run_b = ComplianceRun.objects.create(
        tenant=t.tenant_b,
        job=job_b,
        asset=asset_b,
        regulations=["GDPR"],
        risk_level=RiskLevel.LOW,
        status=ComplianceRunStatus.SUCCEEDED,
    )
    t.client.force_authenticate(user=t.user_a)
    response = t.client.get(f"/api/v1/compliance/runs/{comp_run_b.id}/")
    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )
