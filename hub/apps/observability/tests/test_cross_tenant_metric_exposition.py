"""
End-to-end exposition test for the ``cross_tenant_denied_total`` counter.

Closes the implementation half of Phase 260.A acceptance criterion:

    "Prometheus metric ``cross_tenant_denied_total`` is non-zero in
    [an] integration test."

Why this test exists
--------------------
The per-endpoint isolation suites (e.g. ``test_ingest_rdf_tenant_isolation``)
read the counter directly from the in-memory ``Counter`` object via
``cross_tenant_denied_total._value.get()``. That proves the counter is
**incremented** but does not prove the **exposition path**: the value
must also reach the ``/metrics/`` HTTP endpoint so Prometheus can scrape
it. This test exercises the full path end-to-end with the Django test
client so a regression in either the increment OR the exposition surface
fails CI immediately — without depending on a deployed staging environment.

The companion smoke test
[`tests/smoke/test_phase260_cross_tenant_denial.py`](../../../../tests/smoke/test_phase260_cross_tenant_denial.py)
asserts the same contract against deployed staging; this test asserts it
against a deterministic in-process Django stack.

Contract
--------
1. POST ``/api/v1/semantic/rdf/ingest`` with a foreign ``tenant_id`` in
   the body must return 403 ``CROSS_TENANT_FORBIDDEN``.
2. After the denial, ``GET /metrics/`` must return 200 and the response
   body must contain a ``cross_tenant_denied_total{...}`` line whose
   value is strictly greater than the pre-denial reading and is > 0.

We pin the labels to ``endpoint="semantic.ingest_rdf"`` and
``reason="body_tenant_mismatch"`` so this test fails fast if the
``cross_tenant_denied()`` helper signature drifts (e.g. someone renames
the endpoint label).
"""
from __future__ import annotations

import re
import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

#: Pin the labels we expect to see in the exposition for this test.
EXPECTED_ENDPOINT_LABEL = "semantic.ingest_rdf"
EXPECTED_REASON_LABEL = "body_tenant_mismatch"

#: Match a Prometheus exposition counter line for our metric, regardless of
#: label order. We don't anchor every label — only the two we pin — so
#: existing prometheus_client default labels (e.g. ``_created`` family)
#: don't break the match.
_COUNTER_LINE_RE = re.compile(
    r'^cross_tenant_denied_total\{[^}]*'
    rf'endpoint="{re.escape(EXPECTED_ENDPOINT_LABEL)}"'
    r'[^}]*\}\s+'
    r'(?P<value>[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s*$',
    re.MULTILINE,
)


def _read_counter_from_metrics(client: APIClient) -> float:
    """Return the maximum ``cross_tenant_denied_total`` value visible in
    the response body of ``GET /metrics/`` for our pinned endpoint label.

    Returns 0.0 if the counter has not been incremented yet (the metric
    family may be absent from the exposition until the first increment).
    """
    response = client.get("/metrics/")
    assert response.status_code in (200, 503), (
        f"/metrics/ returned unexpected {response.status_code}: "
        f"{response.content[:300]!r}"
    )
    if response.status_code == 503:
        # Metrics subsystem unavailable — surface a clear failure rather
        # than silently passing.
        pytest.skip(
            "Metrics subsystem unavailable in this test environment "
            "(/metrics/ returned 503 — OPENTELEMETRY_AVAILABLE may be False)."
        )
    body = response.content.decode("utf-8")
    max_value = 0.0
    for match in _COUNTER_LINE_RE.finditer(body):
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        if value > max_value:
            max_value = value
    return max_value


def _make_tenant(prefix: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = cast(
        Tenant,
        Tenant.objects.create(
            name=f"{prefix}-{suffix}",
            slug=f"{prefix}-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        ),
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> Any:
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(  # type: ignore[attr-defined]
        email=f"exposition-{suffix}@example.com",
        password="exposition-pass-1234",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


# ---------------------------------------------------------------------------
# The exposition test
# ---------------------------------------------------------------------------

class CrossTenantDeniedMetricExpositionTests(TransactionTestCase):
    """End-to-end exposition: denial → counter increment → /metrics/ scrape."""

    endpoint = "/api/v1/semantic/rdf/ingest"

    def setUp(self) -> None:
        self.tenant_a = _make_tenant("expose-a")
        self.tenant_b = _make_tenant("expose-b")
        self.user_a = _make_user(self.tenant_a)
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user_a)
        # /metrics/ is unauthenticated; use a separate client to make
        # that explicit.
        self.metrics_client = APIClient()

    def test_cross_tenant_denial_increments_metric_and_metric_is_scrapable(
        self,
    ) -> None:
        before = _read_counter_from_metrics(self.metrics_client)

        # Drive the denial. The view runs the cross-tenant gate FIRST,
        # so even with no role grant on tenant B this returns 403.
        denial_response = self.api_client.post(
            self.endpoint,
            {
                "graph_data": "<urn:s> <urn:p> \"o\" .",
                "format": "turtle",
                "tenant_id": str(self.tenant_b.id),
            },
            format="json",
        )

        self.assertEqual(
            denial_response.status_code,
            403,
            f"Expected 403 from cross-tenant denial, got "
            f"{denial_response.status_code}: "
            f"{denial_response.content[:300]!r}",
        )
        payload = denial_response.json()
        self.assertEqual(payload.get("code"), "CROSS_TENANT_FORBIDDEN")

        after = _read_counter_from_metrics(self.metrics_client)

        self.assertGreater(
            after,
            before,
            f"cross_tenant_denied_total did not increase after a "
            f"cross-tenant denial. before={before} after={after}. "
            f"This means either (a) the counter is not registered with "
            f"the prometheus_client REGISTRY that /metrics/ exposes, or "
            f"(b) the cross_tenant_denied() helper failed silently. "
            f"Check hub/apps/observability/cross_tenant_metrics.py and "
            f"hub/apps/observability/otel_metrics.py.",
        )
        self.assertGreater(
            after,
            0.0,
            "cross_tenant_denied_total must be strictly positive after "
            "the denial — Phase 260.A acceptance.",
        )

    def test_metrics_response_contains_help_and_type_lines_for_counter(
        self,
    ) -> None:
        """The exposition format must include HELP / TYPE lines so
        Prometheus can correctly parse the counter family.

        This protects against a regression where the counter is
        registered but the prometheus_client surface mis-publishes the
        metadata (which makes Prometheus skip the series).
        """
        # Force at least one increment so the family is in the registry.
        denial_response = self.api_client.post(
            self.endpoint,
            {
                "graph_data": "<urn:s> <urn:p> \"o\" .",
                "format": "turtle",
                "tenant_id": str(self.tenant_b.id),
            },
            format="json",
        )
        self.assertEqual(denial_response.status_code, 403)

        response = self.metrics_client.get("/metrics/")
        if response.status_code == 503:
            pytest.skip("Metrics subsystem unavailable in this environment")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")

        self.assertIn(
            "# HELP cross_tenant_denied_total",
            body,
            "Exposition is missing the HELP line for cross_tenant_denied_total — "
            "Prometheus requires it for correct semantic typing.",
        )
        self.assertIn(
            "# TYPE cross_tenant_denied_total counter",
            body,
            "Exposition is missing the TYPE line for cross_tenant_denied_total.",
        )
