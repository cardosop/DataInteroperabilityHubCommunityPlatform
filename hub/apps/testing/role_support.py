"""
Test support: ensure user has DATA_PROVIDER role for asset create/update.

Asset views require DATA_PROVIDER or TENANT_ADMIN role for create and update.
Tests that hit the full request stack (asset CRUD via API) must assign this role
so permission checks pass. No mocks: real Role and UserRole records only.
"""

from hub.apps.users.models import Role, UserRole


def ensure_user_has_data_provider_role(user) -> None:
    """
    Ensure user has DATA_PROVIDER role so asset create/update views allow writes.

    Creates the Role for the user's tenant (get_or_create) and UserRole linking
    user to role. Idempotent: if user already has DATA_PROVIDER, does nothing.
    """
    tenant = user.tenant
    if not tenant:
        return

    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="DATA_PROVIDER",
        defaults={"description": "Data Provider"},
    )

    UserRole.objects.get_or_create(user=user, role=role)


def ensure_user_has_tenant_admin_role(user) -> None:
    """
    Ensure user has TENANT_ADMIN role so all tenant-scoped views allow access.

    Creates the Role for the user's tenant (get_or_create) and UserRole linking
    user to role. Idempotent: if user already has TENANT_ADMIN, does nothing.
    """
    tenant = user.tenant
    if not tenant:
        return

    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant Administrator"},
    )

    UserRole.objects.get_or_create(user=user, role=role)
