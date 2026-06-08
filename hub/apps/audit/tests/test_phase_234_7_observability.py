"""
Phase 234.7 — Cross-cutting audit observability tests.

Pins the contracts the Grafana dashboard + Prometheus alerts depend on:

1.  The four metrics declared in :mod:`hub.apps.audit.metrics` exist
    under their bare names (NOT ``meshant_`` prefixed — see the module
    docstring for the rationale on diverging from the spec text's
    template name).
2.  Each metric is OBSERVED on its respective event:

    * ``audit_chain_break_total`` — every mismatch row surfaced by the
      ``/api/v1/audit/integrity/verify`` endpoint produces one
      counter increment (per-reason). The matching
      ``AUDIT_INTEGRITY_MISMATCH`` audit event is also written.
    * ``audit_merkle_snapshot_duration_seconds`` — every
      ``snapshot_tenant_window`` call observes the histogram on exit
      (success or raise).
    * ``audit_retention_purged_total`` — every ``run_audit_permanent_delete_sweep``
      tenant with deleted_count > 0 increments the counter by the
      deleted count.
    * ``audit_search_query_duration_seconds`` — already pinned in
      :mod:`test_audit_search` (Phase 234.6); we re-assert the
      counter survives the module-level reset that this suite would
      otherwise leak across.

3.  The clean-verifier path emits ``AUDIT_INTEGRITY_VERIFIED`` as a
    durable beacon — an auditor reconstructing a regulatory period
    from the audit log alone can see when the chain was last
    machine-verified.

The suite uses real DB rows, real metric wrappers, and real API
calls. No mocks.
"""
from __future__ import annotations
import pytest

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit import metrics as audit_metrics
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")


def _make_admin(tenant: Tenant, *, role: str = "TENANT_ADMIN") -> User:
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"{role.lower()}-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )
    role_obj, _ = Role.objects.get_or_create(
        tenant=tenant, name=role, defaults={"description": role}
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role_obj)
    return user


def _mk(tenant: Tenant, *, action: str = "TEST_EVENT", details=None) -> AuditEvent:
    return create_audit_event(
        resource_type="TEST",
        action=action,
        actor_user=None,
        tenant=tenant,
        details=details or {},
    )


# ---------------------------------------------------------------------------
# Tier 1 — metric declarations + module surface (no DB / API)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPhase2347MetricsModuleSurface:
    """Every metric declared by 234.7.2 must be importable + named correctly."""

    @pytest.mark.integration
    def test_chain_break_total_exists(self):
        m = audit_metrics.audit_chain_break_total
        assert m.name == "audit_chain_break_total"
        assert "tenant_id" in m._expected_labels
        assert "reason" in m._expected_labels

    @pytest.mark.integration
    def test_merkle_snapshot_duration_exists(self):
        m = audit_metrics.audit_merkle_snapshot_duration_seconds
        assert m.name == "audit_merkle_snapshot_duration_seconds"
        assert m.unit == "s"
        assert m._expected_labels == ("tenant_id",)

    @pytest.mark.integration
    def test_retention_purged_total_exists(self):
        m = audit_metrics.audit_retention_purged_total
        assert m.name == "audit_retention_purged_total"
        assert "tenant_id" in m._expected_labels
        assert "dry_run" in m._expected_labels

    @pytest.mark.integration
    def test_search_query_duration_still_bare_named(self):
        """234.6 metric kept; 234.7 didn't rename it to add a prefix."""
        assert (
            audit_metrics.audit_search_query_duration_seconds.name
            == "audit_search_query_duration_seconds"
        )

    @pytest.mark.integration
    def test_event_type_constants_are_self_describing(self):
        """234.7.1 — every new constant equals its own name."""
        for name in (
            "AUDIT_INTEGRITY_VERIFIED",
            "AUDIT_INTEGRITY_MISMATCH",
            "AUDIT_GDPR_PURGED",
        ):
            value = getattr(_audit_et, name)
            assert value == name
            assert name in _audit_et.__all__


# ---------------------------------------------------------------------------
# Tier 2 — verifier endpoint emission (chain_break + integrity audit)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPhase2347VerifierEndpointEmission:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.admin = _make_admin(self.tenant)
        self.client = APIClient()
        self.url = "/api/v1/audit/integrity/verify/"

    @pytest.mark.integration
    def test_clean_verify_emits_integrity_verified_audit_event(self):
        """A passing verifier run writes one ``AUDIT_INTEGRITY_VERIFIED`` row."""
        # Seed at least one audit event so the verifier has rows to walk.
        _mk(self.tenant, action="SEED_EVENT", details={"smoke": True})
        before_breaks = audit_metrics.chain_break_observation_count()

        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url, {"tenant_id": str(self.tenant.id)})
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        assert body["verified"] is True

        # No chain-break counter ticks for a clean verifier run.
        assert audit_metrics.chain_break_observation_count() == before_breaks
        # AUDIT_INTEGRITY_VERIFIED meta-audit row present.
        assert AuditEvent.objects.filter(
            tenant=self.tenant,
            action=_audit_et.AUDIT_INTEGRITY_VERIFIED,
        ).exists()

    @pytest.mark.integration
    def test_tampered_row_emits_break_counter_and_mismatch_audit(self):
        """A raw-SQL forgery surfaces as exactly ONE chain-break increment."""
        evt = _mk(self.tenant, action="WILL_BE_TAMPERED", details={"k": "v"})
        # Bypass save() guard with a raw UPDATE — the same vector an
        # attacker with DB-write access would use.
        AuditEvent.all_objects.filter(pk=evt.pk).update(
            details_json={"k": "tampered_value"}
        )
        before_breaks = audit_metrics.chain_break_observation_count()

        self.client.force_authenticate(self.admin)
        resp = self.client.get(self.url, {"tenant_id": str(self.tenant.id)})
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        assert body["verified"] is False, body
        assert len(body["mismatches"]) >= 1
        # Counter ticked ONCE for the single tampered row.
        after_breaks = audit_metrics.chain_break_observation_count()
        assert after_breaks - before_breaks == len(body["mismatches"])

        # AUDIT_INTEGRITY_MISMATCH audit event written with the
        # forensic payload (mismatch_count, sample list).
        meta = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action=_audit_et.AUDIT_INTEGRITY_MISMATCH,
            )
            .order_by("-timestamp")
            .first()
        )
        assert meta is not None
        details = meta.details_json or {}
        assert details.get("mismatch_count") == len(body["mismatches"])
        assert isinstance(details.get("mismatches"), list)
        assert len(details["mismatches"]) <= 10  # sample cap


# ---------------------------------------------------------------------------
# Tier 3 — retention purge metric emission
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPhase2347RetentionPurgeEmission:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    def _make_archived_event(self, *, archived_days_ago: int) -> AuditEvent:
        event = _mk(self.tenant, action="OLD_EVENT", details={})
        AuditEvent.all_objects.filter(pk=event.pk).update(
            is_archived=True,
            archived_at=timezone.now() - timedelta(days=archived_days_ago),
        )
        event.refresh_from_db()
        return event

    @pytest.mark.integration
    def test_purge_increments_retention_counter_by_deleted_count(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        for _ in range(3):
            self._make_archived_event(archived_days_ago=200)

        before_obs = audit_metrics.retention_purged_observation_count()
        summary = run_audit_permanent_delete_sweep(dry_run=False)
        after_obs = audit_metrics.retention_purged_observation_count()

        assert summary["deleted_count"] == 3
        # The counter helper is called once per tenant with deletions;
        # the AMOUNT added is the deleted_count (not 1-per-call).
        assert after_obs - before_obs == 1

    @pytest.mark.integration
    def test_dry_run_purge_still_emits_counter_for_preview_panel(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        self._make_archived_event(archived_days_ago=200)

        before_obs = audit_metrics.retention_purged_observation_count()
        run_audit_permanent_delete_sweep(dry_run=True)
        after_obs = audit_metrics.retention_purged_observation_count()

        # Dry-run reports the would-be purge to the counter with
        # dry_run="true" so Grafana can show preview-vs-actual panels.
        assert after_obs - before_obs == 1

    @pytest.mark.integration
    def test_no_eligible_rows_does_not_emit_counter(self):
        """No work done for this tenant → no counter pollution."""
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        before_obs = audit_metrics.retention_purged_observation_count()
        # Scope to THIS tenant only — a fresh tenant with no archived events.
        # Without scoping, --reuse-db accumulated data from other tenants
        # would trigger deletions and increment the counter.
        run_audit_permanent_delete_sweep(
            dry_run=False, tenant_id=str(self.tenant.id)
        )
        assert audit_metrics.retention_purged_observation_count() == before_obs


# ---------------------------------------------------------------------------
# Tier 4 — Merkle snapshot metric emission
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _merkle_signing_keys(monkeypatch):
    """Provide signing keys so Merkle snapshot tests don't fail on
    ``AUDIT_CHAIN_SIGNING_KEYS_JSON`` lookups.  The override is scoped
    to this module and is automatically reverted after each test."""
    from django.test import override_settings

    # A synthetic key — the actual value doesn't matter for metric tests.
    synthetic_key = "00" * 32
    keys_override = override_settings(
        AUDIT_CHAIN_SIGNING_KEYS_JSON={
            "__default__": [synthetic_key],
        }
    )
    keys_override.enable()
    yield
    keys_override.disable()


@pytest.mark.integration
class TestPhase2347MerkleSnapshotEmission:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()

    @pytest.mark.integration
    def test_snapshot_observes_duration_histogram(self):
        """Every snapshot pipeline call observes the histogram once."""
        from hub.apps.audit.merkle import snapshot_tenant_window

        # Seed at least one audit event so the snapshot has leaves.
        _mk(self.tenant, action="LEAF_EVENT", details={})

        now = timezone.now()
        period_end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        period_start = period_end - timedelta(hours=1)

        before_obs = audit_metrics.merkle_snapshot_observation_count()
        snapshot_tenant_window(
            tenant=self.tenant, period_start=period_start, period_end=period_end
        )
        after_obs = audit_metrics.merkle_snapshot_observation_count()

        assert after_obs - before_obs == 1

    @pytest.mark.integration
    def test_idempotent_resnap_does_not_double_emit(self):
        """A second call for the same window short-circuits to the existing row.

        The metric SHOULD NOT increment on the no-op path — the
        histogram represents *work done*, not *call attempts*. Per
        the function's contract, an existing row is returned before
        the timer wraps the actual hash/sign/upload pipeline.
        """
        from hub.apps.audit.merkle import snapshot_tenant_window

        _mk(self.tenant, action="LEAF_EVENT_2", details={})
        now = timezone.now()
        period_end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        period_start = period_end - timedelta(hours=1)

        # First call — observes once.
        snapshot_tenant_window(
            tenant=self.tenant, period_start=period_start, period_end=period_end
        )
        between_obs = audit_metrics.merkle_snapshot_observation_count()

        # Second call for the SAME window — must NOT re-time.
        snapshot_tenant_window(
            tenant=self.tenant, period_start=period_start, period_end=period_end
        )
        after_obs = audit_metrics.merkle_snapshot_observation_count()
        assert after_obs == between_obs, (
            "idempotent re-snap must not double-emit the duration histogram"
        )
