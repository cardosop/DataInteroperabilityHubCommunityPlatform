"""
Phase 240.3.E.1 — DQRun CRUD endpoints dual-mount tests.

Pins the contract for the deprecated ``/api/v1/quality/runs/...``
alias of the canonical ``/api/v1/dq/runs/...`` ViewSet:

* every CRUD verb that works on the canonical mount works on the
  alias (list, retrieve, create, results @action);
* every alias response carries RFC 8594 ``Sunset`` and
  ``Deprecation`` headers + an RFC 8288 ``Link`` header pointing
  at the canonical successor;
* the canonical mount does NOT carry those headers (they're only
  for clients still on the old path).

Phase 240.3.B already dual-mounted the four advanced quality
endpoints (anomalies / trends / scorecards / root-cause) in
``test_quality_endpoints.py``; this file extends the same shape
to the runs CRUD surface.

Real implementations throughout — same Django test-client +
real DB rows pattern as the rest of the dq test suite. No
mocks.
"""
from __future__ import annotations

import uuid

import pytest
from rest_framework import status

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITestBase


pytestmark = pytest.mark.django_db(transaction=True)


CANONICAL_RUNS_PREFIX = "/api/v1/dq/runs"
DEPRECATED_RUNS_PREFIX = "/api/v1/quality/runs"


class DQRunsDualMountBase(DQAPITestBase):
    """Common fixtures for the runs-dual-mount suite."""

    def setUp(self):
        super().setUp()

        # Pre-seed a single DQRun in *this* tenant so list() and
        # retrieve() have something to return on both prefixes.
        # DQRun has no ``created_by`` field — it tracks ownership via
        # ``tenant`` + ``job.created_by`` (the user who triggered the
        # DQ run via a Job). ``engine`` is required (DQRun.save()
        # calls full_clean() which validates non-blank); we pin it
        # to GX since the canonical profile_key uses the GX adapter.
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=DQRunStatus.PENDING,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )


# ────────────────────────────────────────────────────────────────────
# Reachability — every CRUD verb resolves on both prefixes
# ────────────────────────────────────────────────────────────────────


class DQRunsDualMountReachabilityTest(DQRunsDualMountBase):

    def test_list_works_on_deprecated_prefix(self):
        """``GET /api/v1/quality/runs/`` returns 200 + same paginated
        envelope as the canonical mount."""
        canonical = self.client.get(f"{CANONICAL_RUNS_PREFIX}/")
        deprecated = self.client.get(f"{DEPRECATED_RUNS_PREFIX}/")

        self.assertEqual(canonical.status_code, status.HTTP_200_OK)
        self.assertEqual(deprecated.status_code, status.HTTP_200_OK)

        # Same DRF paginator → same top-level keys (results / count /
        # next / previous). Comparing the *set* of keys, not the values,
        # because pagination order/timing isn't load-bearing here.
        self.assertEqual(
            set(canonical.data.keys()), set(deprecated.data.keys()),
            "Deprecated runs alias must surface the same paginated "
            "envelope as the canonical mount.",
        )

        # Per-tenant filtering MUST also apply on the alias —
        # otherwise the alias would be a tenant-isolation bypass.
        canonical_ids = {row["id"] for row in canonical.data["results"]}
        deprecated_ids = {row["id"] for row in deprecated.data["results"]}
        self.assertEqual(canonical_ids, deprecated_ids)
        self.assertIn(str(self.dq_run.id), deprecated_ids)

    def test_retrieve_works_on_deprecated_prefix(self):
        """``GET /api/v1/quality/runs/{id}/`` returns 200 + the
        full DQRun payload."""
        url = f"{DEPRECATED_RUNS_PREFIX}/{self.dq_run.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.dq_run.id))
        # Sanity: the serializer is the same on both mounts —
        # canonical retrieve must produce an equal payload.
        canonical_response = self.client.get(
            f"{CANONICAL_RUNS_PREFIX}/{self.dq_run.id}/",
        )
        self.assertEqual(response.data, canonical_response.data)

    def test_results_action_works_on_deprecated_prefix(self):
        """``GET /api/v1/quality/runs/{id}/results/`` resolves to
        the same ``@action`` as the canonical mount.

        We can't use status-code parity alone to prove routing —
        a 404 from the view (resource missing) is indistinguishable
        from a 404 from the resolver (URL pattern unmatched). Instead
        we check ``Sunset`` header presence: it's set in
        ``DeprecatedDQRunViewSet.finalize_response`` and ONLY fires
        if the request reached our deprecated ViewSet. A
        ``Resolver404`` would short-circuit before any view runs and
        the header would be absent.
        """
        url = f"{DEPRECATED_RUNS_PREFIX}/{self.dq_run.id}/results/"
        response = self.client.get(url)

        self.assertIn(
            "Sunset", response.headers,
            "Routing failure: /api/v1/quality/runs/{id}/results/ "
            "didn't reach DeprecatedDQRunViewSet.finalize_response. "
            f"Got status={response.status_code}, headers="
            f"{dict(response.headers)}.",
        )

        # Status-code parity with canonical — same view, same logic,
        # same outcome (whether 200 with computed results or a
        # well-defined 4xx for an in-flight run).
        canonical_response = self.client.get(
            f"{CANONICAL_RUNS_PREFIX}/{self.dq_run.id}/results/",
        )
        self.assertEqual(response.status_code, canonical_response.status_code)

    def test_create_works_on_deprecated_prefix(self):
        """``POST /api/v1/quality/runs/`` is routed to the create
        action. We use ``Sunset`` header presence as the routing
        proof (same reasoning as the results-action test above) —
        a missing URL pattern would trigger ``Resolver404`` BEFORE
        any view runs, leaving the header absent. Status-code
        parity with canonical pins that the alias produces the
        same validation outcome."""
        canonical = self.client.post(
            f"{CANONICAL_RUNS_PREFIX}/", data={}, format="json",
        )
        deprecated = self.client.post(
            f"{DEPRECATED_RUNS_PREFIX}/", data={}, format="json",
        )

        self.assertIn(
            "Sunset", deprecated.headers,
            "Routing failure: POST /api/v1/quality/runs/ didn't "
            "reach DeprecatedDQRunViewSet (Sunset header missing). "
            f"Got status={deprecated.status_code}, headers="
            f"{dict(deprecated.headers)}.",
        )
        self.assertEqual(canonical.status_code, deprecated.status_code)


# ────────────────────────────────────────────────────────────────────
# Surface stability — the alias mount does NOT publish an API root
# ────────────────────────────────────────────────────────────────────


class DQRunsDualMountSurfaceStabilityTest(DQRunsDualMountBase):
    """Audit-fix regression (GAP-A): the deprecated mount uses
    ``SimpleRouter`` (not ``DefaultRouter``) so probing
    ``/api/v1/quality/`` returns 404 — same as before Phase 240.3.E.
    Otherwise the DRF root view ``rest_framework.routers.APIRootView``
    would publish the alias's route table to anyone with curl,
    WITHOUT carrying ``Sunset`` (the root view doesn't inherit our
    mixin) — defeating the migration-warning surface."""

    def test_quality_root_path_returns_404(self):
        response = self.client.get("/api/v1/quality/")
        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND,
            "Deprecated /api/v1/quality/ must NOT publish a "
            "route-listing API root view. The DRF "
            "``DefaultRouter`` would surface one at this path; the "
            "deprecated mount must use ``SimpleRouter`` to skip it.",
        )


# ────────────────────────────────────────────────────────────────────
# Deprecation headers — RFC 8594 (Sunset) + RFC 8288 (Link)
# ────────────────────────────────────────────────────────────────────


class DQRunsDualMountHeadersTest(DQRunsDualMountBase):

    def test_canonical_runs_does_not_emit_deprecation_headers(self):
        """The canonical path is the FUTURE path — clients on it
        must NOT see deprecation headers (else every HTTP middleware
        in the world thinks the canonical path is going away)."""
        url = f"{CANONICAL_RUNS_PREFIX}/{self.dq_run.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Sunset", response.headers)
        self.assertNotIn("Deprecation", response.headers)

    def test_deprecated_runs_emits_sunset_header(self):
        """RFC 8594 ``Sunset`` carries an HTTP-date 180 days from the
        Phase 240 merge anchor. We assert presence + non-empty
        value — the exact date is pinned in
        ``quality_deprecated_urls._SUNSET_DATE`` and tested there."""
        url = f"{DEPRECATED_RUNS_PREFIX}/{self.dq_run.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "Sunset", response.headers,
            "Deprecated /api/v1/quality/runs/* must carry an "
            "RFC 8594 Sunset header per Phase 227 + D240.10.",
        )
        # IMF-fixdate ends in ``GMT`` per RFC 7231 §7.1.1.1.
        self.assertTrue(
            response.headers["Sunset"].endswith("GMT"),
            f"Sunset must be an RFC 7231 IMF-fixdate, "
            f"got: {response.headers['Sunset']!r}",
        )

    def test_deprecated_runs_emits_deprecation_header(self):
        url = f"{DEPRECATED_RUNS_PREFIX}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "Deprecation", response.headers,
            "Deprecated /api/v1/quality/runs/ must carry the "
            "Deprecation header (HTTP-date of merge).",
        )

    def test_deprecated_runs_emits_link_header_to_canonical_successor(self):
        """The ``Link: <successor>; rel=successor-version`` header
        must point at the canonical mount so machine-readable
        clients can auto-migrate."""
        url = f"{DEPRECATED_RUNS_PREFIX}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Link", response.headers)
        link = response.headers["Link"]
        self.assertIn("/api/v1/dq/runs", link, (
            "Link header must reference the canonical /dq/runs/ "
            f"successor; got: {link!r}"
        ))
        self.assertIn('rel="successor-version"', link)

    def test_deprecated_runs_results_action_emits_deprecation_headers(self):
        """The @action sub-path must also carry the headers — clients
        polling ``/quality/runs/{id}/results/`` shouldn't be silently
        excluded from the migration-warning surface."""
        url = f"{DEPRECATED_RUNS_PREFIX}/{self.dq_run.id}/results/"
        response = self.client.get(url)

        # The action may 4xx for an in-flight run, but Sunset /
        # Deprecation are emitted on EVERY response by
        # ``finalize_response`` — including error responses — so the
        # client always sees the warning.
        self.assertIn("Sunset", response.headers)
        self.assertIn("Deprecation", response.headers)
        self.assertIn("Link", response.headers)


# ────────────────────────────────────────────────────────────────────
# Behaviour parity — alias is NOT a side-channel
# ────────────────────────────────────────────────────────────────────


class DQRunsDualMountParityTest(DQRunsDualMountBase):

    def test_alias_respects_tenant_isolation(self):
        """Cross-tenant rows must NOT leak through the alias —
        same isolation enforced as the canonical mount."""
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        User = get_user_model()
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="x",
            tenant=other_tenant,
        )

        # Authenticate AS the other tenant's user, then list via
        # the alias. The seeded ``self.dq_run`` belongs to
        # ``self.tenant`` and must NOT appear.
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f"{DEPRECATED_RUNS_PREFIX}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        leaked_ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(
            str(self.dq_run.id), leaked_ids,
            "Tenant isolation broken on the deprecated alias — "
            "cross-tenant DQRun leaked into the response.",
        )
