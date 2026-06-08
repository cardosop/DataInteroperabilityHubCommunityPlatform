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

    This function is intentionally read-only: it does NOT mutate request.tenant_id
    or request.tenant.  Mutating request attributes in a GET handler constitutes
    a persistent side-effect on the session-scoped user object, which can leak
    tenant context across request boundaries in long-lived worker threads.
    TenantScopingMiddleware is the sole place that may set these attributes.

    Args:
        request: Django request.

    Returns:
        Tuple of (tenant_id as str or None, Tenant instance or None).
    """
    from hub.apps.tenants.models import Tenant

    tenant_id_str = get_request_tenant_id(request)
    if not tenant_id_str:
        return None, None

    try:
        tenant = Tenant.objects.get(id=tenant_id_str)
        return tenant_id_str, tenant
    except Tenant.DoesNotExist:
        return tenant_id_str, None


class tenant_context:
    """
    Context manager that activates a tenant scope for the current
    database session by setting the PostgreSQL ``app.current_tenant_id``
    run-time parameter.

    Usage::

        with tenant_context(tenant_id):
            # All RLS policies that reference current_setting('app.current_tenant_id')
            # will now see *tenant_id* for the duration of this block.
            do_tenant_scoped_work()

    This is the canonical way for worker/signal code that touches
    tenant-scoped models to ensure RLS policies are enforced correctly
    outside of an HTTP request cycle (where the middleware would
    normally set this).
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)
        self._previous = None

    def __enter__(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_setting('app.current_tenant_id', true)"
            )
            row = cursor.fetchone()
            self._previous = row[0] if row and row[0] else None
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                [self.tenant_id],
            )

    def __exit__(self, exc_type, exc_val, exc_tb):
        from django.db import connection
        with connection.cursor() as cursor:
            if self._previous:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    [self._previous],
                )
            else:
                # Reset the GUC by setting it to NULL (rather than '').
                # NULL matches the semantics of ``SET LOCAL ... = DEFAULT``
                # used by the test helper ``set_tenant_context``
                # (hub/apps/core/tests/test_utils/rls_helpers.py): when no
                # previous tenant context existed, clear the setting so
                # ``current_setting('app.current_tenant_id', true)``
                # returns NULL.
                #
                # We use ``set_config(..., true)`` (is_local) so this works
                # without a wrapping transaction.atomic() block — the
                # setting is transaction-local and reverts after the
                # current (possibly implicit) transaction ends, which
                # matches the documented contract that this context
                # manager is scoped to the caller's transaction.
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', NULL, true)"
                )
        return False  # do not suppress exceptions


def with_tenant_context(tenant_id):
    """Decorator that wraps a function to run inside ``tenant_context(tenant_id)``.

    The GUC (``app.current_tenant_id``) is saved before entering and
    restored after exiting, even if the decorated function raises an
    exception.

    Usage::

        @with_tenant_context(my_tenant_id)
        def do_tenant_scoped_work():
            # All DB queries here are scoped to my_tenant_id via RLS.
            return MyModel.objects.count()
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tenant_context(tenant_id):
                return func(*args, **kwargs)
        return wrapper
    return decorator
