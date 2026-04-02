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
