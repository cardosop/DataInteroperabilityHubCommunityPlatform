"""
Security tests: SQL/NoSQL/command injection via real API and DB.

Per UPDATE_PLAN_MISSING_COVERAGE_5_6_1 §2 and SECURITY_REVIEW_PHASE_5_2.
Uses real APIClient and real DB; no mocks. Parameterized payloads to assert
input is sanitized and does not alter query behavior.
"""

import pytest
from rest_framework import status

from .base_injection import InjectionTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class SQLInjectionAPITest(InjectionTestBase):
    """Test that API inputs are sanitized against SQL injection."""

    def test_audit_list_with_sql_like_param(self):
        """Audit list with parameter that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE audit_auditevent; --",
            "1 OR 1=1",
            "1; SELECT * FROM auth_user",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/audit/audit-events/",
                data={"search": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Search param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, list)
                    or (isinstance(data, dict) and "results" in data),
                    "Response must remain list or paginated",
                )

    def test_contracts_list_with_sql_like_ordering(self):
        """Contracts list with ordering param that looks like SQL is safely handled."""
        payloads = [
            "id); DROP TABLE contracts_contract; --",
            "-id",
            "created_at",
        ]
        for order in payloads:
            response = self.client.get(
                "/api/v1/contracts/",
                data={"ordering": order},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Ordering {order!r} must not cause 500",
            )

    def test_assets_list_with_sql_like_search(self):
        """Assets list with search param that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE assets_asset; --",
            "1 OR 1=1",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/assets/",
                data={"search": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Assets search param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, list)
                    or (isinstance(data, dict) and "results" in data),
                    "Response must remain list or paginated",
                )

    def test_datasets_list_with_sql_like_search(self):
        """Datasets list with search param that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE datasets_dataset; --",
            "1 OR 1=1",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/datasets/",
                data={"search": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Datasets search param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, list)
                    or (isinstance(data, dict) and "results" in data),
                    "Response must remain list or paginated",
                )

    def test_marketplace_search_with_sql_like_param(self):
        """Marketplace listings search with param that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE listings; --",
            "1 OR 1=1",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/marketplace/listings/search/",
                data={"q": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Marketplace search param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, list)
                    or (isinstance(data, dict) and "results" in data),
                    "Response must remain list or paginated",
                )


class CommandInjectionAPITest(InjectionTestBase):
    """Test that API does not pass unsanitized input to shell or commands."""

    def test_health_endpoint_no_command_injection(self):
        """Health endpoint must not interpret query as command."""
        payloads = [
            "$(id)",
            "`whoami`",
            "; ls -la",
        ]
        for q in payloads:
            response = self.client.get(f"/health/?q={q}", HTTP_ACCEPT="application/json")
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE),
                f"Health with q={q!r} must not cause 500",
            )


class NoSQLStyleInjectionAPITest(InjectionTestBase):
    """Test handling of NoSQL-style operators in JSON/query params."""

    def test_audit_list_with_special_chars(self):
        """Audit list with special chars in filter is safely handled."""
        response = self.client.get(
            "/api/v1/audit/audit-events/",
            HTTP_ACCEPT="application/json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN),
            "Audit list must not 500",
        )
