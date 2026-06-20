"""285.14.3.6 — Verify scheduled_export throttle coverage on all views."""

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class ScheduledExportThrottleCoverageTests(TestCase):
    def setUp(self):
        from hub.apps.scheduled_export.views import (
            ScheduledExportRunViewSet,
            ScheduledExportViewSet,
        )

        self.views = [
            ScheduledExportViewSet,
            ScheduledExportRunViewSet,
        ]

    @pytest.mark.integration
    def test_all_views_have_throttle_classes(self):
        for view_cls in self.views:
            classes = getattr(view_cls, "throttle_classes", None)
            assert classes is not None, f"{view_cls.__name__} missing throttle_classes"
            assert len(classes) >= 1, f"{view_cls.__name__} has empty throttle_classes"

    @pytest.mark.integration
    def test_throttle_has_scope(self):
        from hub.apps.scheduled_export.throttles import (
            ScheduledExportTenantThrottle,
        )

        assert hasattr(ScheduledExportTenantThrottle, "scope")
        assert ScheduledExportTenantThrottle.scope == "scheduled_export"

    @pytest.mark.integration
    def test_throttle_has_tenant_aware_cache_key(self):
        from unittest.mock import MagicMock

        from hub.apps.scheduled_export.throttles import (
            ScheduledExportTenantThrottle,
        )

        throttle = ScheduledExportTenantThrottle()
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        # get_request_tenant_id checks request.tenant_id first (step 1),
        # then request.tenant (step 2).  Explicitly set tenant_id to None
        # so it falls through to step 2 where request.tenant.id is used.
        mock_request.tenant_id = None
        mock_request.tenant = MagicMock()
        mock_request.tenant.id = "00000000-0000-0000-0000-000000000001"

        mock_view = MagicMock()

        cache_key = throttle.get_cache_key(mock_request, mock_view)
        self.assertIsNotNone(cache_key)
        self.assertIn("00000000-0000-0000-0000-000000000001", cache_key)
        self.assertIn("scheduled_export", cache_key)
