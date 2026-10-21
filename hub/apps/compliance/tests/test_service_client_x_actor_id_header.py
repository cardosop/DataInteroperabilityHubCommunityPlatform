"""
Phase 270.C.1/270.C.2 — regression test confirming
``ComplianceServiceClient`` forwards the ``X-Actor-Id`` header on
the sync and async endpoints, carrying the **tenant id**.

WHY THIS EXISTS
===============
Phase 270.C.2 made ``X-Actor-Id`` the authoritative TENANT in the
compliance-service: the service cross-checks the header against the
body ``tenant_id`` and rejects with 400 ``TENANT_MISMATCH`` when
they disagree. Phase 270.C.1 additionally derives a SHA-256 prefix
from the incoming ``X-Actor-Id`` and embeds it in the async job_id;
the GET poll endpoint re-derives the prefix from the polling
caller's header and rejects with 403 ``JOB_TENANT_MISMATCH`` on a
mismatch.

For the defense to actually function end-to-end, the Django-side
service client (``hub/apps/compliance/service_client.py``) MUST:

  * send the tenant id as ``X-Actor-Id``, matching the body
    ``tenant_id`` (the old behaviour — sending ``SERVICE_ACTOR_ID``
    — produced a permanent 400 TENANT_MISMATCH once 270.C.2 landed),
  * forward ``X-Actor-Id`` on BOTH ``POST /scan-file-async``
    (submit — server captures the actor) and ``GET /scan-result``
    (poll — server verifies the actor).

This regression test pins that contract so a future refactor of the
client can't silently regress either property.

NO MOCKS POLICY
===============
``httpx.MockTransport`` is the standard ``httpx`` test utility for
inspecting an outgoing request without making a real network call.
It does NOT mock business logic — it intercepts at the transport
layer (the same level a corporate proxy would intercept at). This
is the same pattern the existing
``test_service_client.test_scan_file_endpoint_construction``
already uses. The PRODUCTION header-building code in
``service_client.py`` runs unchanged.
"""

from __future__ import annotations

import httpx
import pytest
from django.test import TestCase

from hub.apps.compliance.service_client import ComplianceServiceClient

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestComplianceServiceClientForwardsXActorIdHeader(TestCase):
    """The async endpoints — submit + poll — MUST both forward
    ``X-Actor-Id`` carrying the tenant id so the compliance-service's
    tenant-scoped job_id machinery works end-to-end."""

    def setUp(self):
        self.client = ComplianceServiceClient()
        # Reset the circuit breaker so a flaky service env from a
        # prior test in this process doesn't surface as a 503-fallback
        # path that bypasses our intercepted handler.
        self.client._circuit_breaker.reset()

    def tearDown(self):
        if hasattr(self.client, "client") and self.client.client:
            self.client.client.close()

    def _intercept(self):
        """Build an httpx.MockTransport handler that records every
        outbound request. Returns ``(transport, recorded)`` where
        ``recorded`` is the list mutated by the handler.
        """
        recorded: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded.append(request)
            # Both endpoints we care about return JSON; the body
            # is irrelevant to header assertions but must be
            # valid so the client's response.json() doesn't blow
            # up after our intercept returns.
            return httpx.Response(
                200,
                json={
                    "job_id": "deadbeef_00000000-0000-0000-0000-000000000000",
                    "status": "QUEUED",
                    "poll_url": "/scan-result/x",
                },
                request=request,
            )

        return httpx.MockTransport(handler), recorded

    @pytest.mark.integration
    def test_scan_file_async_sends_tenant_as_x_actor_id(self):
        """``POST /scan-file-async`` MUST carry ``X-Actor-Id`` equal
        to the tenant passed in the body — Phase 270.C.2 rejects any
        other value with 400 TENANT_MISMATCH."""
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        self.client.scan_file_async(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt-test",
        )

        # Single request, X-Actor-Id present + matches the tenant id.
        self.assertEqual(len(recorded), 1, recorded)
        request = recorded[0]
        self.assertEqual(request.url.path, "/scan-file-async")
        self.assertEqual(request.method, "POST")
        self.assertIn("X-Actor-Id", request.headers, dict(request.headers))
        self.assertEqual(
            request.headers["X-Actor-Id"],
            "tnt-test",
            "Header value must be the tenant id (matching the body "
            "tenant_id) — the compliance-service cross-checks the two "
            "and derives the job_id prefix from the header.",
        )

    @pytest.mark.integration
    def test_get_scan_result_sends_tenant_as_x_actor_id(self):
        """``GET /scan-result/{job_id}`` MUST carry ``X-Actor-Id``
        with the same tenant used at submit — otherwise the
        compliance-service's tenant-scoped poll check fails with
        403 ``JOB_TENANT_MISMATCH`` and the legitimate poll path
        breaks."""
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Use a scoped-format job_id (matches the new contract).
        # The path is the load-bearing assertion; the body
        # response is irrelevant here.
        job_id = "deadbeef_00000000-0000-0000-0000-000000000000"
        self.client.get_scan_result(job_id, tenant_id="tnt-poll")

        self.assertEqual(len(recorded), 1, recorded)
        request = recorded[0]
        self.assertEqual(request.url.path, f"/scan-result/{job_id}")
        self.assertEqual(request.method, "GET")
        self.assertIn("X-Actor-Id", request.headers)
        self.assertEqual(request.headers["X-Actor-Id"], "tnt-poll")

    @pytest.mark.integration
    def test_both_endpoints_use_same_actor_id_value(self):
        """End-to-end consistency: BOTH endpoints must send the
        SAME ``X-Actor-Id`` value for the same tenant. The
        compliance-service derives the job_id prefix from the
        submit actor + verifies it against the poll actor —
        any divergence breaks every legitimate poll. This test
        guards against a future refactor that resolves
        ``actor_id`` differently in the two methods (e.g. one
        reads the tenant, the other a request-scoped var).
        """
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        self.client.scan_file_async(
            file_content=b"id\n1",
            file_format="csv",
            tenant_id="t",
        )
        self.client.get_scan_result("deadbeef_00000000-0000-0000-0000-000000000000", tenant_id="t")

        self.assertEqual(len(recorded), 2)
        post_actor = recorded[0].headers.get("X-Actor-Id")
        poll_actor = recorded[1].headers.get("X-Actor-Id")
        self.assertIsNotNone(post_actor)
        self.assertIsNotNone(poll_actor)
        self.assertEqual(
            post_actor,
            poll_actor,
            "Both async endpoints must emit the SAME X-Actor-Id "
            "value for a given tenant — otherwise the tenant-scoped "
            "job_id verification breaks for legitimate polls.",
        )
