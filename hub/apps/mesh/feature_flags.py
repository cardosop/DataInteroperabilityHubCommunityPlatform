"""
285.5.2.2 — Data Mesh feature-flag gate mixin.

Gates the Data Mesh Domain ViewSet on ``Tenant.data_mesh_enabled``.
"""
from __future__ import annotations

from rest_framework.response import Response

from hub.apps.tenants.feature_flag_gates import check_data_mesh_enabled


class _DataMeshFlagDeniedException(Exception):
    def __init__(self, response: Response):
        self.response = response


class DataMeshFeatureFlagMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        result = check_data_mesh_enabled(request)
        if isinstance(result, Response):
            raise _DataMeshFlagDeniedException(result)

    def handle_exception(self, exc):
        if isinstance(exc, _DataMeshFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
