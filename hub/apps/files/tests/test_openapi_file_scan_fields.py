"""
Phase 260.2.C — OpenAPI ``File`` schema exposes malware scan fields (D260.7).

Regression test: CI / ``spectacular`` output must keep ``scan_status`` and
``scanned_at`` on the default File serializer so the contract stays aligned
with the UI and ``docs/api/openapi-baseline.json``.
"""

import pytest

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from drf_spectacular.generators import SchemaGenerator


class FileOpenAPIScanFieldsTest(SimpleTestCase):
    """No DB: schema generation only."""

    @pytest.mark.unit
    def test_file_component_includes_scan_status_and_scanned_at(self):
        factory = RequestFactory()
        request = factory.get("/api/v1/")
        request.user = AnonymousUser()
        setattr(request, "auth", None)

        generator = SchemaGenerator(urlconf="hub.urls")
        schema = generator.get_schema(request=request, public=True)
        props = schema["components"]["schemas"]["File"]["properties"]

        self.assertIn("scan_status", props)
        self.assertIn("scanned_at", props)
        self.assertTrue(props["scan_status"].get("readOnly"))
        self.assertTrue(props["scanned_at"].get("readOnly"))

        enum_vals = set(props["scan_status"]["enum"])
        self.assertEqual(
            enum_vals,
            {
                "PENDING_SCAN",
                "CLEAN",
                "INFECTED",
                "SCAN_UNAVAILABLE",
                "SCAN_ERROR",
            },
        )

    @pytest.mark.unit
    def test_patched_file_includes_read_only_scan_fields(self):
        factory = RequestFactory()
        request = factory.get("/api/v1/")
        request.user = AnonymousUser()
        setattr(request, "auth", None)
        generator = SchemaGenerator(urlconf="hub.urls")
        schema = generator.get_schema(request=request, public=True)
        props = schema["components"]["schemas"]["PatchedFile"]["properties"]
        self.assertIn("scan_status", props)
        self.assertIn("scanned_at", props)
