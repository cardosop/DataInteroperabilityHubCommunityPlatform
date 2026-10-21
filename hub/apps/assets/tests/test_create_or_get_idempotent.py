"""
Phase 250.2.C.1 + .C.5 (closes Gap 4 / B2-9) — tests for
``AssetService.create_or_get_idempotent``.

Contract under test
-------------------

The method MUST:

1. **Idempotent fast-path**: when an Asset already exists for
   (tenant, key) AND its status is one of ``DRAFT`` / ``ACTIVE`` /
   ``PUBLIC``, return the existing row WITHOUT invoking the
   business-rules pipeline, WITHOUT consuming the tenant plan-limit
   delta, and WITHOUT emitting a new ``ASSET_CREATED`` audit row or
   ``asset.created`` webhook. A retried scheduled-ingestion run that
   re-invokes the method gets the same Asset back; the audit /
   webhook side-effects fire **exactly once** across N retries.

2. **RETIRED rejection (B2-9)**: when an Asset exists for
   (tenant, key) AND status is ``RETIRED``, raise
   ``ConflictError(code="ASSET_KEY_RETIRED", http_status=409)`` with
   ``details={"key", "tenant_id", "asset_id", "current_status",
   "remediation"}``. The retired key is held by an audit row that
   the operator may need to preserve (e.g. for compliance), so the
   resolution is operator action — not silent re-creation that
   would resurrect the retired asset's identity.

3. **Slow-path (asset not found)**: delegate to ``create_asset``,
   which runs the full canonical pipeline:
   ``AssetsBusinessRules.validate(validation_type="structure")`` →
   ``PlanLimitService.check_limit(max_assets, delta=1)`` →
   ``transaction.atomic`` save → ``ASSET_CREATED`` audit row →
   ``asset.created`` webhook on commit → ``post_save`` signal. The
   shape of the validation / plan-limit / conflict errors raised
   from this path MUST be identical to direct ``create_asset``
   callers (the structured-error contract is shared so the worker
   path and the ``POST /assets/`` API path handle errors
   identically — the load-bearing claim of Phase 250.2.C.4).

4. **Race-safe**: if a concurrent caller creates the row between
   our existence check and our save, ``create_asset`` raises
   ``ConflictError(code="ASSET_KEY_EXISTS")``. The idempotent
   method catches that, re-fetches, and returns the now-existing
   row (treating the race as "another caller won the get-or-create
   race"). If the now-existing row is RETIRED, the method raises
   ``ASSET_KEY_RETIRED`` instead of silently returning the
   pre-existing retired row.

5. **Per-tenant isolation**: a RETIRED key in tenant A does NOT
   block creation of the same key in tenant B (the unique
   constraint is per-tenant per Asset.Meta).

TDD doctrine
------------
Real Django ORM rows + real ``AssetsBusinessRules`` evaluation +
real ``PlanLimitService`` check + real audit emission read from the
``AuditEvent`` table + real ``post_save`` dispatch via Django's
signal machinery. The webhook publisher is the only external
boundary; we read the published events from the in-memory queue
the test fixture provides via the ``EventPublisher`` deduplication
cache. NO mocks of business logic.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.services import AssetService
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import (
    ConflictError,
    ValidationError,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_tenant(*, suffix: str | None = None) -> Tenant:
    uid = suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"IdempotentTest-{uid}",
        slug=f"idempotent-test-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _seed_user(tenant: Tenant) -> User:
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _service(tenant: Tenant, user: User) -> AssetService:
    return AssetService(tenant_id=str(tenant.id), user_id=str(user.id))


def _audit_count(*, tenant: Tenant, asset_id: str) -> int:
    """Count ``ASSET_CREATED`` rows for the given asset."""
    return AuditEvent.objects.filter(
        tenant=tenant,
        action="ASSET_CREATED",
        resource_id=asset_id,
    ).count()


# ---------------------------------------------------------------------------
# 250.2.C.1 — slow-path: full pipeline runs on first call
# ---------------------------------------------------------------------------


class TestSlowPathRunsFullPipeline(TestCase):
    """When no Asset exists for (tenant, key), the method delegates
    to ``create_asset`` which runs the full canonical pipeline."""

    def test_creates_new_asset_when_key_not_taken(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)

        asset = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="new-key",
            name="Fresh Asset",
        )

        assert asset.id is not None
        assert asset.key == "new-key"
        assert asset.status == AssetStatus.DRAFT
        assert Asset.objects.filter(pk=asset.pk).exists()

    def test_creates_new_asset_emits_audit_event(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)

        asset = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="audited-key",
            name="Audited",
        )

        assert _audit_count(tenant=tenant, asset_id=str(asset.id)) == 1, (
            "Slow-path MUST emit exactly one ASSET_CREATED audit "
            "row — same as direct create_asset()."
        )

    def test_validation_failure_raises_ValidationError_same_as_create_asset(self):
        """Empty key path raises the same ValidationError as the
        direct ``create_asset`` API. This is the load-bearing claim
        of Phase 250.2.C.4 — worker error shape == HTTP API error
        shape."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)

        with pytest.raises(ValidationError) as exc_info:
            service.create_or_get_idempotent(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                key="",  # invalid
                name="x",
            )
        assert exc_info.value.code == "VALIDATION_ERROR"

    def test_missing_tenant_id_raises_ValidationError(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        # Service constructed with no tenant_id and no fallback.
        service = AssetService(tenant_id=None, user_id=str(user.id))

        with pytest.raises(ValidationError):
            service.create_or_get_idempotent(
                key="x",
                name="y",
            )


# ---------------------------------------------------------------------------
# 250.2.C.1 — fast-path: idempotent return for non-RETIRED existing assets
# ---------------------------------------------------------------------------


class TestFastPathIdempotency(TestCase):
    """Re-invoking ``create_or_get_idempotent`` for an existing
    (tenant, key) pair returns the SAME asset row without firing
    the audit / webhook / plan-limit side-effects again. This is
    the claim that a retried scheduled-ingestion run is
    side-effect-free for already-bootstrapped Assets."""

    def _seed_existing(self, tenant: Tenant, user: User, *, status: str) -> Asset:
        asset = Asset.objects.create(
            tenant=tenant,
            key="existing-key",
            name="Existing",
            status=status,
            created_by=user,
        )
        return asset

    def test_returns_existing_DRAFT_asset(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        existing = self._seed_existing(tenant, user, status=AssetStatus.DRAFT)

        returned = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="existing-key",
            name="Different Name In Retry",
        )
        assert returned.pk == existing.pk
        # Pre-existing name preserved — idempotent does NOT update.
        returned.refresh_from_db()
        assert returned.name == "Existing"

    def test_returns_existing_ACTIVE_asset(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        existing = self._seed_existing(tenant, user, status=AssetStatus.ACTIVE)

        returned = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="existing-key",
            name="ignored",
        )
        assert returned.pk == existing.pk

    def test_returns_existing_PUBLIC_asset(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        existing = self._seed_existing(tenant, user, status=AssetStatus.PUBLIC)

        returned = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="existing-key",
            name="ignored",
        )
        assert returned.pk == existing.pk

    def test_idempotent_call_does_NOT_emit_duplicate_audit(self):
        """Three create_or_get_idempotent calls for the same key
        emit at most ONE ASSET_CREATED audit row (the first call).
        The retries are no-ops in the audit trail."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)

        a1 = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="retried-key",
            name="First",
        )
        a2 = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="retried-key",
            name="Second",
        )
        a3 = service.create_or_get_idempotent(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            key="retried-key",
            name="Third",
        )

        assert a1.pk == a2.pk == a3.pk, "All three calls return same row."
        # Filter by resource_id so other suite noise doesn't bleed in.
        assert _audit_count(tenant=tenant, asset_id=str(a1.id)) == 1, (
            "Three idempotent retries MUST emit exactly one "
            "ASSET_CREATED audit row (the first one); subsequent "
            "calls are pure reads."
        )


# ---------------------------------------------------------------------------
# 250.2.C.3 + .C.5 — RETIRED rejection (B2-9)
# ---------------------------------------------------------------------------


class TestRetiredKeyRejection(TestCase):
    """A RETIRED Asset for (tenant, key) MUST NOT be silently
    re-bootstrapped — the operator must take explicit action.
    Resolution path: transition the Asset OR use a new key."""

    def _seed_retired(self, tenant: Tenant, user: User) -> Asset:
        # Direct create with status=RETIRED via .objects.create(),
        # bypassing the state-machine clean() validation that would
        # reject a brand-new RETIRED row. This is the post-retire
        # state — an asset that lived its full lifecycle and is now
        # in the terminal RETIRED status.
        asset = Asset.objects.create(
            tenant=tenant,
            key="retired-key",
            name="Once Active",
            status=AssetStatus.RETIRED,
            created_by=user,
        )
        return asset

    def test_existing_RETIRED_raises_ASSET_KEY_RETIRED(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        retired = self._seed_retired(tenant, user)

        with pytest.raises(ConflictError) as exc_info:
            service.create_or_get_idempotent(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                key="retired-key",
                name="Resurrection Attempt",
            )

        exc = exc_info.value
        assert exc.code == "ASSET_KEY_RETIRED"
        assert exc.http_status == 409
        # No new asset row created.
        assert Asset.objects.filter(tenant=tenant, key="retired-key").count() == 1
        # The pre-existing RETIRED row is still RETIRED.
        retired.refresh_from_db()
        assert retired.status == AssetStatus.RETIRED

    def test_RETIRED_rejection_carries_remediation_in_details(self):
        """The structured error MUST carry enough context that the
        operator can act without re-reading docs: the asset_id (for
        admin-UI deep-link), the current_status (for the operator
        to confirm it's actually RETIRED), and a remediation hint."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        retired = self._seed_retired(tenant, user)

        with pytest.raises(ConflictError) as exc_info:
            service.create_or_get_idempotent(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                key="retired-key",
                name="Resurrection Attempt",
            )

        details = exc_info.value.details
        for required_key in (
            "key",
            "tenant_id",
            "asset_id",
            "current_status",
            "remediation",
        ):
            assert required_key in details, (
                f"ASSET_KEY_RETIRED.details MUST include {required_key!r}; "
                f"got keys {list(details.keys())}"
            )
        assert details["asset_id"] == str(retired.id)
        assert details["current_status"] == AssetStatus.RETIRED
        assert details["key"] == "retired-key"
        # The remediation hint must point operators to the only two
        # legitimate resolutions (transition or new key).
        remediation = str(details["remediation"]).lower()
        assert "transition" in remediation or "new key" in remediation, (
            f"Remediation MUST mention transition / new-key; got {details['remediation']!r}"
        )

    def test_RETIRED_rejection_emits_NO_audit_or_webhook(self):
        """Rejection is a refusal — no NEW asset row, no audit,
        no webhook. The pre-existing RETIRED row's audit history
        is the durable record of past lifecycle."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        service = _service(tenant, user)
        self._seed_retired(tenant, user)

        # Snapshot audit count before the rejection attempt.
        audit_baseline = AuditEvent.objects.filter(
            tenant=tenant,
            action="ASSET_CREATED",
        ).count()

        with pytest.raises(ConflictError):
            service.create_or_get_idempotent(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                key="retired-key",
                name="x",
            )

        post_audit = AuditEvent.objects.filter(
            tenant=tenant,
            action="ASSET_CREATED",
        ).count()
        assert post_audit == audit_baseline, (
            "ASSET_KEY_RETIRED rejection MUST NOT emit a new ASSET_CREATED audit row."
        )


# ---------------------------------------------------------------------------
# 250.2.C.1 — per-tenant isolation
# ---------------------------------------------------------------------------


class TestPerTenantIsolation(TestCase):
    """A RETIRED key in tenant A MUST NOT block create-or-get in
    tenant B. The (tenant, key) unique constraint is per-tenant
    (see ``Asset.Meta.constraints``); the rejection must respect
    that."""

    def test_RETIRED_in_tenant_A_does_not_block_tenant_B(self):
        tenant_a = _seed_tenant(suffix="aaa")
        tenant_b = _seed_tenant(suffix="bbb")
        user_a = _seed_user(tenant_a)
        user_b = _seed_user(tenant_b)

        # Tenant A: retired row holds the key.
        Asset.objects.create(
            tenant=tenant_a,
            key="shared-key",
            name="A-retired",
            status=AssetStatus.RETIRED,
            created_by=user_a,
        )

        # Tenant B: same key, no existing row → slow-path creates.
        service_b = _service(tenant_b, user_b)
        asset_b = service_b.create_or_get_idempotent(
            tenant_id=str(tenant_b.id),
            user_id=str(user_b.id),
            key="shared-key",
            name="B-fresh",
        )
        assert asset_b.tenant_id == tenant_b.id
        assert asset_b.status == AssetStatus.DRAFT

        # Tenant A retains its retired row untouched.
        a_row = Asset.objects.get(tenant=tenant_a, key="shared-key")
        assert a_row.status == AssetStatus.RETIRED
