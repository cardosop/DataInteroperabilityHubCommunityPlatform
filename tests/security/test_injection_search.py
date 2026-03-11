"""
Security tests: Injection on Search API.

Per tasks 29.5.4. SQL/NoSQL/command injection via search query params.
Uses real APIClient and real DB; no mocks.
"""

import pytest
from rest_framework import status

from .base_injection import InjectionTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class SearchInjectionAPITest(InjectionTestBase):
    """Test that Search API inputs are sanitized against injection."""

    def test_search_with_sql_like_query(self):
        """Search with q param that looks like SQL is safely handled."""
        payloads = [
            "'; DROP TABLE search_searchindex; --",
            "1 OR 1=1",
            "1; SELECT * FROM auth_user",
            "%' OR '1'='1",
        ]
        for q in payloads:
            response = self.client.get(
                "/api/v1/search/search/",
                data={"q": q},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Search q param {q!r} must not cause 500",
            )
            if response.status_code == 200:
                data = getattr(response, "data", None) or (
                    response.json() if hasattr(response, "json") else {}
                )
                self.assertTrue(
                    isinstance(data, dict),
                    "Search response must be dict",
                )
                self.assertIn(
                    "results",
                    data,
                    "Search response must have results key",
                )

    def test_search_with_sql_like_type_filter(self):
        """Search with type param that looks like SQL is safely handled."""
        payloads = [
            "CONTRACT'); DROP TABLE search_searchindex; --",
            "ASSET",
            "1 OR 1=1",
        ]
        for t in payloads:
            response = self.client.get(
                "/api/v1/search/search/",
                data={"q": "test", "type": t},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Search type param {t!r} must not cause 500",
            )

    def test_search_with_sql_like_tags_param(self):
        """Search with tags param that looks like SQL is safely handled."""
        payloads = [
            "tag'); DROP TABLE search_searchindex; --",
            "tag1,tag2",
        ]
        for tags in payloads:
            response = self.client.get(
                "/api/v1/search/search/",
                data={"q": "test", "tags": tags},
                HTTP_ACCEPT="application/json",
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
                f"Search tags param {tags!r} must not cause 500",
            )
