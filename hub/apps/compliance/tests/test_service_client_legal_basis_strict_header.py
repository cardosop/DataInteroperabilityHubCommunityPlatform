"""
Phase 270.C.4.2 — regression test confirming
``ComplianceServiceClient`` forwards the
``X-Compliance-Legal-Basis-Strict`` header when the caller passes
``legal_basis_strict=True``.

WHY THIS EXISTS
===============
Phase 270.C.4 added per-tenant strict-mode for legal-basis
validation. For the defense to function end-to-end, the Django-
side service client MUST forward the spec-mandated header on
both endpoints when (and ONLY when) the tenant's
``compliance_legal_basis_strict`` flag is True. Equally important:
when the flag is False (the default for staging/dev + existing
prod tenants), the header MUST be OMITTED so the compliance-
service's default-False parse keeps the Phase 19.7.1 lenient
response shape — zero-config backward compat for unmodified
callers.

NO MOCKS POLICY
===============
``httpx.MockTransport`` is the standard ``httpx`` test utility
for inspecting an outgoing request without making a real network
call — same precedent as
``test_service_client_x_actor_id_header.py``. The PRODUCTION
header-building code in ``service_client.py`` runs unchanged.
"""
from __future__ import annotations
import pytest

import httpx
from django.test import TestCase, override_settings

from hub.apps.compliance.service_client import ComplianceServiceClient

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(SERVICE_ACTOR_ID="hub-test-actor")
@pytest.mark.integration
class TestComplianceServiceClientForwardsLegalBasisStrictHeader(TestCase):
    """The header is forwarded ONLY when ``legal_basis_strict=True``.
    Omitted otherwise so the compliance-service defaults to
    lenient — preserves Phase 19.7.1 behaviour for unmodified
    callers."""

    def setUp(self):
        self.client = ComplianceServiceClient()
        self.client._circuit_breaker.reset()

    def tearDown(self):
        if hasattr(self.client, "client") and self.client.client:
            self.client.client.close()

    def _intercept(self):
        """Build an ``httpx.MockTransport`` handler that records
        every outbound request."""
        recorded: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded.append(request)
            # Return a valid response shape for whichever endpoint
            # is hit — both methods only care about the response
            # JSON parsing, not the body content.
            return httpx.Response(
                200,
                json={
                    "overall_status": "PASS",
                    "risk_level": "LOW",
                    "allowed_to_store": True,
                    "job_id": "abc12345_00000000-0000-0000-0000-000000000000",
                    "status": "QUEUED",
                    "poll_url": "/scan-result/x",
                },
                request=request,
            )

        return httpx.MockTransport(handler), recorded

    # -----------------------------------------------------------------
    # scan_file (sync path)
    # -----------------------------------------------------------------

    @pytest.mark.integration
    def test_scan_file_omits_header_by_default(self):
        """No ``legal_basis_strict`` argument → header omitted —
        preserves backward-compat for any caller not yet wired
        to the new flag."""
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(
            transport=transport, base_url=self.client.base_url,
        )

        self.client.scan_file(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt",
        )
        self.assertEqual(len(recorded), 1)
        request = recorded[0]
        self.assertNotIn(
            "X-Compliance-Legal-Basis-Strict", request.headers,
            "Default (legal_basis_strict=False) MUST omit the header — "
            "preserves Phase 19.7.1 wire format",
        )

    @pytest.mark.integration
    def test_scan_file_omits_header_when_explicit_false(self):
        """Explicit ``legal_basis_strict=False`` — same as default,
        header omitted."""
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(
            transport=transport, base_url=self.client.base_url,
        )

        self.client.scan_file(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt",
            legal_basis_strict=False,
        )
        self.assertNotIn(
            "X-Compliance-Legal-Basis-Strict",
            recorded[0].headers,
        )

    @pytest.mark.integration
    def test_scan_file_forwards_header_when_strict(self):
        """``legal_basis_strict=True`` → header SENT with value
        ``"true"``."""
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(
            transport=transport, base_url=self.client.base_url,
        )

        self.client.scan_file(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt",
            legal_basis_strict=True,
        )
        self.assertEqual(len(recorded), 1)
        self.assertEqual(
            recorded[0].headers.get("X-Compliance-Legal-Basis-Strict"),
            "true",
        )

    # -----------------------------------------------------------------
    # scan_file_async (async path)
    # -----------------------------------------------------------------

    @pytest.mark.integration
    def test_scan_file_async_omits_header_by_default(self):
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(
            transport=transport, base_url=self.client.base_url,
        )

        self.client.scan_file_async(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt",
        )
        self.assertNotIn(
            "X-Compliance-Legal-Basis-Strict",
            recorded[0].headers,
        )

    @pytest.mark.integration
    def test_scan_file_async_forwards_header_when_strict(self):
        transport, recorded = self._intercept()
        self.client.client = httpx.Client(
            transport=transport, base_url=self.client.base_url,
        )

        self.client.scan_file_async(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            tenant_id="tnt",
            legal_basis_strict=True,
        )
        self.assertEqual(
            recorded[0].headers.get("X-Compliance-Legal-Basis-Strict"),
            "true",
        )
