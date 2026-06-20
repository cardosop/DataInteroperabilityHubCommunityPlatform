"""
Frontend component file-presence tests.

Verifies that critical frontend components exist on disk and contain
the expected props and test-ids for E2E test targeting.
"""

from __future__ import annotations

import os

from django.conf import settings
from django.test import TestCase


class ServiceDegradedBannerTests(TestCase):
    """Verify the frontend ServiceDegradedBanner component exists."""

    def test_banner_component_exists(self):
        """ServiceDegradedBanner component file is present."""
        banner_path = os.path.join(
            settings.BASE_DIR,
            "frontend",
            "src",
            "shared",
            "components",
            "ServiceDegradedBanner.tsx",
        )
        assert os.path.exists(banner_path), (
            "ServiceDegradedBanner.tsx not found — frontend missing degraded-service UI"
        )

    def _banner_path(self):
        return os.path.join(
            settings.BASE_DIR,
            "frontend",
            "src",
            "shared",
            "components",
            "ServiceDegradedBanner.tsx",
        )

    def test_banner_has_test_id(self):
        """The banner has a data-testid for E2E test targeting."""
        banner_path = self._banner_path()
        # File existence is verified by test_banner_component_exists;
        # content tests fail explicitly rather than silently skipping.
        with open(banner_path) as f:
            content = f.read()
        assert "data-testid" in content, "ServiceDegradedBanner missing data-testid"

    def test_banner_accepts_service_name_prop(self):
        """The banner accepts a serviceName prop for per-service messaging."""
        banner_path = self._banner_path()
        with open(banner_path) as f:
            content = f.read()
        assert "serviceName" in content, "ServiceDegradedBanner missing serviceName prop"
