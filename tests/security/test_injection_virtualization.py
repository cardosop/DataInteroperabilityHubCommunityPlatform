"""
Security tests: Injection on Virtualization API.

Per tasks 29.5.4. SQL/NoSQL/command injection via virtualization query params.
Uses real APIClient and real DB; no mocks.
"""

import pytest
from rest_framework import status

from .base_injection import InjectionTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationInjectionAPITest(InjectionTestBase):
    """Test that Virtualization API inputs are sanitized against injection."""

    def test_virtual_datasets_list_with_sql_like_search(self):
        """Virtual datasets list with search param that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE virtualization_virtualdataset; --",
            "1 OR 1=1",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/virtualization/datasets/",
                data={"search": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Virtual datasets search param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                    "Response must remain list or paginated",
                )

    def test_virtual_datasets_list_with_sql_like_ordering(self):
        """Virtual datasets list with ordering param that looks like SQL is safely handled."""
        payloads = [
            "id); DROP TABLE virtualization_virtualdataset; --",
            "-created_at",
            "name",
        ]
        for order in payloads:
            response = self.client.get(
                "/api/v1/virtualization/datasets/",
                data={"ordering": order},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Virtual datasets ordering {order!r} must not cause 500",
            )

    def test_virtual_datasets_list_with_sql_like_status_filter(self):
        """Virtual datasets list with status param that looks like SQL is safely handled."""
        payloads = [
            "ACTIVE'); DROP TABLE virtualization_virtualdataset; --",
            "ACTIVE",
            "1 OR 1=1",
        ]
        for s in payloads:
            response = self.client.get(
                "/api/v1/virtualization/datasets/",
                data={"status": s},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Virtual datasets status param {s!r} must not cause 500",
            )
