"""
Phase 231.3.AUDIT.1 — asset list must prefetch compliance_runs (no N+1).

With N=50 assets on one page, compliance run data must load in a single
prefetch query, not one query per asset.
"""

from __future__ import annotations
import pytest
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetListCompliancePrefetchTests(TestCase):
    """Assert compliance_runs are prefetched for the asset list endpoint."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)

    @override_settings(DEBUG=True)
    @pytest.mark.integration
    def test_list_assets_uses_single_query_for_compliance_runs_with_50_assets(self):
        for i in range(50):
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.DRAFT,
                created_by=self.user,
            )
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.COMPLIANCE_RUN,
                resource_type="ASSET",
                resource_id=str(asset.id),
                created_by=self.user,
                status=JobStatus.COMPLETED,
                completed_at=timezone.now(),
            )
            ComplianceRun.objects.create(
                tenant=self.tenant,
                asset=asset,
                job=job,
                status=ComplianceRunStatus.SUCCEEDED,
                risk_level=RiskLevel.LOW,
                completed_at=timezone.now(),
            )

        reset_queries()

        response = self.client.get("/api/v1/assets/", {"page_size": 50})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 50)

        # Filter to actual SELECT/INSERT/UPDATE/DELETE statements;
        # ``SET LOCAL app.rls_compliance_runs_enabled = 'on'`` is the
        # tenant-RLS context-setter (ParameterizedRLS middleware) that
        # mentions ``compliance_runs`` in the GUC name but does no
        # row I/O. Counting it would penalise the prefetch contract
        # for an unrelated wire-up step.
        compliance_queries = [
            q["sql"] for q in connection.queries
            if "compliance_run" in q["sql"].lower()
            and not q["sql"].lstrip().upper().startswith("SET ")
        ]
        self.assertEqual(
            len(compliance_queries),
            1,
            f"Expected exactly 1 compliance_runs SQL query, got {len(compliance_queries)}: "
            + "\n".join(compliance_queries[:5]),
        )
