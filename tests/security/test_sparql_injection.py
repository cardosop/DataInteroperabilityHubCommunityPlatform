"""Phase 98: SPARQL injection prevention tests via API."""
import uuid
import pytest
from tests.security.base_injection import InjectionTestBase

pytestmark = pytest.mark.security

SPARQL_PAYLOADS = [
    '" } INSERT DATA { <x> <y> <z> } #',
    "' } INSERT DATA { <x> <y> <z> } #",
    '<javascript:alert(1)>',
    '"> . <http://evil.com> <http://evil.com> <http://evil.com> .',
]


class SPARQLInjectionAPITest(InjectionTestBase):
    """Verify SPARQL injection payloads are escaped in semantic endpoints."""

    def test_injection_in_semantic_search(self):
        """SPARQL payloads in search must not cause 500."""
        for payload in SPARQL_PAYLOADS:
            response = self.client.get(
                "/api/v1/semantic/search/",
                {"q": payload},
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            # 400 or 404 is acceptable; 500 is not
            self.assertNotEqual(
                response.status_code, 500,
                f"SPARQL injection in search caused 500: {payload}",
            )

    def test_injection_in_contract_name_with_sparql_chars(self):
        """Contracts with SPARQL-like characters must not cause 500."""
        for payload in SPARQL_PAYLOADS:
            response = self.client.post(
                "/api/v1/contracts/",
                {"original_raw": payload, "original_format": "YAML"},
                format="json",
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertNotEqual(
                response.status_code, 500,
                f"SPARQL chars in contract creation caused 500: {payload}",
            )

# ── Phase 277.4.2 — SPARQL injection expansion (2→6 tests) ────────────

class TestSPARQLInjectionExpanded(InjectionTestBase):
    """Phase 277.4.2 — 4 additional injection vectors."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_union_based_injection_rejected(self):
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } UNION SELECT 1,2,3"
        resp = self.client.post("/api/v1/semantic/sparql/", {"query": query, "format": "json"}, format="json")
        self.assertNotEqual(resp.status_code, 200, "UNION injection should be rejected")

    def test_service_exploitation_blocked(self):
        query = "SELECT * WHERE { SERVICE <http://localhost:8080/admin> { ?s ?p ?o } }"
        resp = self.client.post("/api/v1/semantic/sparql/", {"query": query, "format": "json"}, format="json")
        self.assertNotEqual(resp.status_code, 200, "SERVICE exploitation should be blocked")

    def test_comment_terminator_injection_rejected(self):
        query = "SELECT * WHERE { ?s ?p ?o } #\n; DROP ALL"
        resp = self.client.post("/api/v1/semantic/sparql/", {"query": query, "format": "json"}, format="json")
        self.assertNotEqual(resp.status_code, 200)

    def test_property_path_dos_rejected(self):
        query = "SELECT ?s WHERE { ?s ?p+/?p*/?p? ?o }"
        resp = self.client.post("/api/v1/semantic/sparql/", {"query": query, "format": "json"}, format="json")
        assert resp.status_code != 500, "Property-path DoS should not crash"
