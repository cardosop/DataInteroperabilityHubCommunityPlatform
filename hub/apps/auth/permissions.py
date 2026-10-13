"""
Role-based Authorization Permissions

Custom permission classes for role-based access control.
"""

from django.conf import settings
from django.db import DatabaseError, InterfaceError, OperationalError
from rest_framework import permissions

# W6.5 (S1) — the scope vocabulary moved to hub/apps/auth/scopes.py, a
# Django-free single source the SDK/CLI/JS contract test imports
# directly.  Re-exported here so every existing importer
# (``from hub.apps.auth.permissions import ROLE_SCOPE_MAP``, the
# scheduled_ingestion internal scope) keeps working unchanged.
from hub.apps.auth.scopes import (
    ROLE_SCOPE_MAP,
    SCOPE_SCHEDULED_INGESTION_INTERNAL,
    WILDCARD_SCOPE,
)


def disallowed_mint_scopes(requested: list, allowed: frozenset[str]) -> list[str]:
    """R2-B2 (W1.3a) — the scopes from ``requested`` the requester may NOT
    mint an API key with, given their role allowlist ``allowed``.

    Rules:
    * ``scheduled_ingestion:internal`` is never mintable via the public
      API — no role grants it and no wildcard covers it (the internal
      provisioning path is separate).
    * ``"*"`` requires the PLATFORM_ADMIN allowlist (the only role whose
      ``ROLE_SCOPE_MAP`` entry contains it).
    * every other scope must be in ``allowed``; ``"*"`` in ``allowed``
      covers everything EXCEPT the internal scope.
    """
    disallowed: list[str] = []
    for scope in requested:
        if scope == SCOPE_SCHEDULED_INGESTION_INTERNAL:
            disallowed.append(scope)
        elif scope == WILDCARD_SCOPE:
            if WILDCARD_SCOPE not in allowed:
                disallowed.append(scope)
        elif WILDCARD_SCOPE not in allowed and scope not in allowed:
            disallowed.append(scope)
    return disallowed


def _get_user_scopes(request) -> frozenset[str]:
    """Resolve effective scopes for a request from roles or API key."""
    # Use getattr(..., None) rather than hasattr() so the check is
    # MagicMock-safe: MagicMock.__getattr__ auto-creates attributes on
    # every getattr/hasattr call, making ``hasattr(mock, 'attr')``
    # always True.  ``getattr(x, 'attr', None)`` returns None when the
    # attribute genuinely doesn't exist on a real HttpRequest, and
    # returns the MagicMock (truthy) when it was never set — a callable
    # mock is not None either, so the fix is in the test helper
    # (_mock_request) which explicitly sets ``api_key_scopes = None``.
    if getattr(request, "api_key_scopes", None) is not None:
        return frozenset(request.api_key_scopes)

    if not hasattr(request, "user") or not request.user or not request.user.is_authenticated:
        return frozenset()

    if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
        return frozenset({WILDCARD_SCOPE})

    # Collect scopes from user roles
    role_names = set()
    if hasattr(request, "_roles") and request._roles:
        # Test shortcut: roles passed directly on request
        role_names = set(request._roles)
    else:
        try:
            from hub.apps.users.models import UserRole

            role_names = set(
                UserRole.objects.filter(user_id=request.user.id).values_list(
                    "role__name", flat=True
                )
            )
        except (DatabaseError, InterfaceError, OperationalError):
            # Never silently swallow — a transient DB error (e.g. connection
            # closed after a long-running request) would strip all scopes and
            # cause spurious 403s.  Log the failure and close the stale
            # connection so the next attempt gets a fresh one.
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Failed to resolve user scopes from UserRole; falling back to empty set",
                exc_info=True,
            )
            try:
                from django.db import connections

                for conn in connections.all():
                    conn.close_if_unusable_or_obsolete()
            except (DatabaseError, InterfaceError, OperationalError):
                pass

    scopes: set[str] = set()
    for role in role_names:
        scopes |= ROLE_SCOPE_MAP.get(role, frozenset())
    return frozenset(scopes)


class HasRole(permissions.BasePermission):
    """
    Permission class to check if user has a specific role.

    HasRole takes a required-role argument at construction, so it cannot
    be placed pre-instantiated in ``permission_classes`` — DRF re-invokes
    each entry via ``permission()`` at request time
    (``rest_framework/views.py:284``) and at drf-spectacular schema
    generation, which would raise
    ``TypeError: 'HasRole' object is not callable``. Always pass
    pre-instantiated objects via ``get_permissions`` instead.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            def get_permissions(self):
                return [IsAuthenticated(), HasRole('TENANT_ADMIN')]
    """

    def __init__(self, required_role):
        self.required_role = required_role

    def has_permission(self, request, view):
        """Check if user has the required role"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins have all permissions
        if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
            return True

        # Check if user has the required role
        role_names = []
        if hasattr(request.user, "user_roles"):
            # N+1 acceptable: user_roles typically 1-3 rows.
            # Do not add prefetch_related — low cardinality, hot path.
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
        if not role_names and hasattr(request.user, "id") and request.user.id:
            from hub.apps.users.models import UserRole

            role_names = list(
                UserRole.objects.filter(user_id=request.user.id).values_list(
                    "role__name", flat=True
                )
            )
        return self.required_role in role_names


class HasAnyRole(permissions.BasePermission):
    """
    Permission class to check if user has any of the specified roles.

    HasAnyRole takes a required-roles argument at construction, so it
    cannot be placed pre-instantiated in ``permission_classes`` — DRF
    re-invokes each entry via ``permission()`` at request time
    (``rest_framework/views.py:284``) and at drf-spectacular schema
    generation, which would raise
    ``TypeError: 'HasAnyRole' object is not callable``. Always pass
    pre-instantiated objects via ``get_permissions`` instead.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            def get_permissions(self):
                return [
                    IsAuthenticated(),
                    HasAnyRole(['TENANT_ADMIN', 'DATA_PROVIDER']),
                ]
    """

    def __init__(self, required_roles):
        self.required_roles = required_roles

    def has_permission(self, request, view):
        """Check if user has any of the required roles"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins have all permissions
        if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin:
            return True

        # Check if user has any of the required roles
        role_names = []
        if hasattr(request.user, "user_roles"):
            # N+1 acceptable: user_roles typically 1-3 rows.
            # Do not add prefetch_related — low cardinality, hot path.
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
        # Fallback: direct query when relation is empty (TransactionTestCase, force_authenticate)
        if not role_names and hasattr(request.user, "id") and request.user.id:
            from hub.apps.users.models import UserRole

            role_names = list(
                UserRole.objects.filter(user_id=request.user.id).values_list(
                    "role__name", flat=True
                )
            )
        return any(role in role_names for role in self.required_roles)


class HasScope(permissions.BasePermission):
    """
    Permission class to check if user/API key has a specific scope.

    HasScope takes a required-scope argument at construction, so it
    cannot be placed pre-instantiated in ``permission_classes`` (see
    :class:`HasRole` for the same caveat). Use ``get_permissions``
    instead.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            def get_permissions(self):
                return [IsAuthenticated(), HasScope('assets:write')]
    """

    def __init__(self, required_scope):
        self.required_scope = required_scope

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # API keys are always scope-checked (no enforcement flag bypass).
        # Use getattr(..., None) — MagicMock-safe alternative to hasattr.
        if getattr(request, "api_key_scopes", None) is not None:
            return WILDCARD_SCOPE in request.api_key_scopes or self.required_scope in request.api_key_scopes

        # When ENFORCE_JWT_SCOPES is off, allow all authenticated users (backwards compat)
        if not getattr(settings, "ENFORCE_JWT_SCOPES", False):
            return True

        scopes = _get_user_scopes(request)
        return WILDCARD_SCOPE in scopes or self.required_scope in scopes


class HasAnyScope(permissions.BasePermission):
    """
    Permission class to check if user/API key has any of the specified scopes.

    Usage:
        permission_classes = [IsAuthenticated, HasAnyScope(['assets:read', 'assets:write'])]
    """

    def __init__(self, required_scopes):
        self.required_scopes = required_scopes

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # API keys are always scope-checked.
        # Use getattr(..., None) — MagicMock-safe alternative to hasattr.
        if getattr(request, "api_key_scopes", None) is not None:
            return any(s in request.api_key_scopes for s in self.required_scopes)

        if not getattr(settings, "ENFORCE_JWT_SCOPES", False):
            return True

        scopes = _get_user_scopes(request)
        return WILDCARD_SCOPE in scopes or any(s in scopes for s in self.required_scopes)
