"""
Unit tests for ComplianceRun model, RiskLevel, and ComplianceRunStatus.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceRunModelTest(TestCase):
    """Test ComplianceRun model creation, defaults, constraints, and cascades."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset",
        )
        self.job = Job.objects.create(
            tenant=self.tenant, type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING, resource_type="ASSET",
            resource_id=self.asset.id,
        )

    # ── basic creation ──────────────────────────────────────────────────

    def test_create_compliance_run(self):
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
            status=ComplianceRunStatus.PENDING,
        )
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.tenant, self.tenant)
        self.assertEqual(compliance_run.asset, self.asset)
        self.assertEqual(compliance_run.job, self.job)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)

    # ── default values ──────────────────────────────────────────────────

    def test_default_status_is_pending(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        self.assertEqual(run.status, ComplianceRunStatus.PENDING)

    def test_default_scan_mode_is_file_scan(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        self.assertEqual(run.scan_mode, "FILE_SCAN")

    def test_default_warehouse_config_is_empty_dict(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        self.assertEqual(run.warehouse_config, {})

    def test_id_is_auto_generated_uuid(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        self.assertIsNotNone(run.id)
        self.assertIsInstance(run.id, uuid.UUID)

    # ── __str__ ─────────────────────────────────────────────────────────

    def test_str_representation(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        self.assertEqual(str(run), f"Compliance Run {run.id}")

    # ── clean() validation ──────────────────────────────────────────────

    def test_clean_rejects_no_resource(self):
        """At least one of asset / dataset / file must be set."""
        run = ComplianceRun(tenant=self.tenant, status=ComplianceRunStatus.PENDING)
        with self.assertRaises(DjangoValidationError):
            run.clean()

    def test_clean_accepts_asset_only(self):
        run = ComplianceRun(tenant=self.tenant, asset=self.asset, status=ComplianceRunStatus.PENDING)
        # should not raise
        run.clean()

    def test_clean_accepts_dataset_only(self):
        from hub.apps.datasets.models import Dataset
        ds = Dataset.objects.create(tenant=self.tenant, format="CSV")
        run = ComplianceRun(tenant=self.tenant, dataset=ds, status=ComplianceRunStatus.PENDING)
        run.clean()

    def test_clean_accepts_file_only(self):
        from hub.apps.files.models import File
        f = File.objects.create(
            tenant=self.tenant, name="f.csv", size=10,
            storage_path=f"tests/{uuid.uuid4().hex}.csv",
        )
        run = ComplianceRun(tenant=self.tenant, file=f, status=ComplianceRunStatus.PENDING)
        run.clean()

    # ── save() calls full_clean ─────────────────────────────────────────

    def test_save_rejects_missing_resource(self):
        run = ComplianceRun(tenant=self.tenant, status=ComplianceRunStatus.PENDING)
        with self.assertRaises(DjangoValidationError):
            run.save()

    # ── Meta.ordering ───────────────────────────────────────────────────

    def test_meta_ordering_by_created_at_desc(self):
        run_a = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        job2 = Job.objects.create(
            tenant=self.tenant, type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING, resource_type="ASSET",
            resource_id=self.asset.id,
        )
        run_b = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=job2,
        )
        runs = list(ComplianceRun.objects.all())
        # Newest first
        self.assertEqual(runs[0], run_b)
        self.assertEqual(runs[1], run_a)

    # ── CASCADE on tenant delete ───────────────────────────────────────

    def test_cascade_deletes_runs_when_tenant_deleted(self):
        run = ComplianceRun.objects.create(
            tenant=self.tenant, asset=self.asset, job=self.job,
        )
        run_id = run.id
        self.tenant.delete()
        self.assertFalse(ComplianceRun.objects.filter(id=run_id).exists())


class RiskLevelTests(TestCase):
    """Tests for RiskLevel utility methods — fail-closed semantics are
    security-critical (Phase 213.G.4, Phase 231.3 AUDIT.5)."""

    # ── risk_ordinal ───────────────────────────────────────────────────

    def test_risk_ordinal_none_returns_999(self):
        self.assertEqual(RiskLevel.risk_ordinal(None), 999)

    def test_risk_ordinal_unknown_returns_5(self):
        self.assertEqual(RiskLevel.risk_ordinal("UNKNOWN"), 5)

    def test_risk_ordinal_critical(self):
        self.assertEqual(RiskLevel.risk_ordinal("CRITICAL"), 4)

    def test_risk_ordinal_high(self):
        self.assertEqual(RiskLevel.risk_ordinal("HIGH"), 3)

    def test_risk_ordinal_medium(self):
        self.assertEqual(RiskLevel.risk_ordinal("MEDIUM"), 2)

    def test_risk_ordinal_low(self):
        self.assertEqual(RiskLevel.risk_ordinal("LOW"), 1)

    def test_risk_ordinal_none_level_returns_0(self):
        self.assertEqual(RiskLevel.risk_ordinal("NONE"), 0)

    def test_risk_ordinal_garbage_returns_999(self):
        self.assertEqual(RiskLevel.risk_ordinal("INVALID"), 999)

    # ── exceeds (fail-closed) ──────────────────────────────────────────

    def test_exceeds_higher_over_lower(self):
        self.assertTrue(RiskLevel.exceeds("HIGH", "MEDIUM"))

    def test_exceeds_lower_not_over_higher(self):
        self.assertFalse(RiskLevel.exceeds("LOW", "HIGH"))

    def test_exceeds_equal_not_over_same(self):
        self.assertFalse(RiskLevel.exceeds("MEDIUM", "MEDIUM"))

    def test_exceeds_unknown_level_always_exceeds(self):
        """UNKNOWN level = maximally severe (fail-closed)."""
        self.assertTrue(RiskLevel.exceeds("UNKNOWN", "LOW"))

    def test_exceeds_unknown_threshold_always_exceeded(self):
        """UNKNOWN threshold = maximally restrictive (fail-closed)."""
        self.assertTrue(RiskLevel.exceeds("NONE", "UNKNOWN"))

    def test_exceeds_garbage_level_always_exceeds(self):
        self.assertTrue(RiskLevel.exceeds("INVALID", "LOW"))

    def test_exceeds_garbage_threshold_always_exceeded(self):
        self.assertTrue(RiskLevel.exceeds("NONE", "INVALID"))

    def test_exceeds_none_below_low(self):
        self.assertFalse(RiskLevel.exceeds("NONE", "LOW"))

    def test_exceeds_none_level_same_as_none_threshold(self):
        self.assertFalse(RiskLevel.exceeds("NONE", "NONE"))
