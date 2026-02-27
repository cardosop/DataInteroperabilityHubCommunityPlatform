"""
Role-based Authorization Permissions

Custom permission classes for role-based access control.
"""
from rest_framework import permissions


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
        """Check if user/API key has the required scope"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Platform admins have all permissions
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        
        # Check API key scopes if present
        if hasattr(request, 'api_key_scopes'):
            return self.required_scope in request.api_key_scopes
        
        # For regular users, check if they have the scope via roles
        # This is a simplified approach - in production, you might want to map roles to scopes
        # For now, we'll assume all authenticated users have basic scopes
        return True


class HasAnyScope(permissions.BasePermission):
    """
    Permission class to check if user/API key has any of the specified scopes.
    
    Usage:
        permission_classes = [IsAuthenticated, HasAnyScope(['assets:read', 'assets:write'])]
    """
    
    def __init__(self, required_scopes):
        self.required_scopes = required_scopes
    
    def has_permission(self, request, view):
        """Check if user/API key has any of the required scopes"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Platform admins have all permissions
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        
        # Check API key scopes if present
        if hasattr(request, 'api_key_scopes'):
            return any(scope in request.api_key_scopes for scope in self.required_scopes)
        
        # For regular users, assume they have basic scopes
        return True

