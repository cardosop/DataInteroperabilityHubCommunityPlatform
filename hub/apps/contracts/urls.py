"""
Contract URL Configuration
"""

from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from .views import ContractViewSet

# Create router - format suffixes are enabled by default in DefaultRouter
# This can cause conflicts with query parameters like ?format=dot
router = DefaultRouter()
router.register(r"contracts", ContractViewSet, basename="contract")


# Custom function-based view for lineage visualization that bypasses DRF format suffix routing
# This allows ?format=dot and ?format=mermaid query parameters to work without conflicts
# from DRF's format suffix patterns
#
# CRITICAL: The issue with as_view() is that DRF doesn't properly recognize detail=True actions
# when called directly. Instead, we manually instantiate the viewset and call the action method,
# ensuring proper initialization for detail actions with lookup_field='id'
def lineage_visualization_custom(request, id=None, *args, **kwargs):
    """
    Custom view for lineage visualization that bypasses DRF format suffix routing.

    This endpoint handles ?format=dot and ?format=mermaid query parameters without conflicts
    from DRF's format suffix patterns.

    Root cause fix: When using as_view() for detail=True actions, DRF doesn't properly
    initialize the viewset for detail action dispatch, causing get_object() to fail.
    Solution: Manually instantiate the viewset and ensure proper initialization for
    detail actions with lookup_field='id'.
    """
    # Import here to avoid circular imports
    from rest_framework.exceptions import NotFound

    from .views import ContractViewSet

    # Ensure 'id' is in kwargs (ContractViewSet uses lookup_field='id')
    # CRITICAL: The URL pattern uses 'id', but DRF's router might use 'pk' by default
    # We need to ensure 'id' is in kwargs for get_object() to work correctly
    if "id" not in kwargs:
        if id is not None:
            kwargs["id"] = id
        elif "pk" in kwargs:
            # Convert 'pk' to 'id' since ContractViewSet uses lookup_field='id'
            kwargs["id"] = kwargs.pop("pk")

    # Remove format from kwargs if present (from format suffix pattern)
    # This prevents DRF from trying to match format suffix patterns
    if "format" in kwargs:
        # Store format in request for the view method to use if needed
        # but remove from kwargs to prevent routing conflicts
        request._format_from_suffix = kwargs.pop("format")

    # CRITICAL: Manually instantiate viewset and initialize for detail action
    # Root cause: as_view() doesn't properly initialize detail actions when called directly
    # Solution: Manually instantiate and initialize the viewset with proper action context
    viewset = ContractViewSet()

    # CRITICAL: Set action_map before calling initialize_request
    # DRF's initialize_request expects action_map to be set for proper action dispatch
    # For detail=True actions, we need to map 'get' to the action name
    viewset.action_map = {"get": "get_lineage_visualization"}

    # Initialize the viewset with the request (this sets up authentication, permissions, etc.)
    # We need to call initialize_request to get a DRF request object
    # CRITICAL: Pass method='get' to initialize_request so it can determine the action from action_map
    drf_request = viewset.initialize_request(request, method="get")

    # CRITICAL: Ensure tenant_id and tenant are preserved from original request to DRF request
    # The middleware sets these on the Django request, but we need to ensure they're on the DRF request
    # This is essential for tenant filtering to work correctly
    if hasattr(request, "tenant_id") and request.tenant_id:
        drf_request.tenant_id = request.tenant_id
    if hasattr(request, "tenant") and request.tenant:
        drf_request.tenant = request.tenant

    # CRITICAL: Set up viewset for detail action BEFORE calling the action method
    # This ensures get_object() works correctly:
    # 1. viewset.request is set (for get_queryset() to filter by tenant)
    # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
    # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
    # 4. viewset.action is set (for proper viewset initialization)
    viewset.request = drf_request
    viewset.kwargs = kwargs
    viewset.format_kwarg = None  # Disable format suffix handling
    viewset.action = "get_lineage_visualization"  # Set action for proper dispatch
    viewset.lookup_url_kwarg = "id"  # Match lookup_field='id'

    # CRITICAL: Call check_permissions to ensure permissions are checked
    # This is normally done by DRF's action dispatch, but we're calling the action directly
    try:
        viewset.check_permissions(drf_request)
    except Exception:
        # If permission check fails, let it raise (don't catch and hide)
        raise

    # CRITICAL: Call the action method directly
    # The action method will call get_object() which will now work correctly because:
    # 1. viewset.request is set (for get_queryset() to filter by tenant)
    # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
    # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
    # 4. viewset.action is set (for proper viewset initialization)
    #
    # The action method returns a Response object, which Django will automatically render
    # We don't need to manually render it - Django's middleware handles that
    response = viewset.get_lineage_visualization(drf_request, id=kwargs.get("id"))

    # CRITICAL: Ensure response is properly finalized
    # DRF's Response objects need to have the renderer set for proper rendering
    # We use finalize_response to set up the renderer, but we need to ensure headers is set
    viewset.headers = {}
    try:
        response = viewset.finalize_response(drf_request, response, *args, **kwargs)
    except AttributeError:
        # If finalize_response fails (e.g., headers not set), just return the response
        # Django will handle rendering
        pass

    return response


urlpatterns = [
    # Custom visualization endpoint without format suffix patterns
    # This must come BEFORE the router URLs to take precedence
    # Use re_path with the exact same regex pattern as the router: ^contracts/(?P<id>[^/.]+)/lineage/visualization/$
    # This ensures our pattern matches before the router's format suffix patterns
    re_path(
        r"^contracts/(?P<id>[^/.]+)/lineage/visualization/$",
        lineage_visualization_custom,
        name="contract-lineage-visualization-custom",
    ),
    # Standard router URLs (includes all other actions with format suffixes)
    path("", include(router.urls)),
]
