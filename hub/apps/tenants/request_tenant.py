"""
Current tenant for request (Phase 16 — Tenant isolation).

Single contract for multi-tenant views: use get_request_tenant_id(request) or
get_request_tenant(request) for filtering. Middleware (TenantScopingMiddleware)
sets request.tenant_id and request.tenant; this helper provides the same
fallback order when called from views so filtering is consistent.

Fallback order (standardized):
  1. request.tenant_id (set by TenantScopingMiddleware / auth)
  2. request.tenant.id (set by TenantScopingMiddleware)
  3. request.user from DB: User.objects.only('tenant_id').get(id=user.id)
  4. request.user.tenant_id
  5. request.user.tenant.id

All multi-tenant list/detail views MUST filter by this tenant; see docs/TENANT_ISOLATION.md.
"""
from typing import Optional, Tuple

from django.http import HttpRequest


def get_request_tenant_id(request: HttpRequest) -> Optional[str]:
    """
    Get current tenant ID for the request (Phase 16 contract).

    Use this for tenant-scoped filtering in list/detail views. Same fallback
    order as TenantScopingMiddleware so request.tenant_id/request.tenant are
    the source of truth when set; otherwise we resolve from request.user.

    Args:
        request: Django request (may have tenant_id, tenant, user set).

    Returns:
        Tenant ID as string, or None if no tenant context.
    """
    # 1. request.tenant_id (set by middleware/authentication)
    if hasattr(request, "tenant_id") and request.tenant_id:
        tid = request.tenant_id
        return str(tid) if tid else None

    # 2. request.tenant (set by TenantScopingMiddleware)
    if hasattr(request, "tenant") and request.tenant:
        return str(request.tenant.id)

    # 3–5. From request.user (session auth / force_authenticate)
    user = getattr(request, "user", None) or getattr(request, "_force_auth_user", None)
    if not user:
        return None

    from django.contrib.auth.models import AnonymousUser

    if isinstance(user, AnonymousUser):
        return None
    if not getattr(user, "is_authenticated", False) and not getattr(user, "id", None):
        return None

    # 3. Fresh from DB (thread-safe, works in tests)
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        db_user = User.objects.only("tenant_id").get(id=user.id)
        if db_user.tenant_id:
            return str(db_user.tenant_id)
    except (User.DoesNotExist, Exception):
        pass

    # 4. user.tenant_id
    if hasattr(user, "tenant_id") and user.tenant_id:
        return str(user.tenant_id)

    # 5. user.tenant
    if hasattr(user, "tenant") and user.tenant:
        return str(user.tenant.id)

    return None


def get_request_tenant(request: HttpRequest) -> Tuple[Optional[str], Optional["Tenant"]]:
    """
    Get current tenant instance for the request (Phase 16 contract).

    Returns (tenant_id_str, tenant) or (None, None). Prefer get_request_tenant_id
    for filtering when only the ID is needed.

    Args:
        request: Django request.

    Returns:
        Tuple of (tenant_id as str or None, Tenant instance or None).
    """
    from hub.apps.tenants.models import Tenant

    tenant_id_str = get_request_tenant_id(request)
    if not tenant_id_str:
        return None, None

    # Optionally set request.tenant_id/request.tenant for consistency if not set
    if not hasattr(request, "tenant_id") or not request.tenant_id:
        request.tenant_id = tenant_id_str
    try:
        tenant = Tenant.objects.get(id=tenant_id_str)
        if not hasattr(request, "tenant") or not request.tenant:
            request.tenant = tenant
        return tenant_id_str, tenant
    except Tenant.DoesNotExist:
        return tenant_id_str, None
