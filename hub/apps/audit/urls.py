"""
Audit URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuditEventViewSet,
    AuditEventRetentionPolicyViewSet,
    AuditIntegrityVerifyView,
    ResourceActivityViewSet,
)

# Create router without format suffix patterns for export action
# This allows ?format=csv to work without routing conflicts
router = DefaultRouter()
router.register(r"audit-events", AuditEventViewSet, basename="audit-event")
# Phase 225.3.2 — separate top-level viewset for the per-resource activity
# feed. Kept next to the raw audit log so the tenant-scope middleware chain
# matches; access control is enforced in-viewset by user_is_involved().
router.register(
    r"resource-activity",
    ResourceActivityViewSet,
    basename="resource-activity",
)
# Phase 234.5 — per-event-type retention policy CRUD.
router.register(
    r"event-retention-policies",
    AuditEventRetentionPolicyViewSet,
    basename="audit-event-retention-policy",
)

# Phase 234.1.8 — integrity verify endpoint.
integrity_verify_view = AuditIntegrityVerifyView.as_view({"get": "list"})

# Add custom export endpoint that bypasses DRF format suffix routing
# This allows ?format=csv query parameter to work without conflicts
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

def export_audit_events_custom(request, *args, **kwargs):
    """
    Custom export endpoint that bypasses DRF format suffix routing.
    
    This endpoint handles ?format=csv query parameter without conflicts
    from DRF's format suffix patterns.
    
    Uses the viewset's as_view() to ensure proper authentication and permissions.
    The key is that this function receives the request and passes it to the viewset view,
    which will handle authentication via DRF's authentication classes.
    """
    # Import here to avoid circular imports
    from .views import AuditEventViewSet
    
    # Use the viewset's as_view() method to create a proper view
    # This ensures authentication, permissions, and all DRF machinery works correctly
    # The export action already handles ?format=csv correctly by prioritizing query params
    # We create the view once and reuse it (DRF views are callable and handle this correctly)
    if not hasattr(export_audit_events_custom, '_view'):
        export_audit_events_custom._view = AuditEventViewSet.as_view({'get': 'export'})
    
    # Call the view - this will properly handle authentication via DRF's authentication classes
    # Pass *args and **kwargs to ensure URL parameters are handled correctly
    return export_audit_events_custom._view(request, *args, **kwargs)

urlpatterns = [
    # Standard router URLs (includes export action)
    # The export action in the viewset already handles ?format=csv correctly
    path("", include(router.urls)),
    # Phase 234.1.8 — GET /api/v1/audit/integrity/verify
    path(
        "integrity/verify/",
        integrity_verify_view,
        name="audit-integrity-verify",
    ),
]

