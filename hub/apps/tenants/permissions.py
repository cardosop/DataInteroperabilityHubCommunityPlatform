"""
Tenant Permissions

Custom permissions for tenant management.
"""
from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Permission class to check if user is a platform admin.
    
    Only platform admins can manage tenants.
    """
    
    def has_permission(self, request, view):
        """Check if user is platform admin"""
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, "is_platform_admin") and
            request.user.is_platform_admin
        )


class CanPublishToMarketplace(permissions.BasePermission):
    """
    Permission class to check if tenant can publish to marketplace.
    
    Requires tenant to have KYC status VERIFIED and status ACTIVE.
    """
    
    def has_permission(self, request, view):
        """Check if tenant can publish to marketplace"""
        tenant = getattr(request, "tenant", None)
        
        if not tenant:
            return False
        
        return tenant.can_publish_to_marketplace()

