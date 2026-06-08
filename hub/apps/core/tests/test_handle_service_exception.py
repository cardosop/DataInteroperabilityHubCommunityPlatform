"""
Structured HTTP mapping for hub service-layer exceptions.

``handle_service_exception`` must preserve ``PermissionError`` codes and details —
marketplace publishes ``COMPLIANCE_FORCE_PUBLISH_DENIED`` plus listing context.
"""

import pytest

from django.test import SimpleTestCase
from rest_framework import status

from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    PermissionError,
)
from hub.apps.core.services.base import (
    ValidationError as ServiceValidationError,
)


class HandleServiceExceptionPermissionMapTest(SimpleTestCase):
    @pytest.mark.unit
    def test_permission_error_preserves_custom_code_and_details(self):
        msg = (
            "Only platform administrators may bypass "
            "the compliance gate (force_publish)."
        )
        exc = PermissionError(
            msg,
            code="COMPLIANCE_FORCE_PUBLISH_DENIED",
            details={"listing_id": "lst-1", "tenant_id": "ten-9"},
            http_status=403,
        )
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        payload = getattr(resp, "data", None)
        assert isinstance(payload, dict)
        self.assertEqual(payload["code"], "COMPLIANCE_FORCE_PUBLISH_DENIED")
        self.assertEqual(payload["details"]["listing_id"], "lst-1")
        self.assertEqual(payload["details"]["tenant_id"], "ten-9")
        self.assertIn("platform administrators", str(payload["detail"]))

    @pytest.mark.unit
    def test_permission_error_defaults_for_generic_denial(self):
        exc = PermissionError("Access denied")
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        payload = getattr(resp, "data", None)
        assert isinstance(payload, dict)
        self.assertEqual(payload["code"], "PERMISSION_DENIED")
        self.assertEqual(payload["details"], {})

    @pytest.mark.unit
    def test_not_found_error_maps_to_404(self):
        exc = NotFoundError("Asset not found", code="NOT_FOUND",
                            details={"resource_id": "123"})
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        payload = getattr(resp, "data", None)
        self.assertEqual(payload["code"], "NOT_FOUND")
        self.assertEqual(payload["details"]["resource_id"], "123")

    @pytest.mark.unit
    def test_validation_error_maps_to_400(self):
        exc = ServiceValidationError("Field X is required", code="VALIDATION_ERROR")
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        payload = getattr(resp, "data", None)
        self.assertEqual(payload["code"], "VALIDATION_ERROR")

    @pytest.mark.unit
    def test_conflict_error_maps_to_409(self):
        exc = ConflictError("Duplicate entry", code="CONFLICT_ERROR")
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        payload = getattr(resp, "data", None)
        self.assertEqual(payload["code"], "CONFLICT_ERROR")

    @pytest.mark.unit
    def test_unknown_exception_maps_to_500(self):
        exc = RuntimeError("Unexpected internal failure")
        resp = handle_service_exception(exc)
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        payload = getattr(resp, "data", None)
        self.assertEqual(payload["code"], "INTERNAL_ERROR")
