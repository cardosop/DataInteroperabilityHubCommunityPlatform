"""
Phase 230.11.8 — Semantic search promotion (REQ-SEM-SEARCH-EXPAND-001).

Tests follow TDD-first.  The capability adds a ``?semantic=true`` flag
on the search endpoint that, when paired with
``Tenant.semantic_search_enabled=True``, expands the user's query via
ontology relations (``skos:altLabel``, ``skos:related``,
``owl:equivalentClass``, ``rdfs:subClassOf`` ancestors at depth ≤ 2).

The two spec scenarios are covered directly:

* "Synonym expansion surfaces equivalent-class match" — `Customer
  owl:equivalentClass Client`, asset tagged "client" surfaces with
  ``matched_via=ontology`` and ``bridge_term=Client``, ranked below
  exact "customer" matches (0.5× multiplier on expanded matches).
* "Toggle off reproduces today's behaviour" — same query, same
  ontology, but no ``?semantic=true`` → asset does NOT appear.

Plus engineering-grade extensions: tenant flag default-False (no
expansion when flag is off, even with ?semantic=true); inactive
ontologies do NOT contribute bridges; expansion at depth > 2 is NOT
followed; the helper module's pure-function path is exercised
without the HTTP layer for unit-test latency parity with the rest
of the search test suite.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.postgres.search import SearchVector
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(slug_prefix: str = "sem"):
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _make_user(tenant, email_prefix="u"):
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{email_prefix}-{suffix}@test.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _make_asset(tenant, user, *, name, description=""):
    a = Asset.objects.create(
        tenant=tenant,
        key=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
        name=name,
        description=description,
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    # Populate the FTS index so the live UnifiedSearchView path works
    # (the production signal-driven update is async via RQ; tests must
    # set it deterministically).
    Asset.objects.filter(pk=a.pk).update(
        search_vector=(
            SearchVector("name", weight="A")
            + SearchVector("description", weight="B")
        ),
    )
    return a


def _make_active_ontology(tenant, *, turtle_body):
    from hub.apps.semantic.models import (
        OntologyFormat,
        OntologyValidationStatus,
        TenantOntology,
    )
    suffix = uuid.uuid4().hex[:6]
    return TenantOntology.objects.create(
        tenant=tenant,
        name=f"ont-{suffix}",
        namespace_iri=f"https://t.example.com/ont-{suffix}/",
        format=OntologyFormat.TURTLE,
        rdf_content=turtle_body,
        validation_status=OntologyValidationStatus.VALID,
        is_active=True,
        triple_count=0,
    )


def _client(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


_EQUIV_TURTLE = """
@prefix : <https://t.example.com/sem#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

:Customer owl:equivalentClass :Client .
""".strip()


_SUBCLASS_TURTLE = """
@prefix : <https://t.example.com/sem#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:GoldCustomer rdfs:subClassOf :Customer .
:Customer rdfs:subClassOf :Person .
:Person rdfs:subClassOf :Agent .
:Agent rdfs:subClassOf :Anything .
""".strip()


_SKOS_TURTLE = """
@prefix : <https://t.example.com/sem#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

:Customer skos:altLabel "Patron" .
:Customer skos:related :LoyalShopper .
""".strip()


# ---------------------------------------------------------------------------
# Unit-level tests for the expansion helper
# ---------------------------------------------------------------------------


class SemanticQueryExpansionUnitTests(TransactionTestCase):
    """Tests against the pure expansion function, no HTTP."""

    def test_owl_equivalent_class_produces_bridge(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant = _make_tenant("eq")
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)
        bridges = expand_query_terms(query="customer", tenant_id=str(tenant.id))
        labels = {b.label.lower() for b in bridges}
        self.assertIn("client", labels, msg=f"expected 'client' bridge, got {bridges}")

    def test_skos_alt_label_produces_bridge(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant = _make_tenant("alt")
        _make_active_ontology(tenant, turtle_body=_SKOS_TURTLE)
        bridges = expand_query_terms(query="customer", tenant_id=str(tenant.id))
        labels = {b.label.lower() for b in bridges}
        # altLabel literal produces "patron"; skos:related produces
        # "loyalshopper" (local name fallback when no rdfs:label is
        # asserted).
        self.assertIn("patron", labels, msg=f"got {bridges}")
        self.assertIn("loyalshopper", labels, msg=f"got {bridges}")

    def test_subclass_at_depth_two_included(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant = _make_tenant("sub")
        _make_active_ontology(tenant, turtle_body=_SUBCLASS_TURTLE)
        bridges = expand_query_terms(
            query="goldcustomer", tenant_id=str(tenant.id),
        )
        labels = {b.label.lower() for b in bridges}
        # Depth 1 ancestor.
        self.assertIn("customer", labels, msg=f"got {bridges}")
        # Depth 2 ancestor — included per spec (depth ≤ 2).
        self.assertIn("person", labels, msg=f"got {bridges}")

    def test_subclass_at_depth_three_excluded(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant = _make_tenant("sub3")
        _make_active_ontology(tenant, turtle_body=_SUBCLASS_TURTLE)
        bridges = expand_query_terms(
            query="goldcustomer", tenant_id=str(tenant.id),
        )
        labels = {b.label.lower() for b in bridges}
        # Depth 3+ MUST NOT be in the bridge set.
        self.assertNotIn("agent", labels, msg=f"got {bridges}")
        self.assertNotIn("anything", labels, msg=f"got {bridges}")

    def test_inactive_ontology_does_not_contribute(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms
        from hub.apps.semantic.models import TenantOntology

        tenant = _make_tenant("inact")
        ont = _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)
        TenantOntology.objects.filter(pk=ont.pk).update(is_active=False)

        bridges = expand_query_terms(query="customer", tenant_id=str(tenant.id))
        self.assertEqual(
            bridges, [],
            msg="inactive ontology MUST NOT produce expansion bridges",
        )

    def test_cross_tenant_ontology_does_not_contribute(self):
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant_a = _make_tenant("xt-a")
        tenant_b = _make_tenant("xt-b")
        _make_active_ontology(tenant_a, turtle_body=_EQUIV_TURTLE)
        # Tenant B has no ontology — must see no bridges.
        bridges = expand_query_terms(
            query="customer", tenant_id=str(tenant_b.id),
        )
        self.assertEqual(bridges, [])


# ---------------------------------------------------------------------------
# HTTP-level tests — UnifiedSearchView ?semantic=true
# ---------------------------------------------------------------------------


class SemanticSearchViewTests(TransactionTestCase):
    """Spec scenarios at the /api/search/ endpoint."""

    def test_synonym_expansion_surfaces_equivalent_class_match(self):
        """REQ-SEM-SEARCH-EXPAND-001 scenario 1.

        Asset whose searchable text is "client" surfaces when the
        query "customer" runs with ?semantic=true and the tenant has
        ``Customer owl:equivalentClass Client`` active.  The result
        carries ``matched_via=ontology`` and ``bridge_term=Client``,
        ranked below an exact "customer" match.
        """
        tenant = _make_tenant("scn1")
        tenant.semantic_search_enabled = True
        tenant.save(update_fields=["semantic_search_enabled"])
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)

        # Exact-match asset (the user's literal query "customer").
        exact = _make_asset(tenant, user, name="Customer Loyalty Report")
        # Bridge-match asset — only mentions "client".
        bridge = _make_asset(tenant, user, name="Client Profile Dashboard")

        resp = _client(user).get(
            "/api/search/?q=customer&semantic=true",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        results = resp.data.get("results", resp.data)
        ids = [r["id"] for r in results]
        self.assertIn(str(exact.pk), ids, msg=f"results: {results}")
        self.assertIn(str(bridge.pk), ids, msg=f"results: {results}")

        bridge_row = next(r for r in results if r["id"] == str(bridge.pk))
        exact_row = next(r for r in results if r["id"] == str(exact.pk))

        self.assertEqual(bridge_row.get("matched_via"), "ontology")
        # Bridge term is the label that connected "customer" → "client".
        self.assertIn(
            (bridge_row.get("bridge_term") or "").lower(), {"client"},
            msg=f"row: {bridge_row}",
        )
        # 0.5× multiplier — bridge-match rank MUST be ≤ exact-match rank.
        self.assertLessEqual(
            float(bridge_row["rank"]), float(exact_row["rank"]),
            msg="bridge match should rank ≤ exact match (0.5× multiplier)",
        )

    def test_toggle_off_reproduces_today_behaviour(self):
        """REQ-SEM-SEARCH-EXPAND-001 scenario 2.

        Same tenant, same ontology, query without ?semantic=true →
        bridge-match asset MUST NOT appear.
        """
        tenant = _make_tenant("scn2")
        tenant.semantic_search_enabled = True
        tenant.save(update_fields=["semantic_search_enabled"])
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)
        bridge = _make_asset(tenant, user, name="Client Profile Dashboard")

        resp = _client(user).get("/api/search/?q=customer")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        ids = [r["id"] for r in results]
        self.assertNotIn(
            str(bridge.pk), ids,
            msg="bridge match MUST NOT appear without ?semantic=true",
        )

    def test_tenant_flag_off_makes_semantic_param_no_op(self):
        """``?semantic=true`` is a no-op when tenant flag is False
        (default).  Defence-in-depth: a tenant cannot opt itself
        into expansion via the URL alone."""
        tenant = _make_tenant("flagoff")
        # tenant.semantic_search_enabled stays False (default).
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)
        bridge = _make_asset(tenant, user, name="Client Profile Dashboard")

        resp = _client(user).get(
            "/api/search/?q=customer&semantic=true",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        ids = [r["id"] for r in results]
        self.assertNotIn(str(bridge.pk), ids)

    def test_exact_match_does_not_carry_bridge_metadata(self):
        """Exact matches MUST NOT carry the matched_via=ontology flag —
        that field is reserved for expansion-only matches so the
        client can render the badge unambiguously."""
        tenant = _make_tenant("exactonly")
        tenant.semantic_search_enabled = True
        tenant.save(update_fields=["semantic_search_enabled"])
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)
        exact = _make_asset(tenant, user, name="Customer Loyalty Report")

        resp = _client(user).get(
            "/api/search/?q=customer&semantic=true",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        exact_row = next(r for r in results if r["id"] == str(exact.pk))
        self.assertNotIn("matched_via", exact_row)
        self.assertNotIn("bridge_term", exact_row)


# ---------------------------------------------------------------------------
# Audit fix — SearchViewSet (the production frontend path) must also
# honour ?semantic=true (Phase 230.11 closeout)
# ---------------------------------------------------------------------------


def _make_search_index(tenant, *, title, description=""):
    """Populate a SearchIndex row with the FTS vector set so the
    deprecated SearchViewSet → SearchService → SearchEngine path
    finds it via PostgreSQL ``@@`` matching."""
    from django.contrib.postgres.search import SearchVector
    from hub.apps.search.models import SearchIndex
    idx = SearchIndex.objects.create(
        tenant=tenant,
        resource_id=uuid.uuid4(),
        resource_type="ASSET",
        title=title,
        description=description,
        quality_status="PASS",
        compliance_status="PASS",
    )
    SearchIndex.objects.filter(pk=idx.pk).update(
        search_vector=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("description", weight="B", config="english")
        ),
    )
    idx.refresh_from_db()
    return idx


class SemanticSearchLegacyViewTests(TransactionTestCase):
    """Pin the production frontend path: ``GET /api/v1/search/search/``
    (the deprecated SearchViewSet) MUST honour ``?semantic=true`` per
    Phase 230.11 closeout — the apiClient sends every request to
    ``/api/v1/...``, so wiring expansion only into the unified path
    (mounted at ``/api/search/`` outside ``/api/v1/``) would leave the
    UI toggle dead in production."""

    def test_semantic_param_surfaces_bridge_match_via_legacy_path(self):
        tenant = _make_tenant("legacy-bridge")
        tenant.semantic_search_enabled = True
        tenant.save(update_fields=["semantic_search_enabled"])
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)

        bridge_idx = _make_search_index(
            tenant, title="Client Profile Dashboard",
            description="dashboard for clients",
        )

        resp = _client(user).get(
            "/api/v1/search/search/?q=customer&semantic=true",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        results = resp.data.get("results", [])
        bridge_row = next(
            (r for r in results if str(r["id"]) == str(bridge_idx.resource_id)),
            None,
        )
        self.assertIsNotNone(
            bridge_row,
            msg=f"bridge match missing from legacy path: {results}",
        )
        self.assertEqual(bridge_row.get("matched_via"), "ontology")
        self.assertIn(
            (bridge_row.get("bridge_term") or "").lower(), {"client"},
        )

    def test_legacy_path_without_semantic_param_excludes_bridge_match(self):
        tenant = _make_tenant("legacy-nopass")
        tenant.semantic_search_enabled = True
        tenant.save(update_fields=["semantic_search_enabled"])
        user = _make_user(tenant)
        _make_active_ontology(tenant, turtle_body=_EQUIV_TURTLE)

        bridge_idx = _make_search_index(
            tenant, title="Client Profile Dashboard",
            description="dashboard for clients",
        )

        resp = _client(user).get(
            "/api/v1/search/search/?q=customer",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", [])
        ids = [str(r["id"]) for r in results]
        self.assertNotIn(
            str(bridge_idx.resource_id), ids,
            msg="bridge match MUST NOT appear without ?semantic=true on the legacy path",
        )


# ---------------------------------------------------------------------------
# Audit fix — subClassOf walk is ANCESTORS only per spec
# (REQ-SEM-SEARCH-EXPAND-001 mandates "ancestors at depth ≤ 2")
# ---------------------------------------------------------------------------


class SubclassAncestorOnlyTests(TransactionTestCase):
    """Prior to the Phase 230.11 audit closeout the subClassOf walker
    BFS'd both up AND down.  The spec is explicit: "ancestors at
    depth ≤ 2" — descendant traversal silently broadens recall
    beyond what the spec promises and is now removed."""

    def test_descendant_classes_are_not_included(self):
        """A query for the parent class MUST NOT pull in subclass
        children via the subClassOf walker."""
        from hub.apps.search.semantic_query_expansion import expand_query_terms

        tenant = _make_tenant("anc-only")
        _make_active_ontology(tenant, turtle_body=_SUBCLASS_TURTLE)
        bridges = expand_query_terms(
            query="customer", tenant_id=str(tenant.id),
        )
        labels = {b.label.lower() for b in bridges}
        # Parent-direction (ancestors) MUST appear.
        self.assertIn("person", labels, msg=f"got {bridges}")
        # Child-direction (descendant) MUST NOT — this was the audit
        # fix.  GoldCustomer is a subclass of Customer in the fixture.
        self.assertNotIn("goldcustomer", labels, msg=f"got {bridges}")
