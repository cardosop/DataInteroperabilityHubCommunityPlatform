"""
Tests for ComplianceBusinessRules.validate() limit enforcement.

Validates concurrent run limits, recent failure warnings,
resource requirement, and cross-tenant asset rejection.
"""
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.business_rules import ComplianceBusinessRules
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class BusinessRulesLimitsTest(TestCase):
    """Tests for ComplianceBusinessRules concurrent/quota/resource limits."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def _create_job(self):
        return create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )

    def _create_run(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            asset=self.asset,
            job=self._create_job(),
            status=ComplianceRunStatus.PENDING,
        )
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    # ----------------------------------------------------------------
    # 1. Concurrent limit exceeded (default limit = 10)
    # ----------------------------------------------------------------

    def test_concurrent_limit_exceeded(self):
        """10 PENDING runs for tenant causes validation to fail with concurrent limit error."""
        for _ in range(10):
            self._create_run(status=ComplianceRunStatus.PENDING)

        # Build a new (unsaved) run for validation
        new_run = ComplianceRun(
            tenant=self.tenant,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = rules.validate(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="compliance_run",
        )
        # Concurrent limits are enforced in validate_compliance_run_execution (quota path),
        # not in validate() — the latter only runs _validate_compliance_run / tenant / permissions.
        result_all = rules.validate_compliance_run_execution(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="quota",
        )
        concurrent_exceeded = (
            result_all.details.get("concurrent_limit_exceeded", False)
            or any("concurrent" in e.lower() for e in result_all.errors)
        )
        self.assertTrue(
            concurrent_exceeded,
            f"Expected concurrent limit error. Errors: {result_all.errors}, Details: {result_all.details}",
        )

    # ----------------------------------------------------------------
    # 2. Concurrent limit not exceeded
    # ----------------------------------------------------------------

    def test_concurrent_limit_not_exceeded(self):
        """5 PENDING runs (under default limit of 10) passes validation."""
        for _ in range(5):
            self._create_run(status=ComplianceRunStatus.PENDING)

        new_run = ComplianceRun(
            tenant=self.tenant,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = rules.validate(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="compliance_run",
        )
        self.assertTrue(result.is_valid, f"Unexpected errors: {result.errors}")

    # ----------------------------------------------------------------
    # 3. Recent failures warning
    # ----------------------------------------------------------------

    def test_recent_failures_warning(self):
        """6 FAILED runs in last hour produces a warning about recent failures."""
        for _ in range(6):
            self._create_run(status=ComplianceRunStatus.FAILED)

        new_run = ComplianceRun(
            tenant=self.tenant,
            asset=self.asset,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = rules.validate_compliance_run_execution(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="quota",
        )
        has_warning = any("failed" in w.lower() for w in result.warnings)
        self.assertTrue(
            has_warning,
            f"Expected recent-failures warning. Warnings: {result.warnings}",
        )

    # ----------------------------------------------------------------
    # 4. Validation requires at least one resource
    # ----------------------------------------------------------------

    def test_validation_requires_resource(self):
        """Run with no asset/dataset/file fails validation."""
        new_run = ComplianceRun(
            tenant=self.tenant,
            asset=None,
            dataset=None,
            file=None,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = rules.validate(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="compliance_run",
        )
        self.assertFalse(result.is_valid)
        has_resource_error = any("resource" in e.lower() for e in result.errors)
        self.assertTrue(
            has_resource_error,
            f"Expected resource-required error. Errors: {result.errors}",
        )

    # ----------------------------------------------------------------
    # 5. Cross-tenant asset rejected
    # ----------------------------------------------------------------

    def test_cross_tenant_asset_rejected(self):
        """Run with asset from a different tenant fails validation."""
        other_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {other_uid}",
            slug=f"other-tenant-{other_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-{other_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key=f"other-asset-{other_uid}",
            name="Other Asset",
            status=AssetStatus.DRAFT,
            created_by=other_user,
        )

        # Run belongs to self.tenant but references other_tenant's asset
        new_run = ComplianceRun(
            tenant=self.tenant,
            asset=other_asset,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = rules.validate(
            compliance_run=new_run,
            tenant=self.tenant,
            user=self.user,
            validation_type="compliance_run",
        )
        # The business rules should detect the tenant mismatch between
        # the run's tenant and the asset's tenant, or the run's resource
        # not belonging to the same tenant context.
        has_tenant_error = (
            not result.is_valid
            or any("tenant" in e.lower() for e in result.errors)
            or any("tenant" in w.lower() for w in result.warnings)
        )
        self.assertTrue(
            has_tenant_error,
            f"Expected cross-tenant error/warning. Errors: {result.errors}, Warnings: {result.warnings}",
        )
