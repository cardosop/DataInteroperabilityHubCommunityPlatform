"""
Phase 228 F5 (228.F5.4 + 228.F5.10) — `compute_diff` pure function.

Pins the contract for the time-travel diff:

* Pure: no DB / no signals — takes two edge-set snapshots, returns
  ``{added, removed, changed, unchanged}``.
* Deterministic ordering — added/removed sorted by ``(source_contract,
  target_contract, source_field, target_field)`` so the API response
  is stable across calls.
* Identity tuple matches the SCD-2 open-row unique constraint
  ``(source_contract, target_contract, source_model, source_field,
  target_model, target_field, edge_type)`` so two edges with the same
  scope but different ``transformation_ref`` are CHANGED, not
  remove-then-add.
* No allocation of dicts the caller already owns — accepts iterables
  of plain dicts (the shape ``LineageService._edges_at`` returns).

The diff is the load-bearing operation behind F5.3
``GET /lineage/diff/?from=&to=``; this file pins it before the
endpoint wiring.
"""
from __future__ import annotations

import pytest


# Spec for the diff function — pinned before implementation exists.
def _make_edge(
    *,
    src="A",
    tgt="B",
    src_model="m",
    src_field="f",
    tgt_model="mm",
    tgt_field="ff",
    edge_type="reference",
    transformation_ref="",
    job_ref="",
    valid_from="2026-01-01T00:00:00Z",
    valid_to=None,
    edge_id=None,
):
    return {
        "id": edge_id or f"{src}-{tgt}-{src_field}-{tgt_field}",
        "source_contract": src,
        "target_contract": tgt,
        "source_model": src_model,
        "source_field": src_field,
        "target_model": tgt_model,
        "target_field": tgt_field,
        "edge_type": edge_type,
        "transformation_ref": transformation_ref,
        "job_ref": job_ref,
        "valid_from": valid_from,
        "valid_to": valid_to,
    }


class TestComputeDiffPureFunction:
    """Spec for ``compute_diff`` — no DB, no signals.

    Spec-compliant identity (REQ-LIN-F5-002): an SCD-2 modification
    closes the old row + opens a new one, so a change to any
    diffable attribute (transformation_ref, job_ref) produces a
    distinct identity tuple. ``modified`` is therefore always
    empty in the response.
    """

    def test_added_only_when_left_empty(self):
        from hub.apps.contracts.lineage_diff import compute_diff

        added = [_make_edge(src="A", tgt="B")]
        result = compute_diff(left=[], right=added)
        assert [e["target_contract"] for e in result["added"]] == ["B"]
        assert result["removed"] == []
        assert result["modified"] == []
        assert result["unchanged"] == []

    def test_removed_only_when_right_empty(self):
        from hub.apps.contracts.lineage_diff import compute_diff

        removed = [_make_edge(src="A", tgt="B")]
        result = compute_diff(left=removed, right=[])
        assert result["added"] == []
        assert [e["target_contract"] for e in result["removed"]] == ["B"]
        assert result["modified"] == []
        assert result["unchanged"] == []

    def test_unchanged_when_identical(self):
        from hub.apps.contracts.lineage_diff import compute_diff

        e = _make_edge(src="A", tgt="B")
        result = compute_diff(left=[e], right=[dict(e)])
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []
        assert len(result["unchanged"]) == 1
        assert result["unchanged"][0]["target_contract"] == "B"

    def test_transformation_change_is_remove_and_add_under_scd2(self):
        """Spec: ``modified is always empty``. A change to
        transformation_ref under SCD-2 closes the old row + opens
        a new one — diff sees one removed + one added."""
        from hub.apps.contracts.lineage_diff import compute_diff

        old = _make_edge(src="A", tgt="B", transformation_ref="v1")
        new = _make_edge(src="A", tgt="B", transformation_ref="v2")
        result = compute_diff(left=[old], right=[new])
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 1
        assert result["modified"] == [], (
            "Spec REQ-LIN-F5-002: modified is always empty."
        )
        assert result["added"][0]["transformation_ref"] == "v2"
        assert result["removed"][0]["transformation_ref"] == "v1"

    def test_added_and_removed_distinct_when_scope_differs(self):
        from hub.apps.contracts.lineage_diff import compute_diff

        old = _make_edge(src="A", tgt="B", src_field="x")
        new = _make_edge(src="A", tgt="B", src_field="y")
        result = compute_diff(left=[old], right=[new])
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 1
        assert result["modified"] == []

    def test_deterministic_order_for_added(self):
        from hub.apps.contracts.lineage_diff import compute_diff

        right = [
            _make_edge(src="A", tgt="Z"),
            _make_edge(src="A", tgt="B"),
            _make_edge(src="A", tgt="M"),
        ]
        result = compute_diff(left=[], right=right)
        targets = [e["target_contract"] for e in result["added"]]
        assert targets == ["B", "M", "Z"], (
            f"added must be sorted by (src,tgt,...); got {targets}"
        )

    def test_iterable_inputs_consumed_once(self):
        """The function must accept generators (one-shot iterables) —
        users may stream rows from QuerySet.iterator()."""
        from hub.apps.contracts.lineage_diff import compute_diff

        def _gen():
            yield _make_edge(src="A", tgt="B")
            yield _make_edge(src="A", tgt="C")

        result = compute_diff(left=_gen(), right=_gen())
        assert len(result["unchanged"]) == 2
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []

    def test_handles_missing_optional_fields(self):
        """Old rows might lack ``transformation_ref`` / ``job_ref``;
        treat NULL == empty-string for diff equality."""
        from hub.apps.contracts.lineage_diff import compute_diff

        old = _make_edge()
        del old["transformation_ref"]
        new = _make_edge(transformation_ref="")
        result = compute_diff(left=[old], right=[new])
        assert result["unchanged"]
        assert result["modified"] == []

    def test_result_summary_counts(self):
        """Top-level ``summary`` carries the cardinalities so callers
        can render '5 added / 3 removed' without re-counting."""
        from hub.apps.contracts.lineage_diff import compute_diff

        left = [_make_edge(src="A", tgt="B")]
        right = [
            _make_edge(src="A", tgt="C"),
            _make_edge(src="A", tgt="B", transformation_ref="v2"),
        ]
        result = compute_diff(left=left, right=right)
        s = result["summary"]
        # transformation_ref change → remove+add (close-and-reopen).
        # Plus the genuinely new C edge → 1 unchanged on B-with-v1
        # is not present (left has B-no-tref, right has B-v2-tref);
        # so left's B-no-tref → removed, right has B-v2-tref +
        # C → both added.
        assert s == {
            "added": 2,
            "removed": 1,
            "modified": 0,
            "unchanged": 0,
        }, s

    def test_response_always_carries_modified_empty_list(self):
        """REQ-LIN-F5-002 stable contract: ``modified`` key is always
        present + always an empty list."""
        from hub.apps.contracts.lineage_diff import compute_diff

        # Every input combination must surface ``modified: []``.
        for left, right in (
            ([], []),
            ([_make_edge()], []),
            ([], [_make_edge()]),
            ([_make_edge(transformation_ref="a")],
             [_make_edge(transformation_ref="b")]),
        ):
            result = compute_diff(left=left, right=right)
            assert "modified" in result
            assert result["modified"] == [], (
                f"left={left} right={right} produced {result['modified']!r}"
            )


# ===========================================================================
# Phase 228 F5 (228.F5.3) — diff endpoint integration tests.
# Real DB rows + real APIClient. End-to-end pin of the
# ``GET /api/v1/contracts/{id}/lineage/diff/?from=&to=`` surface.
# ===========================================================================


import uuid as _uuid
from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone


def _create_tenant_with_subscription():
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.billing.tests.plan_fixtures import (
        create_unique_tenant, get_pro_plan,
    )

    plan = get_pro_plan()
    t = create_unique_tenant(
        name_prefix="LD Co",
        slug_prefix="ld-co",
        plan=plan,
    )
    Subscription.objects.create(
        tenant=t,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        category="BASE",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return t


def _create_contract_real(tenant, *, version=1):
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant,
        version=version,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\n"
            "version: 1.0.0\nstatus: active\n"
        ),
        hub_contract_json={
            "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
            "schema": {"fields": []},
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _create_user_for_tenant(tenant):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create(
        email=f"diff-user-{_uuid.uuid4().hex[:6]}@x", tenant=tenant,
    )


@pytest.mark.django_db(transaction=True)
class TestLineageDiffEndpoint(TransactionTestCase):
    """Pin the diff API surface — request shape, response shape, errors."""

    def test_diff_returns_added_when_edge_opens_after_from(self):
        from hub.apps.contracts.models import LineageEdge
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        target = _create_contract_real(tenant)
        upstream = _create_contract_real(tenant)

        # Edge that opens AFTER the ``from`` cutoff.
        from_cutoff = timezone.now() - timedelta(hours=2)
        opened_at = timezone.now() - timedelta(hours=1)
        e = LineageEdge.objects.create(
            tenant=tenant, source_contract=upstream,
            target_contract=target, edge_type="reference",
        )
        LineageEdge.objects.filter(pk=e.pk).update(valid_from=opened_at)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/diff/"
        resp = client.get(url, {"from": from_cutoff.isoformat()})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        # Endpoint surfaces both anchor metadata + the diff.
        assert data["from"]["source"] == "timestamp"
        assert data["to"]["source"] == "now"
        assert data["summary"]["added"] >= 1, data["summary"]

    def test_diff_returns_removed_when_edge_closes_in_window(self):
        from hub.apps.contracts.models import LineageEdge
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        target = _create_contract_real(tenant)
        upstream = _create_contract_real(tenant)

        from_cutoff = timezone.now() - timedelta(hours=2)
        closed_at = timezone.now() - timedelta(minutes=30)
        e = LineageEdge.objects.create(
            tenant=tenant, source_contract=upstream,
            target_contract=target, edge_type="derivation",
        )
        LineageEdge.objects.filter(pk=e.pk).update(
            valid_from=from_cutoff - timedelta(hours=1),
            valid_to=closed_at,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/diff/"
        resp = client.get(url, {"from": from_cutoff.isoformat()})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["summary"]["removed"] >= 1, data["summary"]

    def test_diff_missing_from_returns_400(self):
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        target = _create_contract_real(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/diff/"
        resp = client.get(url)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MISSING_FROM_ANCHOR"

    def test_diff_invalid_from_iso_returns_400(self):
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        target = _create_contract_real(tenant)

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/diff/"
        resp = client.get(url, {"from": "not-iso"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ANCHOR"

    def test_diff_no_change_returns_empty_buckets(self):
        """Spec REQ-LIN-F5-002 scenario "No change returns empty diff":
        when ``from`` and ``to`` are identical, all buckets
        (added/removed/modified) are empty + summary counts are zero
        for those buckets. Existing edges show up as ``unchanged``."""
        from hub.apps.contracts.models import LineageEdge
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        target = _create_contract_real(tenant)
        upstream = _create_contract_real(tenant)
        # Stable open edge that exists at any cutoff in [now-1h, now].
        LineageEdge.objects.create(
            tenant=tenant, source_contract=upstream,
            target_contract=target, edge_type="reference",
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{target.id}/lineage/diff/"
        cutoff = timezone.now().isoformat()
        resp = client.get(url, {"from": cutoff, "to": cutoff})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["added"] == []
        assert data["removed"] == []
        assert data["modified"] == [], (
            "spec REQ-LIN-F5-002: ``modified`` is always empty list"
        )
        assert data["summary"]["added"] == 0
        assert data["summary"]["removed"] == 0
        assert data["summary"]["modified"] == 0

    def test_diff_with_version_anchors_resolves_created_at(self):
        from hub.apps.contracts.models import Contract
        from rest_framework.test import APIClient

        tenant = _create_tenant_with_subscription()
        user = _create_user_for_tenant(tenant)
        # Two contract versions in the tenant (different stems via
        # different rows; the diff endpoint keys on tenant + version).
        v1 = _create_contract_real(tenant, version=1)
        v2 = _create_contract_real(tenant, version=2)
        Contract.objects.filter(pk=v1.pk).update(
            created_at=timezone.now() - timedelta(days=4),
        )
        Contract.objects.filter(pk=v2.pk).update(
            created_at=timezone.now() - timedelta(days=2),
        )

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{v2.id}/lineage/diff/"
        resp = client.get(url, {"from_version": "1", "to_version": "2"})
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["from"]["source"] == "version"
        assert data["to"]["source"] == "version"
        # 'from' anchor must resolve to v1.created_at; 'to' to v2.created_at.
        # Both ts strings carry timezone info — relative ordering check.
        assert data["from"]["timestamp"] < data["to"]["timestamp"]
