"""
285.5.2.4 — Developer portal feature-flag gate mixin.

Gates the Developer Plugin ViewSet on ``Tenant.developer_enabled``.
"""

from __future__ import annotations

from rest_framework.response import Response

from hub.apps.tenants.feature_flag_gates import check_developer_enabled


class _DeveloperFlagDeniedException(Exception):
    def __init__(self, response: Response):
        self.response = response


class DeveloperFeatureFlagMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        result = check_developer_enabled(request)
        if isinstance(result, Response):
            raise _DeveloperFlagDeniedException(result)

    def handle_exception(self, exc):
        if isinstance(exc, _DeveloperFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
