"""
Phase 260.4.G — file-storage quota tests.

Two layers:

* :class:`GetTenantFileStorageQuotaHelperTest` — pure helper unit
  tests against real DB rows (no API plumbing). Exercises the
  computation paths: empty tenant → 0 bytes, summed sizes, ACTIVE +
  COMPLETED inclusion, DELETED / DELETING exclusion, unlimited
  plan, over-quota cap, zero-limit defensive case, cross-tenant
  isolation.

* :class:`FileQuotaEndpointTest` — HTTP wire contract for
  ``GET /api/v1/files/quota/``: 200 with envelope, tenant scoping,
  unauthenticated → 401/403.

* :class:`FileQuotaUsedMatchesPlanLimitGate` — regression guard:
  the meter and the plan-limit gate MUST report identical
  ``used_bytes`` (the meter is supposed to predict the gate, not
  drift from it).
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.quota import (
    QuotaPlanResolutionError,
    _tenant_file_storage_used_bytes,
    get_tenant_file_storage_quota,
)
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


def _seed_plan(slug: str, *, max_storage_gb: float | None) -> TenantPlan:
    plan, _ = TenantPlan.objects.get_or_create(
        slug=slug,
        defaults={
            "name": slug.upper(),
            "tier": PlanTier.PRO,
            "limits_json": {"max_storage_gb": max_storage_gb},
            "is_active": True,
        },
    )
    plan.limits_json = {**(plan.limits_json or {}), "max_storage_gb": max_storage_gb}
    plan.save(update_fields=["limits_json"])
    return plan


def _seed_tenant(slug_prefix: str, *, plan: TenantPlan) -> Tenant:
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"{slug_prefix}-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.VERIFIED,
        plan=plan,
    )
    return tenant


def _seed_file(
    *,
    tenant: Tenant,
    user: User,
    size: int,
    status_: str = FileStatus.ACTIVE,
) -> File:
    file_id = uuid.uuid4()
    return File.objects.create(
        id=file_id,
        tenant=tenant,
        name=f"file-{file_id}.csv",
        content_type="text/csv",
        size=size,
        status=status_,
        scan_status=FileScanStatus.CLEAN,
        storage_path=f"{tenant.id}/{file_id}/file.csv",
        created_by=user,
    )


class GetTenantFileStorageQuotaHelperTest(TestCase):
    """Pure helper tests — no API plumbing."""

    def setUp(self):
        super().setUp()
        # 100 GB plan for predictable percentage math.
        self.plan = _seed_plan("quota-pro", max_storage_gb=100.0)
        self.tenant = _seed_tenant("quota-tenant", plan=self.plan)
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"quota-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_empty_tenant_returns_zero_used(self):
        result = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(result["used_bytes"], 0)
        self.assertEqual(result["limit_bytes"], 100 * (1024 ** 3))
        self.assertEqual(result["percentage"], 0.0)
        self.assertFalse(result["unlimited"])
        self.assertEqual(result["plan_slug"], "quota-pro")

    @pytest.mark.integration
    def test_sums_active_files(self):
        # Phase 260.6.A — only ACTIVE files contribute to storage
        # quota (legacy ``COMPLETED`` retired via migration 0009).
        # Two ACTIVE files with different sizes confirm the SUM
        # aggregation is unchanged.
        _seed_file(tenant=self.tenant, user=self.user, size=1024, status_=FileStatus.ACTIVE)
        _seed_file(tenant=self.tenant, user=self.user, size=2048, status_=FileStatus.ACTIVE)

        result = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(result["used_bytes"], 1024 + 2048)

    @pytest.mark.integration
    def test_excludes_deleted_and_deleting_files(self):
        # Active row counts.
        _seed_file(tenant=self.tenant, user=self.user, size=1000, status_=FileStatus.ACTIVE)
        # DELETED + DELETING + PENDING / FAILED MUST NOT count — the
        # plan-limit gate (billing/limit_registry) excludes them, so
        # the meter MUST match.
        _seed_file(tenant=self.tenant, user=self.user, size=999_999, status_=FileStatus.DELETED)
        _seed_file(tenant=self.tenant, user=self.user, size=999_999, status_=FileStatus.DELETING)
        _seed_file(tenant=self.tenant, user=self.user, size=999_999, status_=FileStatus.PENDING)

        result = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(
            result["used_bytes"],
            1000,
            f"meter MUST exclude non-storage-consuming statuses; got {result}",
        )

    @pytest.mark.integration
    def test_percentage_is_used_over_limit(self):
        # Use 25% of the 100 GB plan.
        quarter = 25 * (1024 ** 3)
        _seed_file(tenant=self.tenant, user=self.user, size=quarter, status_=FileStatus.ACTIVE)

        result = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(result["used_bytes"], quarter)
        self.assertEqual(result["limit_bytes"], 100 * (1024 ** 3))
        self.assertAlmostEqual(result["percentage"], 25.0, places=1)

    @pytest.mark.integration
    def test_percentage_caps_at_100_when_overquota(self):
        # 200 GB used on a 100 GB plan: percentage caps at 100 but
        # used_bytes preserves the absolute overage so the FE banner
        # can surface "you are 200 GB over your 100 GB plan".
        oversize = 200 * (1024 ** 3)
        _seed_file(tenant=self.tenant, user=self.user, size=oversize, status_=FileStatus.ACTIVE)

        result = get_tenant_file_storage_quota(str(self.tenant.id))
        self.assertEqual(result["used_bytes"], oversize)
        self.assertEqual(result["percentage"], 100.0)

    @pytest.mark.integration
    def test_unlimited_plan_returns_null_limit_and_percentage(self):
        # ENTERPRISE-style plan — null limit means unlimited.
        unlimited_plan = _seed_plan("quota-unlimited", max_storage_gb=None)
        unlimited_tenant = _seed_tenant("unlimited-tenant", plan=unlimited_plan)
        unlimited_user = User.objects.create_user(
            email=f"u-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=unlimited_tenant,
            status=UserStatus.ACTIVE,
        )
        _seed_file(tenant=unlimited_tenant, user=unlimited_user, size=5 * (1024 ** 3))

        result = get_tenant_file_storage_quota(str(unlimited_tenant.id))
        self.assertEqual(result["used_bytes"], 5 * (1024 ** 3))
        self.assertIsNone(result["limit_bytes"])
        self.assertIsNone(result["percentage"])
        self.assertTrue(result["unlimited"])

    @pytest.mark.integration
    def test_zero_limit_plan_treated_as_100_when_any_usage(self):
        # Defensive — a misconfigured plan with max_storage_gb=0
        # would divide-by-zero on naive computation. The helper
        # treats any usage as 100% under a 0-byte cap.
        zero_plan = _seed_plan("quota-zero", max_storage_gb=0.0)
        zero_tenant = _seed_tenant("zero-tenant", plan=zero_plan)
        zero_user = User.objects.create_user(
            email=f"z-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=zero_tenant,
            status=UserStatus.ACTIVE,
        )
        _seed_file(tenant=zero_tenant, user=zero_user, size=1)

        result = get_tenant_file_storage_quota(str(zero_tenant.id))
        self.assertEqual(result["limit_bytes"], 0)
        self.assertEqual(result["percentage"], 100.0)

    @pytest.mark.integration
    def test_cross_tenant_isolation(self):
        # Tenant A has files; tenant B has none. Query for B must
        # NOT see A's bytes.
        _seed_file(tenant=self.tenant, user=self.user, size=10_000)
        plan_b = _seed_plan("quota-b", max_storage_gb=100.0)
        tenant_b = _seed_tenant("b-tenant", plan=plan_b)

        result = get_tenant_file_storage_quota(str(tenant_b.id))
        self.assertEqual(result["used_bytes"], 0)


class GetTenantFileStorageQuotaPlanResolutionTest(TestCase):
    """R1 audit GAP-A — when the tenant has no plan AND no FREE plan
    exists, the helper MUST raise rather than falsely claim
    ``unlimited=True``. A misleading meter would tell the user they
    have unlimited storage right before the limit-gate 5xx-s on
    their next upload.
    """

    @pytest.mark.integration
    def test_helper_raises_when_no_plan_and_no_free_plan(self):
        # Set up a tenant with NO plan AND ensure the FREE plan
        # doesn't exist.
        TenantPlan.objects.filter(slug="free").delete()
        plan_free_remaining = TenantPlan.objects.filter(slug="free", is_active=True).count()
        self.assertEqual(plan_free_remaining, 0, "test setup: FREE plan must not exist")

        tenant = Tenant.objects.create(
            name=f"NoPlan {uuid.uuid4().hex[:8]}",
            slug=f"no-plan-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            plan=None,
        )

        with self.assertRaises(QuotaPlanResolutionError) as ctx:
            get_tenant_file_storage_quota(str(tenant.id))
        self.assertIn("seed_default_plans", str(ctx.exception))


class FileQuotaEndpointTest(TestCase):
    """HTTP wire-contract tests."""

    def setUp(self):
        super().setUp()
        self.plan = _seed_plan("ep-quota-pro", max_storage_gb=10.0)
        self.tenant = _seed_tenant("ep-tenant", plan=self.plan)
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ep-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_quota_endpoint_returns_envelope(self):
        _seed_file(tenant=self.tenant, user=self.user, size=1 * (1024 ** 3))

        response = self.client.get("/api/v1/files/quota/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Envelope shape — every documented key present.
        for key in ("used_bytes", "limit_bytes", "percentage", "plan_slug", "plan_tier", "unlimited"):
            self.assertIn(key, response.data, f"missing key: {key}")
        self.assertEqual(response.data["used_bytes"], 1 * (1024 ** 3))
        self.assertEqual(response.data["limit_bytes"], 10 * (1024 ** 3))
        self.assertAlmostEqual(response.data["percentage"], 10.0, places=1)
        self.assertFalse(response.data["unlimited"])

    @pytest.mark.integration
    def test_quota_endpoint_unauthenticated_returns_401_or_403(self):
        anon = APIClient()
        response = anon.get("/api/v1/files/quota/")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    @pytest.mark.integration
    def test_quota_endpoint_returns_503_when_plan_resolution_fails(self):
        """R1 audit GAP-A — endpoint maps QuotaPlanResolutionError → 503
        ``QUOTA_PLAN_NOT_RESOLVED`` so operators see the platform-level
        misconfiguration rather than the meter falsely claiming
        unlimited storage.
        """
        # Detach the tenant's plan AND remove the FREE fallback so
        # ``_resolve_tenant_plan`` returns None.
        self.tenant.plan = None
        self.tenant.save(update_fields=["plan"])
        TenantPlan.objects.filter(slug="free").delete()

        response = self.client.get("/api/v1/files/quota/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        # Error envelope carries the operator-actionable code so
        # alerting can match on it without parsing the message. The
        # platform emits the flat shape ``{"code": "...", "detail":
        # "...", "details": {...}}`` (see
        # ``hub.apps.core.responses.api_error_response``); the legacy
        # nested ``{"error": {"code": ...}}`` envelope is only emitted
        # by middleware short-circuits — accept either so the test
        # remains stable across the migration.
        body = response.data
        if isinstance(body, dict):
            nested_error = body.get("error")
            code = (
                nested_error.get("code") if isinstance(nested_error, dict)
                else body.get("code")
            )
        else:
            code = None
        self.assertEqual(code, "QUOTA_PLAN_RESOLUTION_FAILED")

    @pytest.mark.integration
    def test_quota_endpoint_isolated_per_tenant(self):
        # Seed a SECOND tenant's data; this user must NOT see it.
        _seed_file(tenant=self.tenant, user=self.user, size=1)
        plan_other = _seed_plan("ep-other-plan", max_storage_gb=10.0)
        other_tenant = _seed_tenant("ep-other-tenant", plan=plan_other)
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        _seed_file(tenant=other_tenant, user=other_user, size=999_999_999)

        response = self.client.get("/api/v1/files/quota/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Saw OUR tenant's 1 byte, NOT the other tenant's 999_999_999.
        self.assertEqual(response.data["used_bytes"], 1)


class FileQuotaUsedMatchesPlanLimitGate(TestCase):
    """Regression guard — the meter MUST report the same used_bytes
    as the plan-limit gate (billing/limit_registry). If the two
    drift, the FE meter would say "you have headroom" while the
    backend gate says "limit exceeded" (or vice versa)."""

    @pytest.mark.integration
    def test_used_bytes_aggregates_match_limit_registry(self):
        plan = _seed_plan("gate-plan", max_storage_gb=10.0)
        tenant = _seed_tenant("gate-tenant", plan=plan)
        user = User.objects.create_user(
            email=f"gate-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        # Phase 260.6.A — only ACTIVE counts for storage (legacy
        # COMPLETED retired). Mix of two ACTIVE + one DELETED to
        # confirm DELETED is excluded.
        _seed_file(tenant=tenant, user=user, size=100, status_=FileStatus.ACTIVE)
        _seed_file(tenant=tenant, user=user, size=200, status_=FileStatus.ACTIVE)
        _seed_file(tenant=tenant, user=user, size=999_999, status_=FileStatus.DELETED)

        from hub.apps.billing.limit_registry import get_resource_count

        meter_bytes = _tenant_file_storage_used_bytes(str(tenant.id))
        gate_bytes = get_resource_count(str(tenant.id), "max_storage_gb")
        self.assertEqual(
            meter_bytes,
            gate_bytes,
            (
                "FileQuota meter and PlanLimitService gate disagree on "
                f"used_bytes (meter={meter_bytes}, gate={gate_bytes}). "
                "The meter MUST match the gate so the UI prediction is "
                "consistent with the 403 the user would actually hit."
            ),
        )
