"""
285.6.2 — Data Movement public views.

Tenant-scoped CRUD for DataMovementConfig. Worker API at internal_views.py.
"""

from rest_framework import permissions, viewsets
from rest_framework.exceptions import NotFound

from hub.apps.tenants.request_tenant import get_request_tenant_id

from .models import DataMovementConfig
from .serializers import DataMovementConfigSerializer


class DataMovementConfigViewSet(viewsets.ModelViewSet):
    """Tenant-scoped data movement configuration."""

    # W12.9: previously unset — any request raised AssertionError from
    # get_serializer_class() (500) and drf-spectacular could not introspect
    # the view.  The serializer is the root fix for both.
    serializer_class = DataMovementConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    # throttle_classes = [DataMovementThrottle]  # added after app registration

    def get_queryset(self):
        tenant_id = get_request_tenant_id(self.request)
        if not tenant_id:
            return DataMovementConfig.objects.none()
        return DataMovementConfig.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        tenant_id = get_request_tenant_id(self.request)
        if not tenant_id:
            raise NotFound("Tenant not found")
        serializer.save(tenant_id=tenant_id)
