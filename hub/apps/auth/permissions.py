"""
Role-based Authorization Permissions

Custom permission classes for role-based access control.
"""
from django.conf import settings
from rest_framework import permissions


# ── Role → Scope mapping ────────────────────────────────────────────────
# Each role grants a set of scopes. PLATFORM_ADMIN gets wildcard ("*").
# Use frozensets so callers can do subset checks (e.g. dp.issubset(ta)).
ROLE_SCOPE_MAP: dict[str, frozenset[str]] = {
    "PLATFORM_ADMIN": frozenset({"*"}),
    "TENANT_ADMIN": frozenset({
        "assets:read", "assets:write",
        "contracts:read", "contracts:write",
        "datasets:read", "datasets:write",
        "compliance:read", "compliance:write",
        "governance:read", "governance:write",
        "users:read", "users:write",
        "billing:read", "billing:write",
        "audit:read",
        "files:read", "files:write",
        "jobs:read", "jobs:write",
        "marketplace:read", "marketplace:write",
        "mesh:read", "mesh:write",
        "integrations:read", "integrations:write",
        "ml:read", "ml:write",
        "transformation:read", "transformation:write",
    }),
    "DATA_PROVIDER": frozenset({
        "assets:read", "assets:write",
        "contracts:read", "contracts:write",
        "datasets:read", "datasets:write",
        "files:read", "files:write",
        "jobs:read", "jobs:write",
        "marketplace:read", "marketplace:write",
        "mesh:read", "mesh:write",
        "integrations:read", "integrations:write",
        "ml:read", "ml:write",
        "transformation:read", "transformation:write",
    }),
    "DATA_CONSUMER": frozenset({
        "assets:read",
        "contracts:read",
        "datasets:read",
        "files:read",
        "marketplace:read",
        "mesh:read",
        "ml:read",
        "transformation:read",
    }),
    "DATA_VIEWER": frozenset({
        "assets:read",
        "contracts:read",
        "datasets:read",
    }),
    "AUDITOR": frozenset({
        "audit:read",
        "compliance:read",
        "governance:read",
    }),
    "COMPLIANCE_OFFICER": frozenset({
        "compliance:read", "compliance:write",
        "governance:read", "governance:write",
        "audit:read",
    }),
}


def _get_user_scopes(request) -> frozenset[str]:
    """Resolve effective scopes for a request from roles or API key."""
    if hasattr(request, 'api_key_scopes'):
        return frozenset(request.api_key_scopes)

    if not hasattr(request, 'user') or not request.user or not request.user.is_authenticated:
        return frozenset()

    if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
        return frozenset({"*"})

    # Collect scopes from user roles
    role_names = set()
    if hasattr(request, '_roles') and request._roles:
        # Test shortcut: roles passed directly on request
        role_names = set(request._roles)
    else:
        try:
            from hub.apps.users.models import UserRole
            role_names = set(
                UserRole.objects.filter(user_id=request.user.id)
                .values_list('role__name', flat=True)
            )
        except Exception:
            pass

    scopes: set[str] = set()
    for role in role_names:
        scopes |= ROLE_SCOPE_MAP.get(role, frozenset())
    return frozenset(scopes)


class HasRole(permissions.BasePermission):
    """
    Permission class to check if user has a specific role.
    
    Usage:
        permission_classes = [IsAuthenticated, HasRole('TENANT_ADMIN')]
    """
    
    def __init__(self, required_role):
        self.required_role = required_role
    
    def has_permission(self, request, view):
        """Check if user has the required role"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Platform admins have all permissions
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        
        # Check if user has the required role
        role_names = []
        if hasattr(request.user, 'user_roles'):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
        if not role_names and hasattr(request.user, 'id') and request.user.id:
            from hub.apps.users.models import UserRole
            role_names = list(
                UserRole.objects.filter(user_id=request.user.id)
                .values_list('role__name', flat=True)
            )
        return self.required_role in role_names


class HasAnyRole(permissions.BasePermission):
    """
    Permission class to check if user has any of the specified roles.
    
    Usage:
        permission_classes = [IsAuthenticated, HasAnyRole(['TENANT_ADMIN', 'DATA_PROVIDER'])]
    """
    
    def __init__(self, required_roles):
        self.required_roles = required_roles
    
    def has_permission(self, request, view):
        """Check if user has any of the required roles"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Platform admins have all permissions
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        
        # Check if user has any of the required roles
        role_names = []
        if hasattr(request.user, 'user_roles'):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
        # Fallback: direct query when relation is empty (TransactionTestCase, force_authenticate)
        if not role_names and hasattr(request.user, 'id') and request.user.id:
            from hub.apps.users.models import UserRole
            role_names = list(
                UserRole.objects.filter(user_id=request.user.id)
                .values_list('role__name', flat=True)
            )
        return any(role in role_names for role in self.required_roles)


class HasScope(permissions.BasePermission):
    """
    Permission class to check if user/API key has a specific scope.

    Usage:
        permission_classes = [IsAuthenticated, HasScope('assets:write')]
    """

    def __init__(self, required_scope):
        self.required_scope = required_scope

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # API keys are always scope-checked (no enforcement flag bypass)
        if hasattr(request, 'api_key_scopes'):
            return self.required_scope in request.api_key_scopes

        # When ENFORCE_JWT_SCOPES is off, allow all authenticated users (backwards compat)
        if not getattr(settings, 'ENFORCE_JWT_SCOPES', False):
            return True

        scopes = _get_user_scopes(request)
        return "*" in scopes or self.required_scope in scopes


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

        # API keys are always scope-checked
        if hasattr(request, 'api_key_scopes'):
            return any(s in request.api_key_scopes for s in self.required_scopes)

        if not getattr(settings, 'ENFORCE_JWT_SCOPES', False):
            return True

        scopes = _get_user_scopes(request)
        return "*" in scopes or any(s in scopes for s in self.required_scopes)

