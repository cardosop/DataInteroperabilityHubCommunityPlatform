"""
Phase 234.5 — Per-event-type audit retention policy.

Engineering contract this suite pins (preprod01 tasks.md 234.5):

1.  ``AuditEventRetentionPolicy.clean`` normalises ``regulation_keys``
    (case-insensitive, sorted, deduped) and derives ``retention_days``
    from the Phase 232.7 regulation registry — the SAME helper Phase
    232.7 ``RetentionPolicy`` consults — so audit retention stays
    aligned with data-resource retention under the same regimes.
2.  Explicit ``retention_days`` AND ``regulation_keys`` both being
    set → the registry-derived value wins (regulator contract is
    load-bearing; operator intent is informational).
3.  Neither ``retention_days`` nor a resolvable ``regulation_keys`` →
    ValidationError (the row would otherwise be a no-op).
4.  ``(tenant, event_type)`` is unique — one override per pair.
5.  :func:`resolve_retention_days_for_event_type` returns the
    per-(tenant, event_type) override when enabled, or the supplied
    default otherwise.
6.  ``archive_old_audit_events`` consults per-event-type policies
    BEFORE falling back to the global ``--retention-years`` cutoff:
    a row with a long-retention policy (e.g. GDPR 7y) survives a
    sweep that would archive it under the global 3y default; a row
    with a short-retention policy (e.g. CCPA 2y) is archived earlier
    than the global 3y default.
7.  Disabled policies are ignored — the resolver falls back to the
    default and the archive sweep treats events as global-policy
    rows.
8.  CRUD API: ``/api/v1/audit/event-retention-policies/`` — TENANT_ADMIN-gated,
    tenant-scoped queryset, emits audit events on create/update/delete
    (``AUDIT_EVENT_RETENTION_POLICY_*``).
"""
from __future__ import annotations
import pytest

import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import (
    AuditEvent,
    AuditEventRetentionPolicy,
    resolve_retention_days_for_event_type,
)
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    from datetime import timedelta
    from django.utils import timezone
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
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


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant, *, role: str | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )
    if role:
        role_obj, _ = Role.objects.get_or_create(
            tenant=tenant, name=role, defaults={"description": role}
        )
        UserRole.objects.get_or_create(user=user, tenant=tenant, role=role_obj)
    return user


def _make_archived_event(tenant: Tenant, *, action: str, age_days: int) -> AuditEvent:
    event = create_audit_event(
        resource_type="TEST",
        action=action,
        actor_user=None,
        tenant=tenant,
        details={"smoke": True},
    )
    ts = timezone.now() - timedelta(days=age_days)
    AuditEvent.all_objects.filter(pk=event.pk).update(timestamp=ts)
    event.refresh_from_db()
    return event


# ---------------------------------------------------------------------------
# Tier 1 — model validation / normalisation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditEventRetentionPolicyModel:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    @pytest.mark.integration
    def test_explicit_retention_days_persists(self):
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DSAR_SUBMITTED",
            retention_days=2555,
        )
        row.refresh_from_db()
        assert row.retention_days == 2555
        assert row.regulation_keys == []
        assert row.enabled is True

    @pytest.mark.integration
    def test_regulation_keys_derive_retention_days(self):
        # GDPR data-resource retention is 2555d (7y).
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="BREACH_INCIDENT_OPENED",
            regulation_keys=["GDPR"],
        )
        row.refresh_from_db()
        assert row.retention_days == 2555
        assert row.regulation_keys == ["GDPR"]

    @pytest.mark.integration
    def test_regulation_keys_are_uppercased_sorted_deduped(self):
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DSAR_FULFILLED",
            regulation_keys=[" gdpr ", "UK_GDPR", "gdpr"],
        )
        row.refresh_from_db()
        # Stored canonical form: sorted-uppercase-unique.
        assert row.regulation_keys == ["GDPR", "UK_GDPR"]

    @pytest.mark.integration
    def test_registry_derived_overrides_explicit_retention(self):
        # When both are set, the registry win — regulator contract is
        # load-bearing. Explicit value (1095d) is overridden by GDPR (2555d).
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="COMPLIANCE_RUN_CREATED",
            retention_days=1095,
            regulation_keys=["GDPR"],
        )
        row.refresh_from_db()
        assert row.retention_days == 2555

    @pytest.mark.integration
    def test_strictest_regime_wins_in_multi_regime_list(self):
        # GDPR=2555, CCPA=730 → max = 2555.
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="CONSENT_REVOKED",
            regulation_keys=["CCPA", "GDPR"],
        )
        row.refresh_from_db()
        assert row.retention_days == 2555

    @pytest.mark.integration
    def test_missing_retention_and_regulation_raises_validation_error(self):
        row = AuditEventRetentionPolicy(
            tenant=self.tenant,
            event_type="SOME_EVENT",
            retention_days=None,
            regulation_keys=[],
        )
        with pytest.raises(ValidationError):
            row.full_clean()

    @pytest.mark.integration
    def test_zero_retention_days_rejected(self):
        row = AuditEventRetentionPolicy(
            tenant=self.tenant,
            event_type="SOME_EVENT",
            retention_days=0,
        )
        with pytest.raises(ValidationError):
            row.full_clean()

    @pytest.mark.integration
    def test_empty_event_type_rejected(self):
        row = AuditEventRetentionPolicy(
            tenant=self.tenant,
            event_type="   ",
            retention_days=365,
        )
        with pytest.raises(ValidationError):
            row.full_clean()

    @pytest.mark.integration
    def test_unique_constraint_on_tenant_event_type(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DUP_EVENT",
            retention_days=365,
        )
        # Second row with same (tenant, event_type) fails.
        with pytest.raises((IntegrityError, ValidationError)):
            AuditEventRetentionPolicy.objects.create(
                tenant=self.tenant,
                event_type="DUP_EVENT",
                retention_days=730,
            )

    @pytest.mark.integration
    def test_two_tenants_same_event_type_allowed(self):
        other = _make_tenant()
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant, event_type="SHARED_EVENT", retention_days=365
        )
        # Same event_type on a DIFFERENT tenant is OK.
        AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="SHARED_EVENT", retention_days=730
        )

    @pytest.mark.integration
    def test_unknown_regulation_key_falls_back_to_platform_default(self):
        # Unknown keys yield the platform-default retention (1095d / 3y).
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="EXPERIMENTAL_EVENT",
            regulation_keys=["MADE_UP_REGIME"],
        )
        row.refresh_from_db()
        assert row.retention_days == 1095

    @pytest.mark.integration
    def test_event_type_leading_trailing_whitespace_stripped(self):
        """Phase 234.5 audit-fix Gap 1 — padded event_type must NOT silently break override match.

        Without the strip, an operator typing ``"  DSAR_SUBMITTED  "``
        in the form would create a row that NEVER matches
        ``AuditEvent.action="DSAR_SUBMITTED"`` in the archive sweep
        (byte-for-byte comparison) — the override would appear
        configured but produce zero effect.
        """
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="  DSAR_SUBMITTED  ",
            retention_days=2555,
        )
        row.refresh_from_db()
        assert row.event_type == "DSAR_SUBMITTED"

    @pytest.mark.integration
    def test_update_regulation_keys_recomputes_retention_days(self):
        """Phase 234.5 — saving with new ``regulation_keys`` re-derives ``retention_days``.

        Mirrors the 232.7 ``RetentionPolicy`` contract: every save()
        runs full_clean(), so a PATCH that swaps the regime list must
        update the stored retention to the new registry-derived value.
        Without this, an admin could leave a stale retention_days
        from the prior regime list and the sweep would silently use
        the wrong window.
        """
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="REGIME_SWAP",
            regulation_keys=["CCPA"],  # 730d
        )
        row.refresh_from_db()
        assert row.retention_days == 730

        # Operator escalates the policy to GDPR — the registry must
        # rederive on save, not preserve the old 730d.
        row.regulation_keys = ["GDPR"]
        row.save()
        row.refresh_from_db()
        assert row.retention_days == 2555


# ---------------------------------------------------------------------------
# Tier 2 — resolver
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestResolveRetentionDaysForEventType:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    @pytest.mark.integration
    def test_returns_override_when_policy_active(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="OVERRIDE_ME",
            retention_days=1825,
        )
        result = resolve_retention_days_for_event_type(
            tenant_id=self.tenant.id,
            event_type="OVERRIDE_ME",
            default_days=1095,
        )
        assert result == 1825

    @pytest.mark.integration
    def test_returns_default_when_no_policy(self):
        result = resolve_retention_days_for_event_type(
            tenant_id=self.tenant.id,
            event_type="NO_POLICY_FOR_ME",
            default_days=1095,
        )
        assert result == 1095

    @pytest.mark.integration
    def test_disabled_policy_ignored(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DISABLED_OVERRIDE",
            retention_days=99,
            enabled=False,
        )
        result = resolve_retention_days_for_event_type(
            tenant_id=self.tenant.id,
            event_type="DISABLED_OVERRIDE",
            default_days=1095,
        )
        assert result == 1095

    @pytest.mark.integration
    def test_other_tenant_policy_not_visible(self):
        other = _make_tenant()
        AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="CROSS_TENANT_LEAK", retention_days=99
        )
        result = resolve_retention_days_for_event_type(
            tenant_id=self.tenant.id,
            event_type="CROSS_TENANT_LEAK",
            default_days=1095,
        )
        assert result == 1095

    @pytest.mark.integration
    def test_blank_event_type_returns_default(self):
        assert (
            resolve_retention_days_for_event_type(
                tenant_id=self.tenant.id,
                event_type="",
                default_days=900,
            )
            == 900
        )


# ---------------------------------------------------------------------------
# Tier 3 — archive_old_audit_events integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestArchiveCommandConsultsPerEventTypePolicy:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    def _run(self, *args):
        out, err = StringIO(), StringIO()
        call_command("archive_old_audit_events", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    @pytest.mark.integration
    def test_long_retention_policy_protects_event_under_default(self):
        """GDPR override (7y) blocks archival of a 4y-old row under global 3y."""
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="GDPR_PROTECTED",
            regulation_keys=["GDPR"],  # 2555d
        )
        protected = _make_archived_event(
            self.tenant, action="GDPR_PROTECTED", age_days=4 * 365
        )
        # Also create a plain event of the same age + a different action
        # that has NO per-event-type override — must be archived under
        # the global 3y default.
        unprotected = _make_archived_event(
            self.tenant, action="STANDARD_EVENT", age_days=4 * 365
        )

        self._run("--retention-years=3")

        protected.refresh_from_db()
        unprotected.refresh_from_db()
        assert protected.is_archived is False
        assert unprotected.is_archived is True

    @pytest.mark.integration
    def test_short_retention_policy_archives_earlier_than_default(self):
        """CCPA override (2y) archives a 2.5y-old row under global 3y."""
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="MARKETING_CONSENT",
            regulation_keys=["CCPA"],  # 730d
        )
        ccpa_event = _make_archived_event(
            self.tenant, action="MARKETING_CONSENT", age_days=int(2.5 * 365)
        )
        # Sanity: a same-age event of a non-overridden action survives
        # because it's under the global 3y window.
        survivor = _make_archived_event(
            self.tenant, action="OTHER_EVENT", age_days=int(2.5 * 365)
        )

        self._run("--retention-years=3")

        ccpa_event.refresh_from_db()
        survivor.refresh_from_db()
        assert ccpa_event.is_archived is True
        assert survivor.is_archived is False

    @pytest.mark.integration
    def test_disabled_policy_falls_back_to_global_default(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DISABLED_GDPR",
            regulation_keys=["GDPR"],
            enabled=False,
        )
        evt = _make_archived_event(
            self.tenant, action="DISABLED_GDPR", age_days=4 * 365
        )
        self._run("--retention-years=3")
        evt.refresh_from_db()
        # Disabled policy is invisible → global 3y applies → archived.
        assert evt.is_archived is True

    @pytest.mark.integration
    def test_dry_run_respects_per_event_type_policy(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="DRY_PROTECTED",
            regulation_keys=["GDPR"],
        )
        evt = _make_archived_event(
            self.tenant, action="DRY_PROTECTED", age_days=4 * 365
        )
        self._run("--dry-run", "--retention-years=3")
        evt.refresh_from_db()
        # Dry-run never writes; behaviour is independent of policy.
        assert evt.is_archived is False

    @pytest.mark.integration
    def test_invalid_retention_days_in_override_row_does_not_archive_everything(self):
        """Phase 234.5 audit-fix Gap 2 — defense-in-depth on per-override Q union.

        Manufacture the degenerate case the new validation prevents at
        the model layer: an override row with NULL ``retention_days``
        slipped past validation (e.g. a raw-SQL migration backfill).
        The archive sweep MUST treat the row as no-op rather than
        OR-ing an empty ``Q()`` into the eligibility set and silently
        archiving every audit row for that tenant.

        We bypass ``save()``'s ``full_clean`` via direct ``update()`` —
        the only way a real-world row could end up in this state.
        """
        # First create a valid row, then null out retention_days via
        # raw UPDATE so the validation is bypassed.
        bad = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="POSSIBLY_BAD",
            retention_days=365,
        )
        AuditEventRetentionPolicy.objects.filter(pk=bad.pk).update(
            retention_days=None
        )

        # Unrelated event that SHOULD remain under the global 3y rule.
        survivor = _make_archived_event(
            self.tenant, action="OTHER_KEEP", age_days=int(2 * 365)
        )

        self._run("--retention-years=3")

        survivor.refresh_from_db()
        # If Gap 2 regressed, the empty-Q OR would archive everything
        # in scope. The 2y-old survivor (well under the 3y window)
        # must stay un-archived.
        assert survivor.is_archived is False


# ---------------------------------------------------------------------------
# Tier 4 — DRF API surface
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditEventRetentionPolicyAPI:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.admin = _make_user(self.tenant, role="TENANT_ADMIN")
        self.regular = _make_user(self.tenant)  # no admin role
        self.client = APIClient()
        self.list_url = "/api/v1/audit/event-retention-policies/"

    def _detail_url(self, pk):
        return f"/api/v1/audit/event-retention-policies/{pk}/"

    @pytest.mark.integration
    def test_unauthenticated_request_blocked(self):
        resp = self.client.get(self.list_url)
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.integration
    def test_non_admin_blocked(self):
        self.client.force_authenticate(self.regular)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.integration
    def test_admin_can_list(self):
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="LISTED_EVENT",
            retention_days=365,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        # Pagination shape OR plain list — either is acceptable.
        results = body.get("results", body) if isinstance(body, dict) else body
        event_types = [r["event_type"] for r in results]
        assert "LISTED_EVENT" in event_types

    @pytest.mark.integration
    def test_list_is_tenant_scoped(self):
        other = _make_tenant()
        AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="OTHER_TENANT_EVENT", retention_days=365
        )
        AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant, event_type="MY_TENANT_EVENT", retention_days=365
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.list_url)
        body = resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        event_types = {r["event_type"] for r in results}
        assert "MY_TENANT_EVENT" in event_types
        assert "OTHER_TENANT_EVENT" not in event_types

    @pytest.mark.integration
    def test_admin_can_create_with_regulation_keys(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            self.list_url,
            {
                "event_type": "BREACH_INCIDENT_OPENED",
                "regulation_keys": ["GDPR"],
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        body = resp.json()
        assert body["retention_days"] == 2555
        assert body["regulation_keys"] == ["GDPR"]
        # Audit emission: AUDIT_EVENT_RETENTION_POLICY_CREATED for this tenant.
        audit_match = AuditEvent.objects.filter(
            tenant=self.tenant,
            action=_audit_et.AUDIT_EVENT_RETENTION_POLICY_CREATED,
        )
        assert audit_match.exists()

    @pytest.mark.integration
    def test_admin_can_update_via_patch(self):
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="PATCHED",
            retention_days=365,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            self._detail_url(row.id),
            {"retention_days": 730},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        row.refresh_from_db()
        assert row.retention_days == 730
        assert AuditEvent.objects.filter(
            tenant=self.tenant,
            action=_audit_et.AUDIT_EVENT_RETENTION_POLICY_UPDATED,
        ).exists()

    @pytest.mark.integration
    def test_admin_can_delete(self):
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="TO_DELETE",
            retention_days=365,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(self._detail_url(row.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not AuditEventRetentionPolicy.objects.filter(pk=row.pk).exists()
        assert AuditEvent.objects.filter(
            tenant=self.tenant,
            action=_audit_et.AUDIT_EVENT_RETENTION_POLICY_DELETED,
        ).exists()

    @pytest.mark.integration
    def test_cross_tenant_retrieve_blocked(self):
        other = _make_tenant()
        row = AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="CT_LEAK", retention_days=365
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get(self._detail_url(row.id))
        # Returned 404 (not 403) so tenant existence isn't leaked.
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_create_validates_payload(self):
        self.client.force_authenticate(self.admin)
        # Missing both retention_days and regulation_keys → 400.
        resp = self.client.post(
            self.list_url,
            {"event_type": "BAD"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.integration
    def test_cross_tenant_patch_blocked(self):
        """Phase 234.5 audit-fix Gap 4 — cross-tenant PATCH must 404.

        Defense-in-depth: the queryset filter on ``get_queryset`` is the
        authoritative tenant scope; this test pins that PATCH attempts
        on a foreign-tenant policy fall out of the queryset and surface
        as 404 (NOT 403 — no existence leak), matching the contract
        already pinned for retrieve.
        """
        other = _make_tenant()
        row = AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="CROSS_PATCH", retention_days=365
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            self._detail_url(row.id),
            {"retention_days": 9999},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        row.refresh_from_db()
        assert row.retention_days == 365  # untouched

    @pytest.mark.integration
    def test_cross_tenant_delete_blocked(self):
        """Phase 234.5 audit-fix Gap 4 — cross-tenant DELETE must 404."""
        other = _make_tenant()
        row = AuditEventRetentionPolicy.objects.create(
            tenant=other, event_type="CROSS_DELETE", retention_days=365
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(self._detail_url(row.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        # Row survives in the other tenant.
        assert AuditEventRetentionPolicy.objects.filter(pk=row.pk).exists()

    @pytest.mark.integration
    def test_patch_regulation_keys_updates_retention_days_via_api(self):
        """Phase 234.5 audit-fix Gap 5 — PATCH that swaps regimes re-derives retention.

        Mirror of the model-level ``test_update_regulation_keys_recomputes_retention_days``
        — this version pins the contract end-to-end through the DRF
        write path so a future serializer change that bypasses
        ``full_clean`` fails CI.
        """
        row = AuditEventRetentionPolicy.objects.create(
            tenant=self.tenant,
            event_type="API_REGIME_SWAP",
            regulation_keys=["CCPA"],  # 730d
        )
        assert row.retention_days == 730

        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            self._detail_url(row.id),
            {"regulation_keys": ["GDPR"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        row.refresh_from_db()
        assert row.retention_days == 2555
        # The UPDATED audit event carries the previous retention.
        upd = AuditEvent.objects.filter(
            tenant=self.tenant,
            action=_audit_et.AUDIT_EVENT_RETENTION_POLICY_UPDATED,
        ).order_by("-timestamp").first()
        assert upd is not None
        assert upd.details_json.get("previous_retention_days") == 730
        assert upd.details_json.get("retention_days") == 2555
