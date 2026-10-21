"""
Permission checking utilities for contract operations.

Provides permission validation for ODPS operations:
- Contract creation (TENANT_ADMIN, DATA_PROVIDER)
- Contract export (TENANT_ADMIN, DATA_PROVIDER, DATA_VIEWER)
- Contract modification/linking (TENANT_ADMIN, DATA_PROVIDER)
- Contract deletion (TENANT_ADMIN)
"""

from django.contrib.auth import get_user_model

User = get_user_model()

# Import GraphQLError conditionally to avoid dependency issues
try:
    from graphql import GraphQLError
except ImportError:
    # Fallback for environments where graphql is not available
    class GraphQLError(Exception):
        """GraphQL Error exception"""


class ContractPermissionChecker:
    """
    Permission checker for contract operations.

    Validates user permissions for various contract operations following
    role-based access control (RBAC) principles.
    """

    @staticmethod
    def check_contract_creation_permission(user) -> None:
        """
        Check if user has permission to create contracts.

        Required roles: TENANT_ADMIN or DATA_PROVIDER

        Args:
            user: User instance

        Raises:
            GraphQLError: If user lacks required permission
        """
        if not user:
            raise GraphQLError("Authentication required")

        # Platform admins have all permissions
        if user.is_platform_admin:
            return

        # Check if user has required role
        has_permission = user.has_role("TENANT_ADMIN", "DATA_PROVIDER")
        if not has_permission:
            raise GraphQLError(
                "Permission denied: Contract creation requires TENANT_ADMIN or DATA_PROVIDER role"
            )

    @staticmethod
    def check_contract_export_permission(user) -> None:
        """
        Check if user has permission to export contracts.

        Required roles: TENANT_ADMIN, DATA_PROVIDER, or DATA_VIEWER

        Args:
            user: User instance

        Raises:
            GraphQLError: If user lacks required permission
        """
        if not user:
            raise GraphQLError("Authentication required")

        # Platform admins have all permissions
        if user.is_platform_admin:
            return

        # Check if user has required role
        has_permission = user.has_role("TENANT_ADMIN", "DATA_PROVIDER", "DATA_VIEWER")
        if not has_permission:
            raise GraphQLError(
                "Permission denied: Contract export requires TENANT_ADMIN, DATA_PROVIDER, or DATA_VIEWER role"
            )

    @staticmethod
    def check_contract_modification_permission(user) -> None:
        """
        Check if user has permission to modify contracts (including linking).

        Required roles: TENANT_ADMIN or DATA_PROVIDER

        Args:
            user: User instance

        Raises:
            GraphQLError: If user lacks required permission
        """
        if not user:
            raise GraphQLError("Authentication required")

        # Platform admins have all permissions
        if user.is_platform_admin:
            return

        # Check if user has required role
        has_permission = user.has_role("TENANT_ADMIN", "DATA_PROVIDER")
        if not has_permission:
            raise GraphQLError(
                "Permission denied: Contract modification requires TENANT_ADMIN or DATA_PROVIDER role"
            )

    @staticmethod
    def check_contract_deletion_permission(user) -> None:
        """
        Check if user has permission to delete contracts.

        Required roles: TENANT_ADMIN

        Args:
            user: User instance

        Raises:
            GraphQLError: If user lacks required permission
        """
        if not user:
            raise GraphQLError("Authentication required")

        # Platform admins have all permissions
        if user.is_platform_admin:
            return

        # Check if user has required role
        has_permission = user.has_role("TENANT_ADMIN")
        if not has_permission:
            raise GraphQLError("Permission denied: Contract deletion requires TENANT_ADMIN role")
