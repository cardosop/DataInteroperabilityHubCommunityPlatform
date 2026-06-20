"""
Documentation integrity tests.

Verifies that documentation files referenced by error codes exist and
contain expected content for ops reference.
"""

from __future__ import annotations

import os

from django.conf import settings
from django.test import TestCase


class ErrorCodeDocumentationTests(TestCase):
    """Verify error codes documentation is complete."""

    def test_error_codes_doc_exists(self):
        """The error codes documentation is available for ops reference."""
        doc_path = os.path.join(
            settings.BASE_DIR,
            "docs",
            "api",
            "error-codes.md",
        )
        assert os.path.exists(doc_path), (
            "docs/api/error-codes.md not found — error codes need documentation"
        )

    def test_503_error_documented(self):
        """503 Service Unavailable is documented in error codes."""
        doc_path = os.path.join(
            settings.BASE_DIR,
            "docs",
            "api",
            "error-codes.md",
        )
        if os.path.exists(doc_path):
            with open(doc_path) as f:
                content = f.read()
            assert "503" in content, "503 error code not documented in error-codes.md"
