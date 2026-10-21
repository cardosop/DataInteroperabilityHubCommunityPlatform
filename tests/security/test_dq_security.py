"""
Security tests: DQ service (401 unauthenticated, tenant isolation).

Per tasks 29.6.1. DQ runs API must return 401 when unauthenticated and enforce
tenant isolation for cross-tenant access. Real APIClient; no mocks.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class DQSecurityTest:
    """DQ API security: 401 unauthenticated, tenant isolation."""

    def setUp(self):
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"DQ Sec Tenant A {uid}",
            slug=f"dq-sec-tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"DQ Sec Tenant B {uid}",
            slug=f"dq-sec-tenant-b-{uid}",
        )
        self.user_a = User.objects.create_user(
            email=f"dqseca-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.user_b = User.objects.create_user(
            email=f"dqsecb-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )


def test_dq_runs_list_returns_401_when_unauthenticated():
    """GET /api/v1/dq/runs/ without auth must return 401."""
    client = APIClient()
    response = client.get("/api/v1/dq/runs/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_dq_runs_retrieve_returns_401_when_unauthenticated():
    """GET /api/v1/dq/runs/{id}/ without auth must return 401."""
    import uuid

    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
    from hub.apps.jobs.models import Job, JobStatus, JobType
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import UserStatus

    User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"DQ {uid}", slug=f"dq-{uid}")
    user = User.objects.create_user(
        email=f"dq-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"dq-asset-{uid}",
        name="DQ Asset",
        status=AssetStatus.DRAFT,
        created_by=user,
    )
    job = Job.objects.create(
        tenant=tenant,
        type=JobType.DQ_RUN,
        status=JobStatus.COMPLETED,
        resource_type="ASSET",
        resource_id=str(asset.id),
        created_by=user,
    )
    dq_run = DQRun.objects.create(
        tenant=tenant,
        job=job,
        asset=asset,
        profile_key="intake_basic_gx",
        engine=DQEngine.GREAT_EXPECTATIONS,
        status=DQRunStatus.SUCCEEDED,
    )
    client = APIClient()
    response = client.get(f"/api/v1/dq/runs/{dq_run.id}/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_dq_runs_tenant_isolation_cross_tenant_returns_403_or_404():
    """User from tenant A must not access tenant B's DQ run."""
    from .base_idor import IDORTestBase

    t = IDORTestBase()
    t.setUp()
    asset_b = Asset.objects.create(
        tenant=t.tenant_b,
        key=f"dq-asset-b-{uuid.uuid4().hex[:8]}",
        name="DQ Asset B",
        status=AssetStatus.DRAFT,
        created_by=t.user_b,
    )
    job_b = Job.objects.create(
        tenant=t.tenant_b,
        type=JobType.DQ_RUN,
        status=JobStatus.COMPLETED,
        resource_type="ASSET",
        resource_id=str(asset_b.id),
        created_by=t.user_b,
    )
    dq_run_b = DQRun.objects.create(
        tenant=t.tenant_b,
        job=job_b,
        asset=asset_b,
        profile_key="intake_basic_gx",
        engine=DQEngine.GREAT_EXPECTATIONS,
        status=DQRunStatus.SUCCEEDED,
    )
    t.client.force_authenticate(user=t.user_a)
    response = t.client.get(f"/api/v1/dq/runs/{dq_run_b.id}/")
    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )
