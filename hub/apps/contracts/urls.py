"""
Contract URL Configuration
"""

from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from .views import ContractViewSet

# Create router - format suffixes are enabled by default in DefaultRouter
# This can cause conflicts with query parameters like ?format=dot
# Note: Router is registered with empty string since the 'contracts/' path
# is already included in hub/apps/api/urls.py
router = DefaultRouter()
router.register(r"", ContractViewSet, basename="contract")


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
    # Also, in tests, middleware might not run, so fall back to getting tenant_id from user
    if hasattr(request, "tenant_id") and request.tenant_id:
        drf_request.tenant_id = request.tenant_id
    elif hasattr(drf_request, "user") and drf_request.user and not drf_request.user.is_anonymous:
        # Fallback: get tenant_id from user (for tests where middleware doesn't run)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            db_user = User.objects.only("tenant_id").get(id=drf_request.user.id)
            if db_user.tenant_id:
                drf_request.tenant_id = str(db_user.tenant_id)
        except User.DoesNotExist:
            pass

    if hasattr(request, "tenant") and request.tenant:
        drf_request.tenant = request.tenant
    elif hasattr(drf_request, "tenant_id") and drf_request.tenant_id:
        # Fallback: get tenant object from tenant_id (for tests where middleware doesn't run)
        from hub.apps.tenants.models import Tenant
        try:
            drf_request.tenant = Tenant.objects.get(id=drf_request.tenant_id)
        except Tenant.DoesNotExist:
            pass

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


# Custom function-based view for export endpoint that bypasses DRF format suffix routing
# This allows ?format=hubcontract, ?format=odps, ?format=odcs query parameters to work without conflicts
# from DRF's format suffix patterns
def export_contract_custom(request, id=None, *args, **kwargs):
    """
    Custom view for export endpoint that bypasses DRF format suffix routing.

    This endpoint handles ?format=hubcontract, ?format=odps, ?format=odcs query parameters
    without conflicts from DRF's format suffix patterns.

    Root cause fix: When using as_view() for detail=True actions, DRF doesn't properly
    initialize the viewset for detail action dispatch, and format suffix handling interferes.
    Solution: Manually instantiate the viewset and ensure proper initialization for
    detail actions with lookup_field='id', and disable format_kwarg to prevent format suffix conflicts.
    """
    from rest_framework.exceptions import NotFound

    from .views import ContractViewSet

    # Ensure 'id' is in kwargs (ContractViewSet uses lookup_field='id')
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
    viewset.action_map = {"get": "export_contract"}

    # Initialize the viewset with the request (this sets up authentication, permissions, etc.)
    # We need to call initialize_request to get a DRF request object
    # CRITICAL: Pass method='get' to initialize_request so it can determine the action from action_map
    drf_request = viewset.initialize_request(request, method="get")

    # CRITICAL: Ensure tenant_id and tenant are preserved from original request to DRF request
    # The middleware sets these on the Django request, but we need to ensure they're on the DRF request
    # This is essential for tenant filtering to work correctly
    # Also, in tests, middleware might not run, so fall back to getting tenant_id from user
    if hasattr(request, "tenant_id") and request.tenant_id:
        drf_request.tenant_id = request.tenant_id
    elif hasattr(drf_request, "user") and drf_request.user and not drf_request.user.is_anonymous:
        # Fallback: get tenant_id from user (for tests where middleware doesn't run)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            db_user = User.objects.only("tenant_id").get(id=drf_request.user.id)
            if db_user.tenant_id:
                drf_request.tenant_id = str(db_user.tenant_id)
        except User.DoesNotExist:
            pass

    if hasattr(request, "tenant") and request.tenant:
        drf_request.tenant = request.tenant
    elif hasattr(drf_request, "tenant_id") and drf_request.tenant_id:
        # Fallback: get tenant object from tenant_id (for tests where middleware doesn't run)
        from hub.apps.tenants.models import Tenant
        try:
            drf_request.tenant = Tenant.objects.get(id=drf_request.tenant_id)
        except Tenant.DoesNotExist:
            pass

    # CRITICAL: Set up viewset for detail action BEFORE calling the action method
    # This ensures get_object() works correctly:
    # 1. viewset.request is set (for get_queryset() to filter by tenant)
    # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
    # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
    # 4. viewset.action is set (for proper viewset initialization)
    # 5. viewset.format_kwarg is set to None (prevents format suffix conflicts)
    viewset.request = drf_request
    viewset.kwargs = kwargs
    viewset.format_kwarg = None  # CRITICAL: Disable format suffix handling
    viewset.action = "export_contract"  # Set action for proper dispatch
    viewset.lookup_url_kwarg = "id"  # Match lookup_field='id'
    viewset.lookup_field = "id"  # CRITICAL: Also set lookup_field explicitly

    # CRITICAL: Call the action method and handle exceptions properly
    # We wrap the call to ensure DRF exceptions are handled correctly
    try:
        # Check permissions and throttling before calling the action
        # This ensures authentication errors are caught and handled properly
        viewset.check_permissions(drf_request)
        viewset.check_throttles(drf_request)

        # DEBUG: Verify setup before calling action (always log in test mode)
        import os
        import logging
        logger = logging.getLogger(__name__)
        contract_id = kwargs.get("id")

        # Always log in test environments (check multiple ways to detect test mode)
        is_test = (
            os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test") or
            "test" in os.environ.get("PYTEST_CURRENT_TEST", "") or
            "pytest" in str(os.environ.get("_", ""))
        )


        # Call the action method directly
        # The action method will call get_object() which will now work correctly because:
        # 1. viewset.request is set (for get_queryset() to filter by tenant)
        # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
        # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
        # 4. viewset.action is set (for proper viewset initialization)
        response = viewset.export_contract(drf_request, id=kwargs.get("id"))
    except Exception as e:
        # Handle DRF exceptions and Django Http404 using DRF's exception handler
        from django.http import Http404
        from rest_framework.exceptions import NotFound
        from rest_framework.views import exception_handler

        # Convert Django Http404 to DRF NotFound for proper handling
        # get_object() raises Http404 when object is not found
        if isinstance(e, Http404):
            # Convert to DRF NotFound exception
            e = NotFound(str(e) if str(e) else "Not found")

        # Create context for exception handler
        context = {
            'view': viewset,
            'args': args,
            'kwargs': kwargs,
            'request': drf_request,
        }

        # Get DRF's exception handler response
        exc_response = exception_handler(e, context)

        if exc_response is not None:
            # DRF handled the exception, finalize and return the response
            try:
                exc_response = viewset.finalize_response(drf_request, exc_response, *args, **kwargs)
            except (AttributeError, TypeError):
                pass
            return exc_response

        # If exception handler returns None, re-raise the exception
        # This will be handled by Django's exception middleware
        raise

    # CRITICAL: Ensure response is properly finalized
    # DRF's Response objects need to have the renderer set for proper rendering
    viewset.headers = {}
    try:
        response = viewset.finalize_response(drf_request, response, *args, **kwargs)
    except AttributeError:
        # If finalize_response fails (e.g., headers not set), just return the response
        # Django will handle rendering
        pass

    return response


# Custom function-based view for download endpoint that bypasses DRF format suffix routing
# This allows ?format=hubcontract, ?format=odps, ?format=odcs query parameters to work without conflicts
# from DRF's format suffix patterns
def download_contract_custom(request, id=None, *args, **kwargs):
    """
    Custom view for download endpoint that bypasses DRF format suffix routing.

    This endpoint handles ?format=hubcontract, ?format=odps, ?format=odcs query parameters
    without conflicts from DRF's format suffix patterns.

    Root cause fix: When using as_view() for detail=True actions, DRF doesn't properly
    initialize the viewset for detail action dispatch, and format suffix handling interferes.
    Solution: Manually instantiate the viewset and ensure proper initialization for
    detail actions with lookup_field='id', and disable format_kwarg to prevent format suffix conflicts.
    """
    from rest_framework.exceptions import NotFound
    from rest_framework.views import exception_handler

    from .views import ContractViewSet

    # Ensure 'id' is in kwargs (ContractViewSet uses lookup_field='id')
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
    viewset.action_map = {"get": "download_contract"}

    # Initialize the viewset with the request (this sets up authentication, permissions, etc.)
    # We need to call initialize_request to get a DRF request object
    # CRITICAL: Pass method='get' to initialize_request so it can determine the action from action_map
    drf_request = viewset.initialize_request(request, method="get")

    # CRITICAL: Ensure tenant_id and tenant are preserved from original request to DRF request
    # The middleware sets these on the Django request, but we need to ensure they're on the DRF request
    # This is essential for tenant filtering to work correctly
    # Also, in tests, middleware might not run, so fall back to getting tenant_id from user
    if hasattr(request, "tenant_id") and request.tenant_id:
        drf_request.tenant_id = request.tenant_id
    elif hasattr(drf_request, "user") and drf_request.user and not drf_request.user.is_anonymous:
        # Fallback: get tenant_id from user (for tests where middleware doesn't run)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            db_user = User.objects.only("tenant_id").get(id=drf_request.user.id)
            if db_user.tenant_id:
                drf_request.tenant_id = str(db_user.tenant_id)
        except User.DoesNotExist:
            pass

    if hasattr(request, "tenant") and request.tenant:
        drf_request.tenant = request.tenant
    elif hasattr(drf_request, "tenant_id") and drf_request.tenant_id:
        # Fallback: get tenant object from tenant_id (for tests where middleware doesn't run)
        from hub.apps.tenants.models import Tenant
        try:
            drf_request.tenant = Tenant.objects.get(id=drf_request.tenant_id)
        except Tenant.DoesNotExist:
            pass

    # CRITICAL: Set up viewset for detail action BEFORE calling the action method
    # This ensures get_object() works correctly:
    # 1. viewset.request is set (for get_queryset() to filter by tenant)
    # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
    # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
    # 4. viewset.action is set (for proper viewset initialization)
    # 5. viewset.format_kwarg is set to None (prevents format suffix conflicts)
    viewset.request = drf_request
    viewset.kwargs = kwargs
    viewset.format_kwarg = None  # CRITICAL: Disable format suffix handling
    viewset.action = "download_contract"  # Set action for proper dispatch
    viewset.lookup_url_kwarg = "id"  # Match lookup_field='id'
    viewset.lookup_field = "id"  # CRITICAL: Also set lookup_field explicitly

    # CRITICAL: Call the action method and handle exceptions properly
    # We wrap the call to ensure DRF exceptions are handled correctly
    try:
        # Check permissions and throttling before calling the action
        # This ensures authentication errors are caught and handled properly
        viewset.check_permissions(drf_request)
        viewset.check_throttles(drf_request)

        # Call the action method directly
        # The action method will call get_object() which will now work correctly because:
        # 1. viewset.request is set (for get_queryset() to filter by tenant)
        # 2. viewset.kwargs contains 'id' (for get_object() to find the contract)
        # 3. viewset.lookup_url_kwarg is set to 'id' (matches lookup_field='id')
        # 4. viewset.action is set (for proper viewset initialization)
        response = viewset.download_contract(drf_request, id=kwargs.get("id"))
    except Exception as e:
        # Handle DRF exceptions and Django Http404 using DRF's exception handler
        from django.http import Http404

        # Convert Django Http404 to DRF NotFound for proper handling
        # get_object() raises Http404 when object is not found
        if isinstance(e, Http404):
            # Convert to DRF NotFound exception
            e = NotFound(str(e) if str(e) else "Not found")

        # Create context for exception handler
        context = {
            'view': viewset,
            'args': args,
            'kwargs': kwargs,
            'request': drf_request,
        }

        # Get DRF's exception handler response
        exc_response = exception_handler(e, context)

        if exc_response is not None:
            # DRF handled the exception, finalize and return the response
            try:
                exc_response = viewset.finalize_response(drf_request, exc_response, *args, **kwargs)
            except (AttributeError, TypeError):
                pass
            return exc_response

        # If exception handler returns None, re-raise the exception
        # This will be handled by Django's exception middleware
        raise

    # CRITICAL: Ensure response is properly finalized
    # DRF's Response objects need to have the renderer set for proper rendering
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
    re_path(
        r"^contracts/(?P<id>[^/.]+)/lineage/visualization/$",
        lineage_visualization_custom,
        name="contract-lineage-visualization-custom",
    ),
    # Custom export endpoint without format suffix patterns
    # This must come BEFORE the router URLs to take precedence
    # Note: Pattern is ^(?P<id>...) not ^contracts/(?P<id>...) because this app is already mounted at /api/v1/contracts/
    re_path(
        r"^(?P<id>[^/.]+)/export/$",
        export_contract_custom,
        name="contract-export-custom",
    ),
    # Custom download endpoint without format suffix patterns
    # This must come BEFORE the router URLs to take precedence
    # Note: Pattern is ^(?P<id>...) not ^contracts/(?P<id>...) because this app is already mounted at /api/v1/contracts/
    re_path(
        r"^(?P<id>[^/.]+)/download/$",
        download_contract_custom,
        name="contract-download-custom",
    ),
    # Standard router URLs (includes all other actions with format suffixes)
    path("", include(router.urls)),
]
