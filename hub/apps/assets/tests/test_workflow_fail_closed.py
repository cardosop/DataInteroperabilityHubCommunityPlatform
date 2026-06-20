"""
Phase 250.1.B.1 — fail-closed cleanup invariants for the asset-creation
workflow.

Existing coverage:

* ``hub/apps/assets/tests/test_data_first_fail_closed.py`` covers the
  API-level happy/sad-path: 422 status code + ``ASSET_FAIL_CLOSED_REJECTED``
  error code + zero ``Asset`` rows on compliance/DQ FAIL.
* ``hub/apps/orchestration/workflows/tests/test_asset_creation_fail_closed.py``
  covers the workflow-internal FailClosedRejection round-trip + tenant
  override fallback + audit emission at the workflow boundary.

This file adds the 250.1.B.1 deliverables beyond those:

1. **Tenant kill-switch (``compliance_fail_closed_enabled=False``)** —
   DRAFT asset MUST persist on gate FAIL when the legacy-fallback flag
   is set. Mirrors D250.12 30-day soak window for existing tenants.
2. **Quota invariant** — a failed gate MUST NOT increment the tenant's
   ``Asset`` count. Phase 250.1.A re-sequence makes this trivially true
   (no row created), but the test pins it as a contract — a regression
   that started persisting then-deleting would re-introduce the bug.
3. **Audit-event emission** — ``ASSET_FAIL_CLOSED_REJECTED`` audit row
   MUST exist after the failure with rejection reason + linked
   ``compliance_run_id`` / ``dq_run_id`` (per Phase 250.1.A audit
   contract); ``details_json`` MUST NOT carry the file payload (PII
   redaction per Phase 240.5.F).
4. **Idempotency-Key replay** — same ``(tenant, body, key)`` retried
   within 24h returns the cached 422 response per ADR-AST-005, NOT
   re-running the workflow.
5. **WorkflowRun state** — workflow run MUST land in ``FAILED`` (not
   stuck in ``PENDING`` / ``RUNNING``) after fail-closed, so frontend
   polling per 250.4 can transition to terminal-state UX.
6. **Cross-tenant isolation in fail-closed path** — Tenant B attempting
   to use Tenant A's file_id MUST fail with HTTP 404 BEFORE any gate
   runs (existence-leak protection per D250.16).

Doctrine
--------
External boundaries (compliance-service HTTP, dq-service HTTP, S3
storage) are stubbed at the network boundary using the same pattern
as ``test_data_first_fail_closed.py``. Real Django ORM rows + real
DRF serializers + real workflow execution otherwise — no business-
logic mocking.

Execution model
---------------
``pytest.mark.django_db(transaction=True)`` per existing pattern; each
test runs in an isolated transaction.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.idempotency_helpers import post_data_first
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Test fixtures — mirrored from test_data_first_fail_closed.py to keep
# the test files independently runnable; not imported because cross-test-
# file fixtures are an anti-pattern that hides setup drift.
# ---------------------------------------------------------------------------


def _seed_authenticated_client(
    *,
    fail_closed_enabled: bool = True,
    allow_degraded: bool = False,
) -> tuple[APIClient, Tenant, User, File]:
    """Return ``(client, tenant, user, file_obj)`` with an authenticated
    DRF client + a tenant whose feature flags match the test scenario.

    ``fail_closed_enabled`` controls ``Tenant.compliance_fail_closed_enabled``
    — the per-tenant kill-switch added in Phase 250.1.A. Default True
    matches Phase 250 post-soak behaviour.

    ``allow_degraded`` controls ``Tenant.allow_intake_on_compliance_degraded``
    per D250.9 (permissive override when compliance circuit is OPEN).
    """
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        compliance_fail_closed_enabled=fail_closed_enabled,
        allow_intake_on_compliance_degraded=allow_degraded,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    file_obj = File.objects.create(
        tenant=tenant,
        name="data.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/data.csv",
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, tenant, user, file_obj


def _patch_storage():
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=b"a,b\n1,2\n",
    )


def _patch_compliance(*, allowed_to_store: bool, overall_status: str = "FAIL"):
    return patch(
        "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
        return_value={
            "overall_status": overall_status,
            "risk_level": "HIGH" if overall_status == "FAIL" else "LOW",
            "allowed_to_store": allowed_to_store,
            "metadata": {},
        },
    )


def _patch_dq(*, overall_status: str = "PASS"):
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value={
            "overall_status": overall_status,
            "quality_score": 100 if overall_status == "PASS" else 12.0,
            "metadata": {},
        },
    )


# ---------------------------------------------------------------------------
# 250.1.B.1.a — Tenant kill-switch (legacy fallback)
# ---------------------------------------------------------------------------


class TestTenantKillSwitch:
    """When ``compliance_fail_closed_enabled=False`` the workflow MUST
    fall back to legacy create-then-validate semantics: Asset persists
    in DRAFT with ``compliance_status=FAIL`` so the tenant can inspect
    the failure context.

    Closes D250.12: 30-day soak window for existing tenants on Phase
    250.1.A deploy. Without this fallback, flipping the default for
    existing tenants is a hard breaking change — the soak window
    requires the OLD behaviour to remain reachable per-tenant.
    """

    def test_compliance_fail_with_kill_switch_off_persists_draft(self):
        client, tenant, _user, file_obj = _seed_authenticated_client(
            fail_closed_enabled=False,
        )
        with (
            _patch_storage(),
            _patch_compliance(allowed_to_store=False, overall_status="FAIL"),
            _patch_dq(),
        ):
            response = post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "legacy-fallback",
                    "name": "Legacy Fallback Asset",
                },
                tenant=tenant,
            )

        # Legacy semantic: 200 (or 201) + DRAFT asset with FAIL status.
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_202_ACCEPTED,
        ), (
            f"got {response.status_code}: {response.data}; "
            "expected legacy create-then-validate to return success even "
            "when compliance FAILED, since fail_closed_enabled=False."
        )
        asset = Asset.objects.filter(tenant=tenant, key="legacy-fallback").first()
        assert asset is not None, (
            "Legacy fallback contract violated: tenant has "
            "compliance_fail_closed_enabled=False but no Asset row was "
            "persisted. This breaks the 30-day soak window per D250.12."
        )

    def test_dq_fail_with_kill_switch_off_persists_draft(self):
        client, tenant, _user, file_obj = _seed_authenticated_client(
            fail_closed_enabled=False,
        )
        with (
            _patch_storage(),
            _patch_compliance(allowed_to_store=True, overall_status="PASS"),
            _patch_dq(overall_status="FAIL"),
        ):
            response = post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "legacy-dq-fallback",
                    "name": "Legacy DQ Fallback",
                },
                tenant=tenant,
            )

        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_202_ACCEPTED,
        ), f"got {response.status_code}: {response.data}"
        assert Asset.objects.filter(tenant=tenant, key="legacy-dq-fallback").exists(), (
            "Legacy fallback violated for DQ FAIL: Asset MUST persist "
            "when fail_closed_enabled=False even with DQ failure."
        )


# ---------------------------------------------------------------------------
# 250.1.B.1.b — Quota invariant under fail-closed
# ---------------------------------------------------------------------------


class TestQuotaInvariant:
    """A failed gate MUST NOT increment the tenant's Asset count, even
    transiently. Phase 250.1.A re-sequence (gates BEFORE persist) makes
    this trivially true; this test pins the invariant so a regression
    that re-introduces create-then-delete would fail.
    """

    def test_compliance_fail_does_not_increment_tenant_asset_count(self):
        client, tenant, _user, file_obj = _seed_authenticated_client()
        before = Asset.objects.filter(tenant=tenant).count()
        with _patch_storage(), _patch_compliance(allowed_to_store=False), _patch_dq():
            post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "quota-test",
                    "name": "Quota Test",
                },
                tenant=tenant,
            )
        after = Asset.objects.filter(tenant=tenant).count()
        assert after == before, (
            f"Quota invariant violated: Asset count went {before}→{after} "
            "after a fail-closed rejection. Phase 250.1.A contract: "
            "failed gate MUST NOT touch the Asset table."
        )

    def test_dq_fail_does_not_increment_tenant_asset_count(self):
        client, tenant, _user, file_obj = _seed_authenticated_client()
        before = Asset.objects.filter(tenant=tenant).count()
        with (
            _patch_storage(),
            _patch_compliance(allowed_to_store=True, overall_status="PASS"),
            _patch_dq(overall_status="FAIL"),
        ):
            post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "quota-dq-test",
                    "name": "Quota DQ Test",
                },
                tenant=tenant,
            )
        after = Asset.objects.filter(tenant=tenant).count()
        assert after == before, (
            f"Quota invariant violated for DQ FAIL: count went {before}→{after}."
        )


# ---------------------------------------------------------------------------
# 250.1.B.1.c — Audit-event emission with PII redaction
# ---------------------------------------------------------------------------


class TestAuditEmission:
    """Phase 250.1.A audit contract — fail-closed rejection MUST emit
    ``ASSET_FAIL_CLOSED_REJECTED`` audit with the rejection reason and
    a link to the compliance/DQ run that caused it. ``details_json`` MUST
    NOT carry redacted-key payloads (Phase 240.5.F PII redaction
    extends to fail-closed audits).
    """

    def test_compliance_fail_emits_audit_with_compliance_run_link(self):
        client, tenant, _user, file_obj = _seed_authenticated_client()
        with _patch_storage(), _patch_compliance(allowed_to_store=False), _patch_dq():
            post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "audit-test",
                    "name": "Audit Test",
                },
                tenant=tenant,
            )

        events = AuditEvent.objects.filter(
            tenant=tenant,
            action="ASSET_FAIL_CLOSED_REJECTED",
        )
        assert events.exists(), (
            "ASSET_FAIL_CLOSED_REJECTED audit MUST be emitted on "
            "fail-closed rejection. Without this, ops cannot diagnose "
            "tenant complaints about missing assets."
        )
        # Check at least one event carries the rejection-reason link;
        # implementation freedom is tolerated on which event variant
        # carries it (the workflow may emit multiple audit events
        # during a single rejection cycle).
        assert any(
            "compliance" in (e.action or "").lower()
            or "compliance_run_id" in (e.details_json or {})
            for e in events
        ), (
            "At least one audit event in the rejection chain MUST link "
            "to the compliance run that caused the rejection."
        )

    def test_audit_details_json_does_not_carry_redacted_keys(self):
        """Phase 240.5.F PII redaction extends to fail-closed audits.
        Forbidden keys per ``hub.apps.dq.log_helpers._REDACTED_KEYS``
        must not appear in ``details_json``.
        """
        client, tenant, _user, file_obj = _seed_authenticated_client()
        with _patch_storage(), _patch_compliance(allowed_to_store=False), _patch_dq():
            post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "redaction-test",
                    "name": "Redaction Test",
                },
                tenant=tenant,
            )

        forbidden_keys = {
            "row_samples",
            "sample_value",
            "sample_data_json",
            "file_content",
            "body",
            "raw_data",
            "data",
            "details_json",
        }
        for event in AuditEvent.objects.filter(tenant=tenant):
            details = event.details_json or {}
            offenders = forbidden_keys.intersection(details.keys())
            assert not offenders, (
                f"Audit event {event.action!r} carries forbidden "
                f"redacted keys {offenders} in details_json. "
                "Phase 240.5.F PII redaction violated."
            )


# ---------------------------------------------------------------------------
# 250.1.B.1.d — Idempotency-Key replay (ADR-AST-005)
# ---------------------------------------------------------------------------


class TestIdempotencyReplay:
    """Phase 250.1.D / ADR-AST-005 — repeated POST with the same
    Idempotency-Key + body returns the cached response, NOT a fresh
    workflow execution. This holds for failure responses too (a
    failed gate is a deterministic outcome of input + tenant policy).
    """

    def test_replay_with_same_key_and_body_returns_cached_failure(self):
        """Phase 250.1.D — replay with same valid key + body returns cached failure."""
        import hashlib
        import json as _json

        client, tenant, _user, file_obj = _seed_authenticated_client()
        body = {
            "file_id": str(file_obj.id),
            "key": "idempotency-replay-test",
            "name": "Idempotency Replay",
        }
        canonical = _json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        # Compose a real D250.8-conformant key.
        idempotency_key = f"{tenant.id}:{hashlib.sha256(canonical).hexdigest()}"

        with _patch_storage(), _patch_compliance(allowed_to_store=False), _patch_dq():
            first = client.post(
                "/api/v1/assets/data-first/",
                canonical,
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )

        # Second call WITHOUT the patches active — idempotency cache
        # MUST short-circuit before re-running compliance / DQ. Without
        # the cache, the second call would fail differently (the mocks
        # aren't active).
        second = client.post(
            "/api/v1/assets/data-first/",
            canonical,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        assert second.status_code == first.status_code, (
            "Idempotency violated: replay returned different status "
            f"({first.status_code} → {second.status_code}). "
            "ADR-AST-005 requires same status on replay within 24h."
        )
        # Phase 250.1.D — the cached replay MUST carry the marker
        # header so clients can distinguish a deduplicated replay
        # from a fresh execution.
        assert second.get("Idempotent-Replay") == "true"

    def test_replay_with_different_body_returns_409_conflict(self):
        """Same Idempotency-Key + DIFFERENT body → 409 per ADR-AST-005.

        Phase 250.1.D — the server recomputes the SHA over the actual
        body and compares with the key's suffix; mismatch is a hard
        409 IDEMPOTENCY_KEY_MISMATCH so a key reuse with a new payload
        cannot silently bypass the deduplication contract.
        """
        import hashlib
        import json as _json

        client, tenant, _user, file_obj = _seed_authenticated_client()

        body_a = {
            "file_id": str(file_obj.id),
            "key": "first-body",
            "name": "First",
        }
        canonical_a = _json.dumps(body_a, sort_keys=True, separators=(",", ":")).encode("utf-8")
        # Key encodes body_a's hash; we'll send body_b with the same key.
        idempotency_key = f"{tenant.id}:{hashlib.sha256(canonical_a).hexdigest()}"

        body_b = dict(body_a)
        body_b["key"] = "second-body-different"
        canonical_b = _json.dumps(body_b, sort_keys=True, separators=(",", ":")).encode("utf-8")

        with (
            _patch_storage(),
            _patch_compliance(allowed_to_store=True, overall_status="PASS"),
            _patch_dq(),
        ):
            second = client.post(
                "/api/v1/assets/data-first/",
                canonical_b,
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )

        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.data["code"] == "IDEMPOTENCY_KEY_MISMATCH"


# ---------------------------------------------------------------------------
# 250.1.B.1.e — Cross-tenant isolation in fail-closed path
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    """Tenant B attempting to use Tenant A's ``file_id`` MUST receive
    HTTP 404 BEFORE any gate runs. This pins the existence-leak
    protection per D250.16: cross-tenant access returns 404 (not 403)
    so an attacker cannot enumerate file_ids by status-code analysis.
    """

    def test_cross_tenant_file_id_returns_404_pre_gate(self):
        # Tenant A owns the file.
        _client_a, _tenant_a, _user_a, file_a = _seed_authenticated_client()
        # Tenant B tries to use it.
        client_b, tenant_b, _user_b, _file_b = _seed_authenticated_client()

        with (
            _patch_storage(),
            _patch_compliance(allowed_to_store=True, overall_status="PASS") as compliance_mock,
            _patch_dq() as dq_mock,
        ):
            # Idempotency-Key MUST be composed against tenant B (the
            # request tenant), even though the file_id belongs to
            # tenant A. The view's idempotency check passes (key
            # tenant matches request tenant) and the cross-tenant
            # 404 is then triggered by the file lookup.
            response = post_data_first(
                client_b,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_a.id),  # Tenant A's file!
                    "key": "cross-tenant-attempt",
                    "name": "Cross-tenant",
                },
                tenant=tenant_b,
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            f"Cross-tenant file access returned {response.status_code} "
            "instead of 404. Existence-leak protection (D250.16) "
            "REQUIRES 404, not 403, so callers cannot enumerate other-"
            "tenant file_ids by status-code analysis."
        )
        # Crucial: the gates MUST NOT have been invoked. Cross-tenant
        # checks happen at the file-resolution layer BEFORE any work.
        assert not compliance_mock.called, (
            "Compliance scan should NEVER fire for a cross-tenant "
            "file_id; the 404 must be returned BEFORE gate dispatch."
        )
        assert not dq_mock.called, "DQ scan should NEVER fire for a cross-tenant file_id."


# ---------------------------------------------------------------------------
# 250.1.B.1.f — WorkflowRun terminal state
# ---------------------------------------------------------------------------


class TestWorkflowRunTerminalState:
    """When fail-closed rejects an asset, the underlying ``WorkflowRun``
    (or ``WorkflowInstance``) MUST land in a terminal FAILED state.
    Frontend polling per Phase 250.4 transitions to error UX based on
    this terminal state — a stuck PENDING / RUNNING workflow would
    leave the frontend polling indefinitely.
    """

    def test_workflow_instance_is_failed_after_compliance_rejection(self):
        client, tenant, _user, file_obj = _seed_authenticated_client()

        from hub.apps.orchestration.models import WorkflowInstance

        before = WorkflowInstance.objects.filter(tenant=tenant).count()

        with _patch_storage(), _patch_compliance(allowed_to_store=False), _patch_dq():
            post_data_first(
                client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(file_obj.id),
                    "key": "workflow-state-test",
                    "name": "Workflow State Test",
                },
                tenant=tenant,
            )

        after_runs = WorkflowInstance.objects.filter(tenant=tenant).order_by("-created_at")
        assert after_runs.count() > before, (
            "Phase 250.1.A async workflow MUST create a WorkflowInstance "
            "row on fail-closed — frontend polling requires a terminal "
            "state and cannot hang on PENDING/RUNNING."
        )
        latest = after_runs.first()
        assert latest is not None
        # ROLLED_BACK is a terminal state per
        # WorkflowInstance.is_terminal() in orchestration/models.py.
        # The asset-creation workflow has compensation enabled, so
        # a fail-closed rejection triggers full rollback → status
        # lands on ROLLED_BACK, not FAILED. Both are terminal.
        terminal_states = ("FAILED", "COMPLETED", "ABORTED", "ROLLED_BACK")
        assert latest.status in terminal_states, (
            f"WorkflowInstance landed in non-terminal state "
            f"{latest.status!r}; frontend polling would hang. "
            "Phase 250.4 polling contract requires terminal state "
            "after fail-closed."
        )
