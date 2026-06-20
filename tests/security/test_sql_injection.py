"""Phase 98: SQL injection prevention tests."""

import pytest

from tests.security.base_injection import InjectionTestBase

pytestmark = pytest.mark.security

SQL_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1 OR 1=1",
    "1; SELECT * FROM refresh_tokens; --",
    "' UNION SELECT password FROM users --",
    "1' AND '1'='1",
]


class SQLInjectionAPITest(InjectionTestBase):
    """Verify SQL injection payloads don't cause 500 errors or data leaks."""

    def test_injection_in_search_query(self):
        """SQL payloads in search query parameter must not cause 500."""
        for payload in SQL_PAYLOADS:
            response = self.client.get(
                "/api/v1/assets/",
                {"search": payload},
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertNotEqual(
                response.status_code,
                500,
                f"SQL injection payload caused 500: {payload}",
            )

    def test_injection_in_filter_parameter(self):
        """SQL payloads in filter fields must not cause 500."""
        for payload in SQL_PAYLOADS:
            response = self.client.get(
                "/api/v1/assets/",
                {"status": payload},
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertNotEqual(
                response.status_code,
                500,
                f"SQL injection in filter caused 500: {payload}",
            )

    def test_injection_in_sort_parameter(self):
        """SQL payloads in ordering parameter must not cause 500."""
        for payload in SQL_PAYLOADS:
            response = self.client.get(
                "/api/v1/assets/",
                {"ordering": payload},
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertNotEqual(
                response.status_code,
                500,
                f"SQL injection in ordering caused 500: {payload}",
            )

    def test_injection_in_contract_creation(self):
        """SQL payloads in contract data must not cause 500."""
        for payload in SQL_PAYLOADS:
            response = self.client.post(
                "/api/v1/contracts/",
                {"original_raw": payload, "original_format": "YAML"},
                format="json",
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertNotEqual(
                response.status_code,
                500,
                f"SQL injection in contract creation caused 500: {payload}",
            )
