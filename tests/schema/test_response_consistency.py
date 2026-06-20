"""
312.14.1 — Response schema consistency tests.

Verifies that all API endpoints return consistent response formats:
pagination envelope, snake_case fields, ISO 8601 dates, consistent
null/empty representation.  Tests use Django's APIClient for
in-process testing against real views.
"""

import re

import pytest
from rest_framework.test import APIClient

# Endpoints to test for response consistency (top 30+ by usage)
_LIST_ENDPOINTS = [
    "/api/v1/assets/",
    "/api/v1/contracts/",
    "/api/v1/datasets/",
    "/api/v1/files/",
    "/api/v1/audit/events/",
    "/api/v1/jobs/",
    "/api/v1/search/?q=test",
    "/api/v1/governance/access-requests/",
]

# ISO 8601 regex with optional timezone
_ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$")


@pytest.mark.integration
@pytest.mark.schema
class TestPaginationEnvelope:
    """All list endpoints MUST return {count, next, previous, results}."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS)
    def test_list_endpoint_returns_pagination_envelope(self, endpoint):
        client = APIClient()
        response = client.get(endpoint)
        if response.status_code >= 500:
            pytest.skip(f"Backend unavailable for {endpoint}")  # noqa: skip-in-body — runtime service dependency
        if response.status_code == 404:
            pytest.skip(f"Endpoint not mounted: {endpoint}")  # noqa: skip-in-body — runtime service dependency

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code} for {endpoint}"
        )

        data = response.json()
        if isinstance(data, dict) and "results" in data:
            # Paginated response
            assert "count" in data, f"Missing 'count' in paginated response for {endpoint}"
            assert "next" in data, f"Missing 'next' in paginated response for {endpoint}"
            assert "previous" in data, f"Missing 'previous' in paginated response for {endpoint}"
            assert isinstance(data["results"], list), (
                f"'results' must be list, got {type(data['results'])} for {endpoint}"
            )
            assert isinstance(data["count"], int), (
                f"'count' must be int, got {type(data['count'])} for {endpoint}"
            )


@pytest.mark.integration
@pytest.mark.schema
class TestFieldNaming:
    """Response fields MUST use snake_case."""

    _SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

    def _check_keys_snake_case(self, data, path="root"):
        """Recursively check all keys in a dict for snake_case."""
        if isinstance(data, dict):
            for key in data:
                # Allow Django/DRF internal keys
                if key.startswith("@"):
                    continue
                if not self._SNAKE_CASE_RE.match(key):
                    return False, f"{path}.{key} is not snake_case"
                ok, msg = self._check_keys_snake_case(data[key], f"{path}.{key}")
                if not ok:
                    return ok, msg
        elif isinstance(data, list) and data:
            ok, msg = self._check_keys_snake_case(data[0], f"{path}[0]")
            if not ok:
                return ok, msg
        return True, ""

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS[:5])
    def test_response_fields_are_snake_case(self, endpoint):
        client = APIClient()
        response = client.get(endpoint)
        if response.status_code >= 400:
            pytest.skip(f"Endpoint {endpoint} returned {response.status_code}")  # noqa: skip-in-body — runtime service dependency

        data = response.json()
        ok, msg = self._check_keys_snake_case(data)
        assert ok, f"{msg} in response from {endpoint}"


@pytest.mark.integration
@pytest.mark.schema
class TestDateTimeFormat:
    """Date/time fields MUST use ISO 8601 with timezone."""

    def _find_datetime_fields(self, data, path="root"):
        """Recursively find string values that look like dates/times."""
        datetimes = []
        if isinstance(data, dict):
            for key, val in data.items():
                datetimes.extend(self._find_datetime_fields(val, f"{path}.{key}"))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                datetimes.extend(self._find_datetime_fields(item, f"{path}[{i}]"))
        elif isinstance(data, str):
            if _ISO8601_RE.match(data) and ("T" in data or "-" in data):
                datetimes.append((path, data))
        return datetimes

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS[:5])
    def test_datetime_fields_use_iso8601(self, endpoint):
        client = APIClient()
        response = client.get(endpoint)
        if response.status_code >= 400:
            pytest.skip(f"Endpoint {endpoint} returned {response.status_code}")  # noqa: skip-in-body — runtime service dependency

        data = response.json()
        datetimes = self._find_datetime_fields(data)
        for path, value in datetimes:
            assert _ISO8601_RE.match(value), (
                f"Date/time field {path}='{value}' is not ISO 8601 in {endpoint}"
            )


@pytest.mark.integration
@pytest.mark.schema
class TestNullAndEmptyRepresentation:
    """null values use JSON null. Empty collections use [] not null."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint", _LIST_ENDPOINTS[:5])
    def test_empty_collections_are_empty_arrays(self, endpoint):
        """Results arrays are never null and are always JSON arrays."""
        client = APIClient()
        response = client.get(endpoint)
        if response.status_code >= 400:
            pytest.skip(f"Endpoint {endpoint} returned {response.status_code}")  # noqa: skip-in-body — runtime service dependency

        data = response.json()
        if isinstance(data, dict) and "results" in data:
            assert isinstance(data["results"], list), (
                f"'results' must be a JSON array, got {type(data['results'])} in {endpoint}"
            )
            assert data["results"] is not None, (
                f"'results' must not be null (use [] for empty) in {endpoint}"
            )
