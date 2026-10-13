"""
W4.3 — Erasure (R2-B6/E1–E8): tenant hard-delete sweep pre-steps, admin
delete via service, partial unique indexes, tombstone filtering, and
user-delete PROTECT pre-checks.

This suite pins the tenant-lifecycle integrity contract end to end:

1.  **R2-B6 (named evidence)** — the 90-day hard-delete sweep COMPLETES
    for a tenant with real users present. Pre-fix, ``User.tenant
    on_delete=RESTRICT`` made every real tenant's hard delete raise and
    skip forever ("cascade_failed") — the erasure contract silently
    failed. The sweep must run an itemized pre-sweep (users, delta-share
    estate, bare-UUID tenant refs, PROTECT user referrers) BEFORE the
    tenant cascade, all recorded in the ``TENANT_HARD_DELETED`` audit
    ``pre_sweep`` details.
2.  **E3** — bare-UUID tenant references (``Event``, ``IdempotencyKey``,
    ``RequestDeduplication``, ``BaaSUsageRecord``) are removed so no
    tenant UUID garbage survives the hard delete.
3.  **E1/E8 (sweep side)** — PROTECT/RESTRICT referrers of the tenant's
    users are swept itemized, so user deletion (and therefore the tenant
    hard delete) cannot be blocked by them.
4.  **E4/R2-I4** — the PLATFORM_ADMIN soft-delete endpoint routes the
    state mutation through ``TenantService.delete_tenant`` (``save()``)
    instead of ``QuerySet.update`` — the post-save tombstone signal
    fires, consumer-side ``ExternalResourceReference`` rows get
    ``source_tenant_deleted_at``, and the 90-day grace anchor
    ``scheduled_for_deletion_at`` is stamped.
5.  **E5** — re-creating a soft-deleted tenant's slug is legitimate
    (partial unique index); an ACTIVE duplicate slug is still refused.
6.  **E6 (named evidence)** — a soft-deleted ``ExternalResourceReference``
    is invisible in access paths: the virtualization source validation
    raises ``EXTERNAL_RESOURCE_NOT_FOUND`` with http_status 404, and
    ``Asset.can_download_resource`` refuses it.

No mocks — real Postgres rows, real sweep runs, real audit rows.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.core.events.models import Event as PersistedEvent
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    # billing is the paid layer — the sanctioned guard covers both
    # core-only absence forms (W7.1).
    try:
        from hub.apps.billing.models import Subscription, SubscriptionStatus
    except (RuntimeError, ModuleNotFoundError):
        pytest.skip("billing (paid layer) not installed in core-only mode")
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(
        tenant=tenant, status=SubscriptionStatus.ACTIVE
    ).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{tenant.slug}",
        defaults={
            "name": f"Test Plan {tenant.slug}",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


def _make_tenant(*, slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_platform_admin(*, tenant: Tenant | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    home_tenant = tenant or _make_tenant(slug_suffix=f"pa-home-{uid}")
    user = User.objects.create_user(
        email=f"pa-{uid}@example.com", password="testpass123", tenant=home_tenant
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _make_regular_user(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _backdate_grace(tenant: Tenant, days: int = 91) -> None:
    past = timezone.now() - timedelta(days=days)
    Tenant.all_objects.filter(pk=tenant.pk).update(
        scheduled_for_deletion_at=past,
        deleted_at=past,
        status=TenantStatus.DELETED,
    )


def _run_sweep():
    from hub.apps.tenants.tenant_hard_delete_sweep import run_tenant_hard_delete_sweep

    return run_tenant_hard_delete_sweep(dry_run=False)


def _hard_delete_audit(tenant_pk) -> AuditEvent | None:
    return (
        AuditEvent.all_objects.filter(
            action=_audit_et.TENANT_HARD_DELETED,
            details_json__tenant_id=str(tenant_pk),
        )
        .order_by("-timestamp")
        .first()
    )


# ---------------------------------------------------------------------------
# R2-B6 — sweep completes with real users present (named evidence)
# ---------------------------------------------------------------------------


class TestSweepCompletesWithRealUsers:
    def test_hard_delete_completes_with_real_users_present(self):
        """The 90-day sweep hard-deletes a tenant that still has users.

        Pre-fix, ``tenant.delete()`` raised ``ProtectedError``
        (``User.tenant`` is RESTRICT) and the sweep skipped the tenant as
        ``cascade_failed`` forever — the erasure contract never fired for
        any real tenant. The sweep must run a user-cleanup pre-step.
        """
        tenant = _make_tenant()
        u1 = _make_regular_user(tenant)
        u2 = _make_regular_user(tenant)
        _backdate_grace(tenant)

        summary = _run_sweep()

        assert not Tenant.all_objects.filter(
            pk=tenant.pk
        ).exists(), "tenant hard-delete must complete with real users present"
        assert not User.objects.filter(pk__in=[u1.pk, u2.pk]).exists()
        assert not any(
            str(tenant.pk) == r.get("tenant_id") and r.get("reason") == "cascade_failed"
            for r in summary.get("skipped", [])
        )
        audit = _hard_delete_audit(tenant.pk)
        assert audit is not None
        pre_sweep = (audit.details_json or {}).get("pre_sweep", {})
        assert (
            pre_sweep.get("users") == 2
        ), "TENANT_HARD_DELETED must itemize the user-cleanup pre-sweep"


class TestSweepBareUuidTenantRefs:
    """E3 — bare-UUID tenant references must not survive the hard delete."""

    def test_bare_uuid_refs_are_swept_itemized(self):
        # baas is the paid layer — the sanctioned guard covers both
        # core-only absence forms (W7.1).
        try:
            from hub.apps.baas.models import BaaSUsageRecord
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("baas (paid layer) not installed in core-only mode")
        from hub.apps.core.bug_prevention.models import (
            IdempotencyKey,
            RequestDeduplication,
        )

        tenant = _make_tenant()
        _make_regular_user(tenant)
        tid = tenant.pk
        PersistedEvent.objects.create(
            event_id=uuid.uuid4(),
            event_type="contract.created",
            event_version="1",
            timestamp=timezone.now(),
            source_service="test",
            tenant_id=tid,
            data={},
        )
        IdempotencyKey.objects.create(
            tenant_id=tid,
            idempotency_key="k1",
            method="POST",
            path="/x",
            request_fingerprint="fp1",
            response_status=201,
            response_body={},
        )
        RequestDeduplication.objects.create(
            tenant_id=tid,
            request_fingerprint=f"fp-{uuid.uuid4().hex}",
            method="POST",
            path="/x",
            request_body_hash="h",
        )
        BaaSUsageRecord.objects.create(
            api_key_id=uuid.uuid4(),
            tenant_id=tid,
            endpoint="/x",
            method="GET",
            status_code=200,
            response_time_ms=5,
            response_size_bytes=1,
            request_size_bytes=1,
            timestamp=timezone.now(),
        )
        _backdate_grace(tenant)

        _run_sweep()

        assert not Tenant.all_objects.filter(pk=tid).exists()
        audit = _hard_delete_audit(tid)
        assert audit is not None
        pre_sweep = (audit.details_json or {}).get("pre_sweep", {})
        assert pre_sweep.get("events") == 1
        assert pre_sweep.get("idempotency_keys") == 1
        assert pre_sweep.get("request_deduplication") == 1
        assert pre_sweep.get("baas_usage_records") == 1


class TestSweepProtectedUserReferrers:
    """E1/E8 (sweep side) — PROTECT referrers of tenant users are swept."""

    def test_protected_user_referrers_are_swept_itemized(self):
        from hub.apps.tenants.models import (
            FeatureFlagFlipApproval,
            ImpersonationSession,
            PlanPriceChangeApproval,
            TenantPlan,
        )

        tenant = _make_tenant()
        plan = TenantPlan.objects.create(
            slug=f"plan-{uuid.uuid4().hex[:8]}",
            name=f"Plan {uuid.uuid4().hex[:8]}",
            tier="FREE",
            limits_json={},
            is_active=True,
        )
        requester = _make_regular_user(tenant)
        approver = _make_regular_user(tenant)
        other_tenant = _make_tenant()
        target = _make_regular_user(other_tenant)
        FeatureFlagFlipApproval.objects.create(
            tenant=tenant,
            flag="sensitive_flag_x",
            requested_value=True,
            requested_by=requester,
            approved_by=approver,
        )
        ImpersonationSession.objects.create(
            impersonator=approver,
            impersonated_user=target,
            impersonator_tenant=tenant,
            impersonated_tenant=other_tenant,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
            max_minutes=60,
        )
        PlanPriceChangeApproval.objects.create(
            requested_by=requester,
            tenant_plan=plan,
            old_price_cents=100,
            new_price_cents=200,
        )
        _backdate_grace(tenant)

        _run_sweep()

        assert not Tenant.all_objects.filter(pk=tenant.pk).exists()
        audit = _hard_delete_audit(tenant.pk)
        assert audit is not None
        pre_sweep = (audit.details_json or {}).get("pre_sweep", {})
        referrers = pre_sweep.get("user_protected_referrers", {})
        assert referrers.get("requested_feature_flag_flips") == 1
        assert referrers.get("impersonation_sessions_started") == 1
        assert referrers.get("requested_price_changes") == 1
        assert pre_sweep.get("users") == 2


# ---------------------------------------------------------------------------
# E4 / R2-I4 — admin delete routes through the service (signal + tombstone)
# ---------------------------------------------------------------------------


class TestAdminDeleteRoutesThroughService:
    def test_admin_delete_fires_tombstone_signal_and_grace_anchor(self):
        """DELETE /api/v1/admin/tenants/{id}/ must go through the service.

        Pre-fix the view mutated state via ``QuerySet.update`` which skips
        ``post_save`` — the federated tombstone signal never fired and the
        consumer-side 90-day grace never materialised. Routing through
        ``TenantService.delete_tenant`` (``save()``) fires the signal:
        consumer-side ``ExternalResourceReference`` rows carrying the
        deleted tenant's ``source_tenant_id`` get ``source_tenant_deleted_at``.
        """
        from hub.apps.assets.models import (
            Asset,
            AssetStatus,
            AssetSourceType,
            ExternalResourceReference,
        )

        target = _make_tenant()
        consumer = _make_tenant()
        consumer_user = _make_regular_user(consumer)
        asset = Asset.objects.create(
            tenant=consumer,
            key=f"fed-{uuid.uuid4().hex[:8]}",
            name="Federated asset",
            status=AssetStatus.ACTIVE,
            source_type=AssetSourceType.FEDERATED,
            created_by=consumer_user,
        )
        err = ExternalResourceReference.objects.create(
            asset=asset,
            resource_id=f"r-{uuid.uuid4().hex[:8]}",
            name="federated copy",
            url="https://safe.example.com/data.csv",
            format="CSV",
            marketplace_type="CKAN_INSTANCE",
            connection_id=uuid.uuid4(),
            source_tenant_id=target.id,
        )
        admin = _make_platform_admin()
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.delete(f"/api/v1/admin/tenants/{target.id}/")

        assert resp.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.status == TenantStatus.DELETED
        assert target.scheduled_for_deletion_at is not None
        err.refresh_from_db()
        assert (
            err.source_tenant_deleted_at is not None
        ), "the soft-delete tombstone signal must stamp consumer-side rows"
        assert AuditEvent.objects.filter(
            action=_audit_et.TENANT_SOFT_DELETED,
            details_json__tenant_id=str(target.id),
        ).exists()

    def test_service_delete_stamps_grace_anchor(self):
        """``TenantService.delete_tenant`` must anchor the 90-day grace.

        Pre-fix, ``Tenant.soft_delete()`` stamped status/deleted_at but NOT
        ``scheduled_for_deletion_at`` — the hard-delete sweep's eligibility
        query never matched, so the service path never reached erasure.
        """
        from hub.apps.tenants.services import TenantService

        tenant = _make_tenant()
        TenantService().delete_tenant(tenant_id=str(tenant.id), reason="test")

        tenant.refresh_from_db()
        assert tenant.status == TenantStatus.DELETED
        assert tenant.deleted_at is not None
        assert (
            tenant.scheduled_for_deletion_at is not None
        ), "delete_tenant must stamp the grace anchor the sweep depends on"


# ---------------------------------------------------------------------------
# E5 — tenant slug partial unique index
# ---------------------------------------------------------------------------


class TestTenantSlugRecreate:
    def test_slug_recreated_after_soft_delete(self):
        """A soft-deleted tenant's slug may be taken by a NEW tenant.

        Pre-fix, ``Tenant.slug`` was globally UNIQUE — re-creating the slug
        of a soft-deleted tenant raised IntegrityError (500) with no
        recovery. The partial unique index (WHERE deleted_at IS NULL)
        makes the re-create legitimate.
        """
        from hub.apps.tenants.services import TenantService

        original = _make_tenant()
        slug = original.slug
        TenantService().delete_tenant(tenant_id=str(original.id), reason="test")

        replacement = Tenant.objects.create(
            name=f"Replacement {uuid.uuid4().hex[:8]}", slug=slug
        )
        assert replacement.slug == slug
        assert replacement.pk != original.pk
        assert Tenant.all_objects.filter(slug=slug).count() == 2

    def test_duplicate_active_slug_still_blocked(self):
        """Two ACTIVE tenants must never share a slug — the partial index
        still enforces uniqueness for non-deleted rows."""
        existing = _make_tenant()

        with pytest.raises(IntegrityError):
            Tenant.objects.create(name="Duplicate", slug=existing.slug)


# ---------------------------------------------------------------------------
# E6 — soft-deleted ExternalResourceReference is invisible in access paths
# ---------------------------------------------------------------------------


class TestSoftDeletedExternalResourceAccess:
    """Named evidence: soft-deleted resource access must be refused."""

    def _seed_asset_and_ref(self, tenant, user, *, soft_delete: bool):
        from hub.apps.assets.models import (
            Asset,
            AssetStatus,
            AssetSourceType,
            DataStrategy,
            ExternalResourceReference,
        )

        asset = Asset.objects.create(
            tenant=tenant,
            key=f"fed-{uuid.uuid4().hex[:8]}",
            name="Federated asset",
            status=AssetStatus.ACTIVE,
            source_type=AssetSourceType.FEDERATED,
            data_strategy=DataStrategy.DOWNLOAD_SELECTIVE,
            created_by=user,
        )
        err = ExternalResourceReference.objects.create(
            asset=asset,
            resource_id=f"r-{uuid.uuid4().hex[:8]}",
            name="federated copy",
            url="https://safe.example.com/data.csv",
            format="CSV",
            marketplace_type="CKAN_INSTANCE",
            connection_id=uuid.uuid4(),
        )
        if soft_delete:
            ExternalResourceReference.all_objects.filter(pk=err.pk).update(
                deleted_at=timezone.now()
            )
            err.refresh_from_db()
        return asset, err

    def test_soft_deleted_resource_is_404_in_access_validation(self):
        """The virtualization source-access gate must refuse a soft-deleted
        resource with EXTERNAL_RESOURCE_NOT_FOUND (404) — the named
        evidence pin.

        Pre-fix, ``ExternalResourceReference.objects.get(...)`` matched
        soft-deleted rows — deletion was cosmetic and the row still
        granted data access. The source-connectivity gate is the access
        path whose catalogue code is 404; the full create flow refuses
        the same row one gate earlier (business rules, 400 — pinned in
        ``test_soft_deleted_resource_refused_by_create_flow``).
        """
        from hub.apps.core.services.base import ValidationError
        from hub.apps.virtualization.services import VirtualizationService

        tenant = _make_tenant()
        user = _make_regular_user(tenant)
        asset, err = self._seed_asset_and_ref(tenant, user, soft_delete=True)

        service = VirtualizationService(tenant_id=str(tenant.id), user_id=str(user.id))
        with pytest.raises(ValidationError) as exc_info:
            service._validate_source_connectivity(
                [
                    {
                        "type": "external_resource",
                        "asset_id": str(asset.id),
                        "resource_id": str(err.resource_id),
                    }
                ],
                str(tenant.id),
            )
        assert exc_info.value.code == "EXTERNAL_RESOURCE_NOT_FOUND"
        assert exc_info.value.http_status == status.HTTP_404_NOT_FOUND

    def test_soft_deleted_resource_refused_by_create_flow(self):
        """The end-to-end create flow also refuses a soft-deleted resource
        (business-rules gate, 400) — the refusal is total, not just the
        execution-time gate."""
        from hub.apps.core.services.base import ValidationError
        from hub.apps.virtualization.services import VirtualizationService

        tenant = _make_tenant()
        user = _make_regular_user(tenant)
        asset, err = self._seed_asset_and_ref(tenant, user, soft_delete=True)

        service = VirtualizationService(tenant_id=str(tenant.id), user_id=str(user.id))
        with pytest.raises(ValidationError) as exc_info:
            service.create_virtual_dataset(
                name="vd-soft-deleted",
                query="SELECT * FROM x",
                query_type="SQL",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                sources=[
                    {
                        "type": "external_resource",
                        "asset_id": str(asset.id),
                        "resource_id": str(err.resource_id),
                    }
                ],
            )
        assert exc_info.value.code == "BUSINESS_RULES_VALIDATION"
        assert exc_info.value.http_status == status.HTTP_400_BAD_REQUEST

    def test_active_resource_still_validates_through_business_rules(self):
        """Contract guard: an ACTIVE resource still passes the access-path
        lookup (the manager filter must not hide live rows)."""
        from hub.apps.assets.models import ExternalResourceReference

        tenant = _make_tenant()
        user = _make_regular_user(tenant)
        asset, err = self._seed_asset_and_ref(tenant, user, soft_delete=False)

        found = ExternalResourceReference.objects.get(
            asset=asset, resource_id=str(err.resource_id)
        )
        assert found.id == err.id
        assert asset.can_download_resource(str(err.resource_id)) is True

    def test_soft_deleted_resource_refused_by_download_gate(self):
        """``Asset.can_download_resource`` must refuse a soft-deleted copy."""
        tenant = _make_tenant()
        user = _make_regular_user(tenant)
        asset, err = self._seed_asset_and_ref(tenant, user, soft_delete=True)

        assert asset.can_download_resource(str(err.resource_id)) is False
        assert not asset.external_resource_references.filter(pk=err.pk).exists()
