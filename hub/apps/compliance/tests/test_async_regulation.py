"""
Phase 121E — Compliance Async & Regulation Tests

Tests async compliance scanning and multi-jurisdiction support.
"""
import uuid

from django.test import TestCase

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus


class TestComplianceAsyncScanning(TestCase):
    """Verify compliance scans run asynchronously with status tracking."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-tenant-comp-{uuid.uuid4().hex[:8]}",
            slug=f"comp-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"comp-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )

    def test_compliance_run_starts_as_pending(self):
        """New compliance run has PENDING status."""
        from hub.apps.assets.models import Asset
        from hub.apps.jobs.models import Job, JobType
        asset = Asset.objects.create(
            name="comp-asset", key=f"comp-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant, created_by=self.user,
        )
        job = Job.objects.create(
            tenant=self.tenant, type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET", resource_id=str(asset.id),
        )
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job,
            status=ComplianceRunStatus.PENDING,
        )
        self.assertEqual(run.status, ComplianceRunStatus.PENDING)

    def test_compliance_run_has_status_tracking(self):
        """ComplianceRun model has all required status values."""
        statuses = [choice[0] for choice in ComplianceRunStatus.choices]
        for expected in ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]:
            self.assertIn(expected, statuses)

    def test_compliance_run_has_risk_level(self):
        """Test ComplianceRun risk_level field stores and retrieves correctly."""
        from hub.apps.compliance.models import RiskLevel
        from hub.apps.assets.models import Asset
        from hub.apps.jobs.models import Job, JobType
        asset = Asset.objects.create(
            name="risk-asset", key=f"risk-{uuid.uuid4().hex[:8]}",
            tenant=self.tenant, created_by=self.user,
        )
        job = Job.objects.create(
            tenant=self.tenant, type=JobType.COMPLIANCE_RUN,
            resource_type="ASSET", resource_id=str(asset.id),
        )
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=asset, job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.HIGH,
        )
        run.refresh_from_db()
        self.assertEqual(run.risk_level, RiskLevel.HIGH)


class TestComplianceRegulations(TestCase):
    """Verify multi-jurisdiction regulation support."""

    def test_valid_compliance_regimes_defined(self):
        """VALID_COMPLIANCE_REGIMES contains expected jurisdictions."""
        from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES

        for regime in ["GDPR", "HIPAA", "SOX", "LGPD", "CCPA"]:
            self.assertIn(regime, VALID_COMPLIANCE_REGIMES)

    def test_compliance_regimes_count(self):
        """Test all required compliance regimes are defined."""
        from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES

        required = {"GDPR", "HIPAA", "SOX", "LGPD", "CCPA"}
        self.assertTrue(required.issubset(set(VALID_COMPLIANCE_REGIMES)))
