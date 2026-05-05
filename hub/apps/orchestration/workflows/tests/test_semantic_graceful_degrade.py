"""
Phase 250.7.A TDD pin for the semantic graceful-degrade contract.

Per D250.6, semantic-mapping or search-indexing failures during
asset creation MUST NOT block activation — the asset should land
ACTIVE with a marker on its ``semantic_status`` field so the SPA
can surface "active but not discoverable" inline. The audit row
``ASSET_SEMANTIC_DEGRADED`` is the durable record of the
degradation so audit-replay queries can answer "which activations
silently degraded?" without scanning workflow state.

Tests pin:

1. Field default + choices — ``Asset.semantic_status`` defaults
   to ``UNKNOWN`` and accepts ``UNKNOWN`` / ``PASS`` / ``WARN``
   / ``FAIL``.

2. ``_index_for_search_task`` — when ``SearchIndexer.index_asset``
   raises, the task (a) does NOT propagate the exception (asset
   still activates), (b) sets ``asset.semantic_status = "FAIL"``,
   (c) emits ``ASSET_SEMANTIC_DEGRADED`` audit, (d) returns
   ``{indexed: False, semantic_status: "FAIL"}`` so downstream
   workflow state can surface the degradation.

3. ``_activate_asset_task`` semantic-mapping — when
   ``map_asset_to_semantic`` raises, same contract: asset still
   activates, audit emitted, ``semantic_status`` flipped to FAIL.

4. PASS / clean path — when both calls succeed, ``semantic_status``
   transitions to ``PASS`` and NO ``ASSET_SEMANTIC_DEGRADED`` audit
   row fires.

Tests use real Django ORM rows + the canonical
``ensure_user_has_data_provider_role`` helper. The ``SearchIndexer``
+ ``map_asset_to_semantic`` failure injection uses
``unittest.mock.patch`` at the module-import boundary — both are
stable system boundaries (search index, Fuseki RPC) where
fault-injection is the standard pattern (matching the convention
established by Phase 250.2.B's audit-best-effort tests).
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T {uid}",
        slug=f"t-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


def _seed_asset_and_workflow(tenant, user, *, status=AssetStatus.DRAFT):
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"a-{uuid.uuid4().hex[:6]}",
        name="Test Asset",
        status=status,
        created_by=user,
    )
    wf_def = WorkflowDefinition.objects.create(
        name="asset_creation_test",
        version="2.0.0",
        dsl_json={"version": "2.0.0", "steps": []},
        is_active=True,
        created_by=user,
    )
    instance = WorkflowInstance.objects.create(
        workflow_definition=wf_def,
        workflow_name="asset_creation_test",
        workflow_version="2.0.0",
        tenant=tenant,
        status=WorkflowStatus.RUNNING,
        input_data={},
        state_data={"asset_id": str(asset.id)},
        created_by=user,
    )
    return asset, instance


# ---------------------------------------------------------------------------
# 250.7.A.1 — field shape
# ---------------------------------------------------------------------------


class AssetSemanticStatusFieldTest(TestCase):
    """``Asset.semantic_status`` defaults to UNKNOWN and accepts the
    four values from the SemanticStatus enum."""

    def test_default_unknown(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}",
            name="A", status=AssetStatus.DRAFT,
        )
        assert asset.semantic_status == "UNKNOWN"

    def test_accepts_all_four_values(self):
        tenant, user = _seed()
        for value in ("UNKNOWN", "PASS", "WARN", "FAIL"):
            asset = Asset.objects.create(
                tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}-{value}",
                name="A", status=AssetStatus.DRAFT,
                semantic_status=value,
            )
            assert asset.semantic_status == value


# ---------------------------------------------------------------------------
# 250.7.A.2 — index_for_search degradation contract
# ---------------------------------------------------------------------------


class IndexForSearchDegradedTest(TestCase):
    """When ``SearchIndexer.index_asset`` raises, the task degrades
    gracefully (no exception propagated; asset still activates)
    AND emits ``ASSET_SEMANTIC_DEGRADED`` AND sets the
    ``semantic_status`` to FAIL."""

    def test_indexer_failure_emits_audit_and_marks_fail(self):
        tenant, user = _seed()
        asset, instance = _seed_asset_and_workflow(
            tenant, user, status=AssetStatus.ACTIVE,
        )
        before = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()

        with patch(
            "hub.apps.orchestration.workflows.asset_creation.SearchIndexer.index_asset",
            side_effect=RuntimeError("search index unreachable"),
        ):
            result = AssetCreationWorkflow._index_for_search_task(
                input_data={}, instance=instance, step=None,
            )

        # Task did NOT propagate the exception.
        assert result["indexed"] is False
        assert result.get("semantic_status") == "FAIL"

        # Asset row was marked FAIL.
        asset.refresh_from_db()
        assert asset.semantic_status == "FAIL"
        # AND status remains ACTIVE — the degradation MUST NOT
        # demote the asset (D250.6 — degradation is observability,
        # not enforcement).
        assert asset.status == AssetStatus.ACTIVE

        # Audit row emitted.
        after = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).order_by("-created_at")
        assert after.count() - before == 1
        ev = after.first()
        assert ev.details_json["asset_id"] == str(asset.id)
        assert ev.details_json["degraded_step"] == "index_for_search"
        assert "search index unreachable" in ev.details_json["error"]


# ---------------------------------------------------------------------------
# 250.7.A.4 — semantic-mapping degradation in activation
# ---------------------------------------------------------------------------


class ActivationSemanticMappingDegradedTest(TestCase):
    """When ``map_asset_to_semantic`` raises during activation, the
    activation MUST still succeed, audit fires, and
    ``semantic_status`` flips to FAIL."""

    def test_semantic_map_failure_during_activation_keeps_asset_active(self):
        tenant, user = _seed()
        # Pre-condition: asset is DRAFT with all gates green (so
        # activation will fire). The asset will be activated by the
        # task; we only need the basic shape here.
        from hub.apps.assets.models import DQStatus, ComplianceStatus

        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="Active",
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=user,
        )
        wf_def = WorkflowDefinition.objects.create(
            name="asset_creation_test",
            version="2.0.0",
            dsl_json={"version": "2.0.0", "steps": []},
            is_active=True,
            created_by=user,
        )
        instance = WorkflowInstance.objects.create(
            workflow_definition=wf_def,
            workflow_name="asset_creation_test",
            workflow_version="2.0.0",
            tenant=tenant,
            status=WorkflowStatus.RUNNING,
            input_data={"auto_activate": True},
            state_data={
                "asset_id": str(asset.id),
                "auto_activate": True,
            },
            created_by=user,
        )

        before = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()

        with patch(
            "hub.apps.orchestration.workflows.asset_creation.map_asset_to_semantic",
            side_effect=RuntimeError("Fuseki unreachable"),
        ):
            # The activate task is the wrapper that calls
            # map_asset_to_semantic; we exercise it directly.
            AssetCreationWorkflow._activate_asset_task(
                input_data={"auto_activate": True},
                instance=instance,
                step=None,
            )

        asset.refresh_from_db()
        # Asset was promoted to ACTIVE despite the semantic failure.
        assert asset.status == AssetStatus.ACTIVE
        # And marked FAIL on semantic_status so the SPA can render
        # the degraded banner.
        assert asset.semantic_status == "FAIL"

        after = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).order_by("-created_at")
        assert after.count() - before == 1
        ev = after.first()
        assert ev.details_json["degraded_step"] == "activate_asset_semantic_map"
        assert "Fuseki unreachable" in ev.details_json["error"]


# ---------------------------------------------------------------------------
# Clean path — no degradation, no audit
# ---------------------------------------------------------------------------


class IndexForSearchPassTest(TestCase):
    """When ``SearchIndexer.index_asset`` succeeds, ``semantic_status``
    flips to PASS and NO ``ASSET_SEMANTIC_DEGRADED`` audit row
    fires."""

    def test_clean_index_marks_pass_no_audit(self):
        tenant, user = _seed()
        asset, instance = _seed_asset_and_workflow(
            tenant, user, status=AssetStatus.ACTIVE,
        )
        before = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()

        # Patch the indexer to return a synthetic success object so
        # the test doesn't need a real OpenSearch instance.
        from types import SimpleNamespace

        with patch(
            "hub.apps.orchestration.workflows.asset_creation.SearchIndexer.index_asset",
            return_value=SimpleNamespace(id=uuid.uuid4()),
        ):
            result = AssetCreationWorkflow._index_for_search_task(
                input_data={}, instance=instance, step=None,
            )

        assert result["indexed"] is True
        assert result.get("semantic_status") == "PASS"
        asset.refresh_from_db()
        assert asset.semantic_status == "PASS"

        after = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()
        assert after == before  # no audit on clean path


# ---------------------------------------------------------------------------
# Audit-pass-2 — FAIL-ratchet semantics across independent steps
# ---------------------------------------------------------------------------


class IndexForSearchPreservesPriorFailTest(TestCase):
    """The DSL runs ``activate_asset`` BEFORE ``index_for_search``.
    If activation's semantic-mapping wrapper set ``semantic_status``
    to FAIL (Fuseki down), a subsequent successful indexing step
    MUST NOT overwrite the FAIL with PASS — that would silently
    mask the Fuseki outage on the SPA's degraded banner the moment
    OpenSearch is healthy. The two systems are independent failure
    modes; FAIL is a ratchet released only by an explicit retry."""

    def test_index_success_preserves_prior_fail(self):
        tenant, user = _seed()
        asset, instance = _seed_asset_and_workflow(
            tenant, user, status=AssetStatus.ACTIVE,
        )
        # Pre-condition: a prior step already marked FAIL.
        asset.semantic_status = "FAIL"
        asset.save(update_fields=["semantic_status"])

        before_audit = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()

        from types import SimpleNamespace

        with patch(
            "hub.apps.orchestration.workflows.asset_creation.SearchIndexer.index_asset",
            return_value=SimpleNamespace(id=uuid.uuid4()),
        ):
            result = AssetCreationWorkflow._index_for_search_task(
                input_data={}, instance=instance, step=None,
            )

        # Indexing succeeded BUT the FAIL ratchet held: no overwrite.
        assert result["indexed"] is True
        assert result.get("semantic_status") == "FAIL"
        asset.refresh_from_db()
        assert asset.semantic_status == "FAIL"

        # And no spurious second audit row — the indexing step did
        # not detect a NEW degradation, it just declined to overwrite
        # an existing one.
        after_audit = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
            tenant=tenant,
        ).count()
        assert after_audit == before_audit
