"""
Tenant Middleware

Enforces tenant suspension read-only behavior and tenant isolation.
Also checks subscription status (Phase 25.2.4).
"""

from django.http import HttpResponseForbidden, JsonResponse

from .models import Tenant, TenantStatus


class TenantSuspensionMiddleware:
    """
    Middleware to enforce read-only mode for suspended tenants.

    Blocks write operations (POST, PUT, PATCH, DELETE) for suspended tenants.
    Allows read operations (GET, HEAD, OPTIONS).
    """

    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and return response."""
        # Handle DRF's force_authenticate in test environments
        # force_authenticate sets _force_auth_user before authentication classes run
        # We need to set request.user here so our middleware can access it
        if not hasattr(request, "user") or not request.user or not request.user.is_authenticated:
            forced_user = getattr(request, "_force_auth_user", None)
            if forced_user is not None:
                request.user = forced_user

        # Process request (may return early response)
        response = self.process_request(request)
        if response is not None:
            return response

        # Get response
        response = self.get_response(request)

        # Process response (if needed in future)
        return response

    # HTTP methods that are considered write operations
    WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

    # Endpoints that are always allowed (health checks, auth, etc.)
    # Auth endpoints must work without subscription: login, logout, sessions (list/revoke),
    # api-keys, password-reset, etc. Session list/revoke and logout must work so users can
    # manage sessions and sign out regardless of billing state.
    ALLOWED_PATHS = [
        "/health/",
        "/api/health/",
        "/api/v1/auth/",
    ]

    def process_request(self, request):
        """Check if tenant is suspended and block writes"""
        # Skip if path is in allowed list
        if any(request.path.startswith(path) for path in self.ALLOWED_PATHS):
            return None

        # Get tenant_id to fetch fresh tenant from database
        # We always fetch from DB to avoid cached objects with stale status
        tenant_id = None

        # Try multiple sources for tenant_id, in order of preference
        # 1. Check request.tenant_id (set by authentication or TenantScopingMiddleware)
        if hasattr(request, "tenant_id") and request.tenant_id:
            tenant_id = request.tenant_id

        # 2. Check request.tenant (set by TenantScopingMiddleware)
        if tenant_id is None and hasattr(request, "tenant") and request.tenant:
            tenant_id = request.tenant.id
            # Set request.tenant_id for consistency
            if tenant_id:
                request.tenant_id = tenant_id

        # 3. Check request.user and query from database
        # This is the most reliable source in test environments
        # Note: DRF's force_authenticate may set request._force_auth_user instead of request.user
        # Check both locations for test compatibility
        user = getattr(request, "user", None)
        if user is None:
            # DRF's force_authenticate might set _force_auth_user
            user = getattr(request, "_force_auth_user", None)

        if tenant_id is None and user:
            # Check if user is authenticated (works with both force_authenticate and JWT)
            from django.contrib.auth.models import AnonymousUser

            is_anonymous = isinstance(user, AnonymousUser)

            # User is considered authenticated if not AnonymousUser and has an id
            # In test environments, force_authenticate sets user but is_authenticated might not be evaluated
            # So we check both is_authenticated and if user has an ID
            is_authenticated = not is_anonymous and (
                getattr(user, "is_authenticated", False)
                or (hasattr(user, "id") and user.id is not None)
            )

            if is_authenticated:
                # Ensure request.user is set for consistency
                if not hasattr(request, "user") or request.user != user:
                    request.user = user
                # Get tenant_id by querying user from database to avoid cached relationship issues
                # This ensures we get the actual tenant_id from the database, not from a cached object
                tenant_id_set = False
                try:
                    from django.contrib.auth import get_user_model

                    User = get_user_model()
                    # Query user from database to get fresh tenant_id
                    db_user = User.objects.only("tenant_id").get(id=user.id)
                    tenant_id = db_user.tenant_id
                    # Set request.tenant_id and request.tenant for consistency
                    if tenant_id:
                        request.tenant_id = tenant_id
                        tenant_id_set = True
                        # Also set request.tenant if not already set
                        if not hasattr(request, "tenant") or not request.tenant:
                            try:
                                request.tenant = Tenant.objects.get(id=tenant_id)
                            except Tenant.DoesNotExist:
                                pass
                except User.DoesNotExist:
                    # User doesn't exist in database - can't get tenant_id, try fallback
                    pass
                except Exception as e:
                    # Log the exception for debugging but continue with fallback
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error querying user for tenant_id: {e}", exc_info=True)

                # Fallback: if DB query didn't set tenant_id, try user object directly
                # This is important for test environments where transaction isolation might prevent DB queries
                if not tenant_id_set:
                    fallback_tenant_id = getattr(user, "tenant_id", None)
                    if fallback_tenant_id:
                        tenant_id = fallback_tenant_id
                        request.tenant_id = tenant_id
                        tenant_id_set = True
                        # Try to get tenant object
                        if not hasattr(request, "tenant") or not request.tenant:
                            try:
                                request.tenant = Tenant.objects.get(id=tenant_id)
                            except Tenant.DoesNotExist:
                                pass
                    elif hasattr(user, "tenant") and user.tenant:
                        tenant_id = user.tenant.id
                        request.tenant_id = tenant_id
                        tenant_id_set = True
                        request.tenant = user.tenant

        # 3. Last resort: try to get it from request.tenant
        if tenant_id is None:
            tenant = getattr(request, "tenant", None)
            if tenant:
                tenant_id = tenant.id

        # Always fetch tenant directly from database to get latest status
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                # Update request.tenant with fresh object
                request.tenant = tenant
            except Tenant.DoesNotExist:
                return None  # No tenant found, let other middleware handle
        else:
            return None  # No tenant context, let other middleware handle

        # Check if tenant is suspended (we already have fresh object from DB)
        # Double-check status by refreshing from DB (defensive programming)
        tenant.refresh_from_db()
        if tenant.status == TenantStatus.SUSPENDED:
            # Block write operations
            if request.method in self.WRITE_METHODS:
                return JsonResponse(
                    {
                        "error": "Tenant is suspended. Write operations are not allowed.",
                        "code": "tenant_suspended",
                    },
                    status=403,
                )

        # Block all operations for deleted tenants
        elif tenant.status == TenantStatus.DELETED:
            return JsonResponse({"error": "Tenant is deleted. All access is blocked."}, status=403)

        # Check subscription status (Phase 25.2.4)
        # Block write operations if no subscription or subscription is inactive
        if request.method in self.WRITE_METHODS:
            try:
                from hub.apps.billing.models import Subscription, SubscriptionStatus

                subscription = (
                    Subscription.objects.filter(tenant_id=tenant_id).order_by("-created_at").first()
                )

                if not subscription:
                    return JsonResponse(
                        {
                            "error": "No active subscription",
                            "code": "subscription_inactive",
                            "details": {"tenant_id": str(tenant_id)},
                        },
                        status=403,
                    )

                if subscription.status in [
                    SubscriptionStatus.PAST_DUE,
                    SubscriptionStatus.UNPAID,
                    SubscriptionStatus.CANCELED,
                    SubscriptionStatus.INCOMPLETE,
                    SubscriptionStatus.INCOMPLETE_EXPIRED,
                ]:
                    return JsonResponse(
                        {
                            "error": "Subscription is inactive. Write operations are not allowed.",
                            "code": "subscription_inactive",
                            "details": {
                                "subscription_id": str(subscription.id),
                                "status": subscription.status,
                            },
                        },
                        status=403,
                    )
            except Exception:
                # Don't block on subscription check errors - allow request to proceed
                pass

        return None
