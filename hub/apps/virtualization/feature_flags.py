"""
285.5.2.3 — Virtualization feature-flag gate mixin.

Gates the Virtual Dataset ViewSet on ``Tenant.virtualization_enabled``.
"""
from __future__ import annotations

from rest_framework.response import Response

from hub.apps.tenants.feature_flag_gates import check_virtualization_enabled


class _VirtualizationFlagDeniedException(Exception):
    def __init__(self, response: Response):
        self.response = response


class VirtualizationFeatureFlagMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        result = check_virtualization_enabled(request)
        if isinstance(result, Response):
            raise _VirtualizationFlagDeniedException(result)

    def handle_exception(self, exc):
        if isinstance(exc, _VirtualizationFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
