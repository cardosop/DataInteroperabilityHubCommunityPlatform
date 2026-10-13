"""W3.7 (oss-release-remediation R2-P6) — the internal config endpoint
fails closed and masks credentials.

Evidence pins (real DB rows + the real view function; no mocks/stubs):

* **No-key → 401** — with no ``INTERNAL_API_KEY`` configured the
  endpoint rejects EVERY request (the pre-fix dev fallback returned
  200 to anyone); a missing or wrong key header is 401 too.
* **Masked output** — a legacy PLAINTEXT config row (the pre-migration
  shape ``get_source_config`` returns as-is) never leaks its secrets:
  the response carries the sibling-endpoint masking and no resolved
  credentials block.
"""

import json
import uuid

import pytest
from django.http import HttpRequest
from django.test import override_settings

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.data_movement.internal_views import internal_pipeline_config

pytestmark = pytest.mark.django_db(transaction=True)

_SECRET_VALUE = "super-secret-material-4f9c1a"
_SECRET_KEY = "AKIA_SUPER_SECRET"


def _get(path: str, headers: dict | None = None) -> HttpRequest:
    request = HttpRequest()
    request.method = "GET"
    request.path = path
    request.META = {}
    if headers:
        request.META.update(headers)
    request.GET = {}
    return request


class TestFailClosedAuth:
    """The endpoint rejects every unauthenticated request — configured
    or not."""

    @override_settings(INTERNAL_API_KEY="")
    def test_no_key_configuration_fails_closed(self, scheduled_ingestion):
        """No INTERNAL_API_KEY configured → 401 for EVERYONE (the
        pre-fix dev fallback returned 200)."""
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 401, response.content

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_missing_key_header_returns_401(self, scheduled_ingestion):
        request = _get("/")
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 401, response.content

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_wrong_key_returns_401(self, scheduled_ingestion):
        request = _get("/", {"HTTP_X_INTERNAL_API_KEY": "wrong-key"})
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(scheduled_ingestion.id),
        )
        assert response.status_code == 401, response.content

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_authorized_request_returns_masked_config(self, scheduled_ingestion):
        """The authorized contract: 200 with the masking-shaped payload."""
        request = _get("/", {"HTTP_X_INTERNAL_API_KEY": "test-key-123"})
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
        assert "credentials" not in body, (
            "the resolved credentials block is gone — the endpoint must "
            "not hand out credential material"
        )


class TestMaskedOutput:
    """Legacy plaintext config rows never leak through the endpoint."""

    def _legacy_plaintext_ingestion(self, tenant):
        """A pre-migration-shaped row: the source_config is a PLAINTEXT
        dict (the shape get_source_config returns verbatim)."""
        from hub.apps.scheduled_ingestion.models import ScheduleType, SourceType

        obj = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"w37-legacy-{uuid.uuid4().hex[:8]}",
            source_type=SourceType.S3,
            source_config={"bucket": "legacy-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            created_by=None,
        )
        # Bypass the save-time encryption to land the legacy plaintext
        # shape in the row (queryset.update skips save()).
        type(obj).objects.filter(pk=obj.pk).update(
            source_config={
                "bucket": "legacy-bucket",
                "access_key_id": _SECRET_KEY,
                "secret_access_key": _SECRET_VALUE,
            }
        )
        return type(obj).objects.get(pk=obj.pk)

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_plaintext_secrets_are_masked(self, tenant):
        obj = self._legacy_plaintext_ingestion(tenant)
        request = _get("/", {"HTTP_X_INTERNAL_API_KEY": "test-key-123"})
        response = internal_pipeline_config(
            request,
            direction="ingestion",
            resource_id=str(obj.id),
        )
        assert response.status_code == 200, response.content
        body = json.loads(response.content)
        raw_body = json.dumps(body)
        assert _SECRET_VALUE not in raw_body, "the secret value must never leave the hub"
        assert _SECRET_KEY not in raw_body, "the secret key must never leave the hub"
        config = body["config"]
        assert config.get("secret_access_key") == f"{_SECRET_VALUE[:4]}***", (
            "the sibling-endpoint masking shape (first 4 chars + ***)"
        )
        assert config.get("access_key_id") == f"{_SECRET_KEY[:4]}***"
        assert "credentials" not in body

    @override_settings(INTERNAL_API_KEY="test-key-123")
    def test_export_plaintext_secrets_are_masked(self, tenant):
        from hub.apps.scheduled_export.models import ScheduledExport

        export = ScheduledExport.objects.create(
            tenant=tenant,
            name=f"w37-legacy-exp-{uuid.uuid4().hex[:8]}",
            schedule_config={"cron": "0 3 * * *", "timezone": "UTC"},
            destination_type="S3",
            destination_config={"bucket": "dest-bucket"},
            source_scope={"dataset_ids": [str(uuid.uuid4())]},
        )
        type(export).objects.filter(pk=export.pk).update(
            destination_config={
                "bucket": "dest-bucket",
                "access_key_id": _SECRET_KEY,
                "secret_access_key": _SECRET_VALUE,
            }
        )
        export = type(export).objects.get(pk=export.pk)

        request = _get("/", {"HTTP_X_INTERNAL_API_KEY": "test-key-123"})
        response = internal_pipeline_config(
            request,
            direction="export",
            resource_id=str(export.id),
        )
        assert response.status_code == 200, response.content
        body = json.loads(response.content)
        raw_body = json.dumps(body)
        assert _SECRET_VALUE not in raw_body
        assert _SECRET_KEY not in raw_body
        assert body["config"].get("secret_access_key") == f"{_SECRET_VALUE[:4]}***", (
            "the sibling-endpoint masking shape"
        )
        assert "credentials" not in body
