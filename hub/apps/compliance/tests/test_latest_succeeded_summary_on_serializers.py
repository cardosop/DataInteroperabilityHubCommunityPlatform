"""Phase 231.3 — latest_compliance_run exposes only SUCCEEDED runs (AUDIT.5)."""

from __future__ import annotations
import pytest

import pytest
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.serializers import AssetSerializer
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class LatestSucceededComplianceSummaryTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="a1",
            name="A",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def _job(self):
        return Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            created_by=self.user,
            status=JobStatus.COMPLETED,
            completed_at=timezone.now(),
        )

    @pytest.mark.integration
    def test_latest_compliance_run_ignores_failed(self):
        job_f = self._job()
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job_f,
            status=ComplianceRunStatus.FAILED,
            risk_level=RiskLevel.CRITICAL,
            completed_at=timezone.now(),
        )
        job_ok = self._job()
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job_ok,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.MEDIUM,
            overall_status="PASS",
            completed_at=timezone.now(),
        )
        data = AssetSerializer(self.asset).data
        self.assertIsNotNone(data["latest_compliance_run"])
        self.assertEqual(data["latest_compliance_run"]["status"], ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(data["latest_compliance_run"]["risk_level"], RiskLevel.MEDIUM)

    @pytest.mark.integration
    def test_latest_compliance_run_null_when_only_failed(self):
        job_f = self._job()
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=job_f,
            status=ComplianceRunStatus.FAILED,
            risk_level=RiskLevel.HIGH,
            completed_at=timezone.now(),
        )
        data = AssetSerializer(self.asset).data
        self.assertIsNone(data["latest_compliance_run"])
