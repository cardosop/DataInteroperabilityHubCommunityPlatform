"""Tests for internal_pipeline_config view.

These tests call the view function directly to avoid middleware interactions
in the test environment.  The URL routing is tested implicitly by the
module-level ``urls.py`` registration.
"""

import json
import uuid

import pytest
from django.http import HttpRequest
from django.test import override_settings

from hub.data_movement.internal_views import internal_pipeline_config

pytestmark = pytest.mark.django_db(transaction=True)


def _get(path: str) -> HttpRequest:
    """Build a minimal GET request for view testing."""
    request = HttpRequest()
    request.method = "GET"
    request.path = path
    request.META = {}
    request.GET = {}
    return request


class TestInternalPipelineConfig:
    """Tests for GET /api/v1/data-movement/internal/config/{direction}/{id}/"""

    @override_settings(INTERNAL_API_KEY="")
    def test_ingestion_config_returns_200(self, scheduled_ingestion):
        """Valid ingestion ID returns pipeline config (dev mode — empty key)."""
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 200, response.content
        body = json.loads(response.content)
        assert body["direction"] == "ingestion"
        assert body["source_type"] == scheduled_ingestion.source_type
        assert "dlt_source" in body
        assert "credentials" in body

    @override_settings(INTERNAL_API_KEY="")
    def test_export_config_returns_200(self, scheduled_export):
        """Valid export ID returns pipeline config."""
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="export",
            resource_id=str(scheduled_export.id),
        )
        assert response.status_code == 200, response.content
        body = json.loads(response.content)
        assert body["direction"] == "export"
        assert body["destination_type"] == scheduled_export.destination_type
        assert "dlt_destination" in body
        assert "credentials" in body

    @override_settings(INTERNAL_API_KEY="")
    def test_nonexistent_resource_returns_404(self):
        """Unknown ID returns 404."""
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(uuid.uuid4()),
        )
        assert response.status_code == 404

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_unauthorized_request_returns_403(self, scheduled_ingestion):
        """Missing API key returns 403 when key is configured."""
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 403

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_authorized_request_returns_200(self, scheduled_ingestion):
        """Correct API key allows access."""
        request = _get("/")
        request.META["HTTP_X_INTERNAL_API_KEY"] = "test-key-123"
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 200, response.content
