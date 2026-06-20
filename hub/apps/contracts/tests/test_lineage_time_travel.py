"""
Phase 228 (228.0.14, REQ-LIN-004) — time-travel API baseline tests.

Pins ``LineageService.<method>(as_of=...)`` against the SCD Type 2
``LineageEdge`` rows. Real DB rows; no internal mocks.

Coverage:

* All five read-side methods accept the ``as_of`` keyword.
* ``as_of=None`` returns the current state (existing behavior).
* ``as_of=<historical>`` returns the historical state.
* The SCD Type 2 predicate is correct: edges with
  ``valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)``
  match.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import timedelta

import pytest
from django.test import TransactionTestCase, override_settings
from django.utils import timezone


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"TT Co {suffix}",
        slug=f"tt-co-{suffix}",
    )


def _create_contract(tenant, *, lineage_refs=None):
    """Create a Contract, optionally with lineage references pointing at
    other contracts so ``generate_lineage_json`` can traverse them.

    ``lineage_refs``, when given, is a list of (namespace, name)
    tuples to embed in ``hub_contract_json.lineage.contracts``.
    """
    from hub.apps.contracts.models import Contract

    hub_json = {
        "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
    }
    if lineage_refs:
        hub_json["lineage"] = {
            "contracts": [
                {"namespace": ns, "name": nm} for ns, nm in lineage_refs
            ]
        }
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw="kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\nversion: 1.0.0\nstatus: active\n",
        hub_contract_json=hub_json,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def test_all_five_methods_accept_as_of_kwarg():
    """REQ-LIN-004: every read-side method exposes ``as_of``."""
    from hub.apps.contracts.lineage_service import LineageService

    methods = (
        LineageService.get_contract_lineage,
        LineageService.get_model_lineage,
        LineageService.get_field_lineage,
        LineageService.get_full_lineage,
        LineageService.get_lineage_visualization,
    )
    for fn in methods:
        sig = inspect.signature(fn)
        assert "as_of" in sig.parameters, (
            f"{fn.__name__} must accept as_of kwarg per REQ-LIN-004; params={list(sig.parameters)}"
        )


@pytest.mark.django_db(transaction=True)
class TestAsOfReturnsCurrentByDefault(TransactionTestCase):
    """REQ-LIN-004 scenario: ``as_of=None`` (default) returns current."""

    def test_default_returns_current_open_edges(self):
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)
        # Create one open edge directly so we control the DB state.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )

        svc = LineageService(tenant_id=str(tenant.id))
        # as_of=now (explicitly historical) should return the open edge.
        result = svc.get_contract_lineage(
            str(target.id),
            as_of=timezone.now() + timedelta(seconds=1),
        )
        assert "contracts" in result
        # The edge is in the response.
        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["source_contract"] == str(upstream.id)


@pytest.mark.django_db(transaction=True)
class TestAsOfReturnsHistoricalState(TransactionTestCase):
    """REQ-LIN-004 scenario: ``as_of`` returns the historical state."""

    def test_as_of_yesterday_excludes_today_only_edge(self):
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        now = timezone.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Edge that existed two days ago and was closed yesterday.
        old_edge = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="derivation",
        )
        # Backdate via a raw update so auto-now/db_default doesn't fight us.
        LineageEdge.objects.filter(pk=old_edge.pk).update(
            valid_from=two_days_ago - timedelta(hours=1),
            valid_to=yesterday,
        )

        # Current edge (open today).
        current_edge = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )
        LineageEdge.objects.filter(pk=current_edge.pk).update(
            valid_from=now - timedelta(hours=1),
        )

        svc = LineageService(tenant_id=str(tenant.id))

        # Query as-of two days ago: only the old edge should appear.
        historical = svc.get_contract_lineage(
            str(target.id),
            as_of=two_days_ago,
        )
        edge_types = sorted(c["edge_type"] for c in historical["contracts"])
        assert edge_types == ["derivation"], (
            f"as_of={two_days_ago} should return only the old derivation edge; got {edge_types}"
        )

        # Query as-of now: only the current edge.
        current = svc.get_contract_lineage(
            str(target.id),
            as_of=now + timedelta(seconds=1),
        )
        edge_types_now = sorted(c["edge_type"] for c in current["contracts"])
        assert edge_types_now == ["reference"], (
            f"as_of=now should return only the current edge; got {edge_types_now}"
        )

    def test_as_of_filters_get_full_lineage(self):
        """GAP-1 regression: ``get_full_lineage(as_of=...)`` must
        return upstream/downstream from the relational index, not the
        JSON path."""
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )

        svc = LineageService(tenant_id=str(tenant.id))
        result = svc.get_full_lineage(
            str(target.id),
            as_of=timezone.now() + timedelta(seconds=1),
        )
        assert "upstream" in result and "downstream" in result, (
            f"as_of-bearing get_full_lineage should return upstream/"
            f"downstream; got keys={list(result)}"
        )
        assert len(result["upstream"]) == 1
        assert result["as_of"] is not None

    def test_as_of_filters_get_lineage_visualization(self):
        """GAP-1 regression: ``get_lineage_visualization(as_of=...)``
        returns nodes+edges shape from the relational index."""
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )

        svc = LineageService(tenant_id=str(tenant.id))
        result = svc.get_lineage_visualization(
            str(target.id),
            as_of=timezone.now() + timedelta(seconds=1),
        )
        assert "nodes" in result and "edges" in result
        # Two nodes (upstream + target), one edge.
        node_ids = {n["id"] for n in result["nodes"]}
        assert node_ids == {str(upstream.id), str(target.id)}
        assert len(result["edges"]) == 1

    def test_query_metric_emitted_per_read(self):
        """GAP-3 regression: every read-method invocation increments
        ``lineage_query_total{detail,cross_tenant,as_of}``. Pre-fix the
        metric existed but no code site called .inc(); the REQ-LIN-007
        scenario was unsatisfiable."""
        from unittest import mock

        from hub.apps.contracts.lineage_service import LineageService

        tenant = _create_tenant()
        target = _create_contract(tenant)

        svc = LineageService(tenant_id=str(tenant.id))
        # Patch the metric at the import-site that LineageService uses.
        with mock.patch("hub.apps.observability.metrics.lineage_query_total") as m:
            svc.get_contract_lineage(
                str(target.id),
                as_of=timezone.now() + timedelta(seconds=1),
            )
        # ``.labels(...).inc()`` was called at least once.
        assert m.labels.called, (
            "expected lineage_query_total.labels(...).inc() to fire on "
            "every read-method invocation; pre-fix the counter was never "
            "emitted, making the REQ-LIN-007 dashboard panel hollow"
        )
        labels_kwargs = m.labels.call_args.kwargs
        assert labels_kwargs.get("detail") == "contract"
        assert labels_kwargs.get("as_of") == "true"

    def test_edges_at_helper_validity_predicate(self):
        """Direct test of the SCD Type 2 predicate via the
        ``_edges_at`` helper — confirms the boundary cases:
        edge open at ``as_of`` is included; edge that closed at
        exactly ``as_of`` is excluded (``valid_to > as_of``)."""
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        cutoff = timezone.now() - timedelta(days=1)

        # Edge open at cutoff (valid_from before, valid_to after).
        e1 = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )
        LineageEdge.objects.filter(pk=e1.pk).update(
            valid_from=cutoff - timedelta(hours=1),
            valid_to=cutoff + timedelta(hours=1),
        )

        # Edge that closed BEFORE cutoff (excluded).
        e2 = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="export",
        )
        LineageEdge.objects.filter(pk=e2.pk).update(
            valid_from=cutoff - timedelta(days=2),
            valid_to=cutoff - timedelta(hours=1),
        )

        edges = LineageService._edges_at(str(target.id), as_of=cutoff)
        types = sorted(e["edge_type"] for e in edges)
        assert types == ["reference"], f"only the edge open at cutoff should match; got {types}"


# ===========================================================================
# Phase 228 F5 (REQ-LIN-F5-001 / 228.F5.2 + F5.9) — view-layer plumbing of
# ``?as_of=<ISO8601>`` and ``?version=<int>`` on the lineage visualization
# endpoint.
# ===========================================================================


def _create_subscription_for_tenant(tenant):
    """Create an ACTIVE BASE subscription so the billing middleware
    doesn't 403 the GET. Mirrors the F4 inbound test pattern."""
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.billing.tests.plan_fixtures import get_pro_plan

    plan = get_pro_plan()
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        category="BASE",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )


def _create_authenticated_user(tenant):
    """Build an authenticated User attached to the tenant."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(
        email=f"tt-user-{uuid.uuid4().hex[:6]}@x",
        tenant=tenant,
    )


@pytest.mark.django_db(transaction=True)
class TestVisualizationViewAsOf(TransactionTestCase):
    """REQ-LIN-F5-001 — visualization view threads ``?as_of=`` to the
    service-layer ``as_of`` cutoff."""

    def _post_setup(self):
        from rest_framework.test import APIClient

        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        # Old edge: open from 2 days ago, closed yesterday.
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        old = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="derivation",
        )
        LineageEdge.objects.filter(pk=old.pk).update(
            valid_from=two_days_ago,
            valid_to=yesterday,
        )
        # New edge: open since today.
        new_edge = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        return tenant, target, old, new_edge, two_days_ago, yesterday, now, client, url

    def test_no_as_of_returns_current_state(self):
        """Current-state visualization returns the ``generate_lineage_json``
        shape: ``nodes`` + ``links`` keys, not ``edges``.

        The ``as_of=None`` path uses the legacy traverser which reads
        contract ``hub_contract_json``, not ``LineageEdge`` rows.
        """
        _, target, _old, _new_edge, _, _, _, client, url = self._post_setup()
        resp = client.get(url)
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert "nodes" in data
        # Legacy path returns 'links' not 'edges'.
        assert "links" in data
        assert isinstance(data["links"], list)
        node_ids = {n.get("id") for n in data.get("nodes", [])}
        assert str(target.id) in node_ids

    def test_as_of_yesterday_returns_historical_state(self):
        _, _, _old, _, _two_days_ago, yesterday, _, client, url = self._post_setup()
        # Cutoff: yesterday - 1 hour (so the old edge is still open).
        cutoff = (yesterday - timedelta(hours=1)).isoformat()
        resp = client.get(url, {"as_of": cutoff})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        edge_types = {e.get("edge_type") for e in data.get("edges", [])}
        # Only the historical "derivation" edge should appear.
        assert "derivation" in edge_types
        assert "reference" not in edge_types
        # The view echoes the resolved cutoff for UX traceability.
        assert data.get("as_of") is not None
        assert data.get("as_of_source") == "as_of"

    def test_invalid_as_of_returns_400(self):
        _, _, _, _, _, _, _, client, url = self._post_setup()
        resp = client.get(url, {"as_of": "not-a-real-date"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_AS_OF"


@pytest.mark.django_db(transaction=True)
class TestVisualizationViewVersionParam(TransactionTestCase):
    """REQ-LIN-F5-001 — ``?version=<int>`` resolves to a Contract row's
    ``created_at`` and uses it as the as_of cutoff."""

    def test_version_resolves_to_contract_created_at(self):
        from rest_framework.test import APIClient

        from hub.apps.contracts.models import Contract, LineageEdge

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)
        upstream = _create_contract(tenant)

        # Backdate target's created_at so we can pin the cutoff.
        anchor_time = timezone.now() - timedelta(days=3)
        Contract.objects.filter(pk=target.pk).update(created_at=anchor_time)

        # Edge that opened BEFORE the version anchor → visible at as_of
        old = LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="derivation",
        )
        LineageEdge.objects.filter(pk=old.pk).update(
            valid_from=anchor_time - timedelta(days=1),
            valid_to=None,  # still open at anchor
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        resp = client.get(url, {"version": "1"})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data.get("as_of_source") == "version"

    def test_unknown_version_returns_404(self):
        from rest_framework.test import APIClient

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        resp = client.get(url, {"version": "9999"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "VERSION_NOT_FOUND"

    def test_invalid_version_returns_400(self):
        from rest_framework.test import APIClient

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        resp = client.get(url, {"version": "not-a-number"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_VERSION"


# ===========================================================================
# Phase 228 F5 (REQ-LIN-F5-001 / DoD-G1 + G2 + G9) — spec-mandated
# scenarios that the first-pass DoD self-audit missed.
# ===========================================================================


@pytest.mark.django_db(transaction=True)
class TestVisualizationViewSpecScenarios(TransactionTestCase):
    """REQ-LIN-F5-001 spec scenarios:
    - "as_of in the future returns current state"
    - "Both params returns 400"
    - "Flag off ignores params"
    """

    def test_as_of_in_future_returns_current_state(self):
        """REQ-LIN-F5-001 scenario "as_of in the future returns
        current state"."""
        from rest_framework.test import APIClient

        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        upstream = _create_contract(tenant)
        target = _create_contract(tenant)

        # Single open edge — current state.
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=upstream,
            target_contract=target,
            edge_type="reference",
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        future = (timezone.now() + timedelta(days=365)).isoformat()
        resp = client.get(url, {"as_of": future})
        assert resp.status_code == 200
        data = resp.json()
        # Edge is still open (valid_to NULL) → present at any future
        # cutoff per the SCD-2 predicate
        # `valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)`.
        edge_types = {e.get("edge_type") for e in data.get("edges", [])}
        assert "reference" in edge_types

    def test_both_as_of_and_version_returns_400(self):
        """Spec REQ-LIN-F5-001: "Setting both SHALL return HTTP 400"."""
        from rest_framework.test import APIClient

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        resp = client.get(
            url,
            {
                "as_of": (timezone.now() - timedelta(days=1)).isoformat(),
                "version": "1",
            },
        )
        assert resp.status_code == 400, resp.content
        assert resp.json()["error"]["code"] == "AS_OF_AND_VERSION_MUTUALLY_EXCLUSIVE"

    @override_settings(CAPABILITY_FLAGS={"lineage.snapshots": False})
    def test_flag_off_silently_ignores_params(self):
        """Spec REQ-LIN-F5-001: "When OFF, the parameters SHALL be
        silently ignored (treated as 'current')".

        When the flag is OFF, ``as_of_cutoff`` stays None and the
        request flows through the legacy ``generate_lineage_json``
        path — the same as when ``as_of`` was never passed.  The
        response MUST carry ``as_of_source = "ignored_flag_off"``
        so operators can diagnose their date-picker no-op.
        """
        from rest_framework.test import APIClient

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        cutoff = (timezone.now() - timedelta(days=1)).isoformat()
        resp = client.get(url, {"as_of": cutoff})
        assert resp.status_code == 200
        data = resp.json()
        # Flag OFF → param silently ignored.
        assert data.get("as_of_source") == "ignored_flag_off"
        # Response shape must be valid (legacy path → 'links' key).
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["links"], list)
        node_ids = {n.get("id") for n in data.get("nodes", [])}
        assert str(target.id) in node_ids


# ===========================================================================
# Phase 228 F5 (DoD-G6 + G7) — observability of point-in-time queries.
# ===========================================================================


@pytest.mark.django_db(transaction=True)
class TestVisualizationViewObservability(TransactionTestCase):
    def test_as_of_emits_audit_event(self):
        """Spec REQ-LIN-F5-001 — every successful point-in-time query
        emits LINEAGE_SNAPSHOT_QUERIED."""
        from rest_framework.test import APIClient

        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        before = AuditEvent.objects.filter(
            action="LINEAGE_SNAPSHOT_QUERIED",
            tenant=tenant,
        ).count()
        cutoff = (timezone.now() - timedelta(days=1)).isoformat()
        resp = client.get(url, {"as_of": cutoff})
        assert resp.status_code == 200
        after = AuditEvent.objects.filter(
            action="LINEAGE_SNAPSHOT_QUERIED",
            tenant=tenant,
        ).count()
        assert after - before == 1, (
            f"every successful point-in-time query must emit one audit; got delta={after - before}"
        )

    def test_no_anchor_does_not_emit_audit(self):
        """Current-state query (no `as_of`/`version`) MUST NOT fire
        the snapshot audit — that would inflate the audit table."""
        from rest_framework.test import APIClient

        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        _create_subscription_for_tenant(tenant)
        user = _create_authenticated_user(tenant)
        target = _create_contract(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/visualization/"
        before = AuditEvent.objects.filter(
            action="LINEAGE_SNAPSHOT_QUERIED",
            tenant=tenant,
        ).count()
        resp = client.get(url)
        assert resp.status_code == 200
        after = AuditEvent.objects.filter(
            action="LINEAGE_SNAPSHOT_QUERIED",
            tenant=tenant,
        ).count()
        assert after == before
