"""
Phase 228.F1 (REQ-LIN-F1-001 / F1.20) — service-level unit tests for
``LineageService.get_for_asset``.

The view-layer test (`test_listing_lineage_view.py`) exercises the
full HTTP surface; this file pins the **service primitives** the
view depends on:

* Resolves an asset to its ACTIVE contract (404 when none).
* Walks ``LineageEdge`` rows up to ``max_depth``.
* Truncates at the per-query node + edge caps and surfaces
  ``truncated=true``.
* Anonymises cross-tenant endpoints (D1 mitigation in the F1
  STRIDE threat model).
* Renders node labels from contract names — never from
  ``transformation_ref`` (I4 mitigation).

No mocks of internal code paths.  Real DB rows for tenants, assets,
contracts, and lineage edges.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(slug_prefix: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_contract(
    tenant: Tenant, *, name: str, asset: Asset | None = None,
) -> "Contract":  # type: ignore[name-defined]  # test: edge-case type exercise
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={
            "info": {"name": name},
            "models": [
                {
                    "name": "default",
                    "fields": [
                        {"name": "id", "data_type": "string", "nullable": False},
                    ],
                }
            ],
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


def _make_asset(tenant: Tenant) -> Asset:
    suffix = uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{suffix}",
        name=f"asset-{suffix}",
        status=AssetStatus.ACTIVE,
    )


def _make_edge(
    tenant: Tenant,
    *,
    source_contract,
    target_contract,
    edge_type: str = "reference",
    transformation_ref: str = "",
    job_ref: str = "",
):
    """Create a current LineageEdge row (``valid_to IS NULL``)."""
    from hub.apps.contracts.models import LineageEdge

    return LineageEdge.objects.create(
        tenant=tenant,
        source_contract=source_contract,
        target_contract=target_contract,
        source_model="default",
        target_model="default",
        edge_type=edge_type,
        transformation_ref=transformation_ref,
        job_ref=job_ref,
    )


# ---------------------------------------------------------------------------
# Asset resolution
# ---------------------------------------------------------------------------


class GetForAssetResolutionTests(TestCase):

    def test_no_active_contract_raises_notfound(self):
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.core.services.base import NotFoundError

        tenant = _make_tenant("nf")
        asset = _make_asset(tenant)
        # No contract created.
        service = LineageService(tenant_id=str(tenant.id))
        with self.assertRaises(NotFoundError):
            service.get_for_asset(
                asset_id=str(asset.id),
                caller_tenant_id=str(tenant.id),
                owner_tenant_id=str(tenant.id),
            )

    def test_asset_with_active_contract_returns_root_node(self):
        """An asset with an ACTIVE contract but zero edges still
        produces a one-node graph rooted at the contract.  This
        is the marketplace's empty-but-valid lineage case."""
        from hub.apps.contracts.lineage_service import LineageService

        tenant = _make_tenant("root-only")
        asset = _make_asset(tenant)
        _make_contract(tenant, name="orders", asset=asset)

        service = LineageService(tenant_id=str(tenant.id))
        graph = service.get_for_asset(
            asset_id=str(asset.id),
            caller_tenant_id=str(tenant.id),
            owner_tenant_id=str(tenant.id),
        )
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["nodes"][0]["label"], "orders")
        self.assertEqual(graph["nodes"][0]["type"], "contract")
        self.assertEqual(len(graph["links"]), 0)
        self.assertFalse(graph["truncated"])


# ---------------------------------------------------------------------------
# Edge traversal + max_depth
# ---------------------------------------------------------------------------


class GetForAssetTraversalTests(TestCase):

    def test_walks_one_hop_at_max_depth_1(self):
        """A → B edge, max_depth=1, returns both nodes + the link."""
        from hub.apps.contracts.lineage_service import LineageService

        tenant = _make_tenant("walk")
        asset_a = _make_asset(tenant)
        contract_a = _make_contract(tenant, name="orders", asset=asset_a)
        asset_b = _make_asset(tenant)
        contract_b = _make_contract(tenant, name="customers", asset=asset_b)
        _make_edge(
            tenant, source_contract=contract_a, target_contract=contract_b,
            edge_type="reference",
        )

        service = LineageService(tenant_id=str(tenant.id))
        graph = service.get_for_asset(
            asset_id=str(asset_a.id),
            caller_tenant_id=str(tenant.id),
            owner_tenant_id=str(tenant.id),
            max_depth=1,
        )
        node_ids = {n["id"] for n in graph["nodes"]}
        self.assertIn(str(contract_a.id), node_ids)
        self.assertIn(str(contract_b.id), node_ids)
        self.assertEqual(len(graph["links"]), 1)


# ---------------------------------------------------------------------------
# Truncation guard (D2 mitigation in F1 STRIDE threat model)
# ---------------------------------------------------------------------------


class GetForAssetTruncationTests(TestCase):

    def test_dense_graph_truncation_returns_flag(self):
        """When the BFS would exceed F1_NODE_CAP, the response carries
        ``truncated=true`` and the result set is bounded."""
        from hub.apps.contracts.lineage_service import LineageService
        from hub.apps.contracts.models import LineageEdge

        tenant = _make_tenant("dense")
        asset = _make_asset(tenant)
        root = _make_contract(tenant, name="root", asset=asset)

        # Bound reduced for test speed — patch the cap to 5 so
        # creating 10 outgoing edges trips it without seeding 500
        # real contracts.
        original_cap = LineageService.F1_EDGE_CAP
        LineageService.F1_EDGE_CAP = 5
        try:
            for i in range(10):
                target = _make_contract(tenant, name=f"sink-{i}")
                _make_edge(
                    tenant, source_contract=root, target_contract=target,
                )
            service = LineageService(tenant_id=str(tenant.id))
            graph = service.get_for_asset(
                asset_id=str(asset.id),
                caller_tenant_id=str(tenant.id),
                owner_tenant_id=str(tenant.id),
                max_depth=3,
            )
        finally:
            LineageService.F1_EDGE_CAP = original_cap

        self.assertTrue(
            graph["truncated"],
            "BFS over 10 edges with F1_EDGE_CAP=5 must surface "
            "truncated=true so the frontend can show the "
            "'lineage truncated' affordance.",
        )
        self.assertLessEqual(len(graph["links"]), 5)


# ---------------------------------------------------------------------------
# Cross-tenant endpoint anonymisation (I-tier mitigation)
# ---------------------------------------------------------------------------


class GetForAssetCrossTenantAnonymisationTests(TestCase):

    def test_cross_tenant_endpoint_rendered_as_external(self):
        """An edge pointing at a contract owned by a DIFFERENT tenant
        SHALL render the foreign endpoint as a generic ``external``
        node.  No tenant_id, no contract name, no transformation IP.

        This is the I1/I4 mitigation in the F1 STRIDE threat model:
        when buyers from tenant B view tenant A's lineage, they
        can see that A's pipeline reads from tenant C's data — but
        the C-side endpoint MUST NOT carry C's tenant id or
        contract name (that would be a cross-tenant info leak with
        no entitlement).
        """
        from hub.apps.contracts.lineage_service import LineageService

        provider = _make_tenant("xt-provider")
        consumer_in_chain = _make_tenant("xt-other")  # different tenant
        # Provider's asset + ACTIVE contract.
        asset = _make_asset(provider)
        contract_a = _make_contract(provider, name="orders", asset=asset)
        # Foreign contract owned by a DIFFERENT tenant.
        contract_c = _make_contract(consumer_in_chain, name="secret-pipeline")
        # Edge crosses tenants.
        _make_edge(
            provider,
            source_contract=contract_a,
            target_contract=contract_c,
            edge_type="reference",
        )

        service = LineageService(tenant_id=str(provider.id))
        graph = service.get_for_asset(
            asset_id=str(asset.id),
            caller_tenant_id=str(provider.id),  # provider's own user
            owner_tenant_id=str(provider.id),
            max_depth=2,
        )
        foreign_nodes = [
            n for n in graph["nodes"]
            if n["id"] == str(contract_c.id)
        ]
        self.assertEqual(len(foreign_nodes), 1)
        node = foreign_nodes[0]
        self.assertEqual(node["type"], "external")
        # Anonymised label — NOT "secret-pipeline".
        self.assertNotIn("secret-pipeline", node.get("label", ""))


# ---------------------------------------------------------------------------
# Node label derivation (I4 mitigation)
# ---------------------------------------------------------------------------


class GetForAssetNodeLabelTests(TestCase):

    def test_label_derived_from_contract_name_not_transformation_ref(self):
        """Node labels SHALL be derived from
        ``hub_contract_json.info.name`` only — never from
        ``transformation_ref`` or ``job_ref``.  This is the I4
        mitigation in the F1 STRIDE threat model: a label like
        ``"dbt_redact_pii"`` would leak transformation hints into
        the summary tier."""
        from hub.apps.contracts.lineage_service import LineageService

        tenant = _make_tenant("label")
        asset = _make_asset(tenant)
        # Contract has a benign info.name ("orders") but a sensitive
        # transformation_ref on its incoming edge.
        contract = _make_contract(tenant, name="orders", asset=asset)
        upstream = _make_contract(tenant, name="raw-orders")
        _make_edge(
            tenant, source_contract=upstream, target_contract=contract,
            edge_type="transformation",
            transformation_ref="dbt_redact_pii_secret_logic_v3",
        )

        service = LineageService(tenant_id=str(tenant.id))
        graph = service.get_for_asset(
            asset_id=str(asset.id),
            caller_tenant_id=str(tenant.id),
            owner_tenant_id=str(tenant.id),
            max_depth=1,
        )
        for node in graph["nodes"]:
            self.assertNotIn(
                "dbt_redact_pii", node["label"],
                msg=(
                    "Node label MUST NOT carry transformation_ref hints — "
                    "I4 mitigation in F1 STRIDE threat model"
                ),
            )
