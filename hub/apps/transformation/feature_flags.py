"""
285.9.1.0.1 — Transformation feature-flag gate mixin.

Follows the DQFeatureFlagMixin pattern from hub/apps/dq/feature_flags.py:
gates an entire ViewSet on Tenant.transformation_enabled.

Usage:
    class TransformationPipelineViewSet(TransformationFeatureFlagMixin, viewsets.ModelViewSet):
        ...
"""

from __future__ import annotations

from rest_framework.response import Response

from hub.apps.tenants.feature_flag_gates import check_transformation_enabled

ERR_TRANSFORMATION_DISABLED = "TRANSFORMATION_DISABLED"


class _TransformationFlagDeniedException(Exception):
    """Sentinel so handle_exception can return the canonical 403 shape
    without going through the global custom_exception_handler."""

    def __init__(self, response: Response):
        self.response = response


class TransformationFeatureFlagMixin:
    """Drop-in mixin that gates a ViewSet on transformation_enabled.

    Fires from initial() AFTER DRF auth/permission/throttle checks.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        result = check_transformation_enabled(request)
        if isinstance(result, Response):
            raise _TransformationFlagDeniedException(result)

    def handle_exception(self, exc):
        if isinstance(exc, _TransformationFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
