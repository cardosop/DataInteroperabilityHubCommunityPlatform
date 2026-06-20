#!/usr/bin/env python3
"""
Setup E2E Test User
Creates or updates test user for frontend E2E tests
Run from project root: python3 frontend/scripts/setup_e2e_user.py
"""

import os
import sys

import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus


def setup_e2e_user():
    """Create or update E2E test user"""
    # Create or get tenant (VERIFIED KYC so Phase 4 marketplace listing creation passes)
    tenant, created = Tenant.objects.get_or_create(
        name="E2E Test Tenant",
        slug="e2e-test-tenant",
        defaults={"status": "ACTIVE", "kyc_status": KYCStatus.VERIFIED},
    )
    if not created and tenant.kyc_status != KYCStatus.VERIFIED:
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status", "updated_at"])

    # Create or get user
    user, created = User.objects.get_or_create(
        email="e2e_test@example.com",
        defaults={"tenant": tenant, "status": UserStatus.ACTIVE, "display_name": "E2E Test User"},
    )

    # Always set password and ensure user is active (must match frontend e2e/setup/create-test-user.ts)
    user.set_password("TestPass123")
    user.status = UserStatus.ACTIVE
    user.tenant = tenant
    user.display_name = "E2E Test User"
    user.save()

    if created:
        print(f"✅ Created test user: {user.email}")
    else:
        print(f"✅ Updated test user: {user.email}")

    # Assign DATA_PROVIDER role
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
    )

    UserRole.objects.get_or_create(user=user, role=role)
    print("✅ Assigned DATA_PROVIDER role to user")

    # Verify user can be authenticated
    from django.contrib.auth import authenticate

    authenticated = authenticate(email=user.email, password="TestPass123")
    if authenticated:
        print("✅ User authentication verified")
    else:
        print("❌ User authentication failed - check password")
        sys.exit(1)

    # Create consumer tenant and user so Phase 4 E2E (purchase flow) can create orders
    # Backend requires "User must belong to a tenant to create orders"
    consumer_tenant, _ct_created = Tenant.objects.get_or_create(
        name="E2E Consumer Tenant",
        slug="e2e-consumer-tenant",
        defaults={"status": "ACTIVE", "kyc_status": KYCStatus.VERIFIED},
    )
    consumer_user, cu_created = User.objects.get_or_create(
        email="e2e_consumer@example.com",
        defaults={
            "tenant": consumer_tenant,
            "status": UserStatus.ACTIVE,
            "display_name": "E2E Consumer User",
        },
    )
    consumer_user.set_password("TestPass123")
    consumer_user.status = UserStatus.ACTIVE
    consumer_user.tenant = consumer_tenant
    consumer_user.display_name = "E2E Consumer User"
    consumer_user.save()
    if cu_created:
        print(f"✅ Created consumer test user: {consumer_user.email}")
    else:
        print(f"✅ Updated consumer test user: {consumer_user.email}")
    consumer_role, _ = Role.objects.get_or_create(
        tenant=consumer_tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
    )
    UserRole.objects.get_or_create(user=consumer_user, role=consumer_role)
    if authenticate(email=consumer_user.email, password="TestPass123"):
        print("✅ Consumer user authentication verified")
    else:
        print("❌ Consumer user authentication failed")


if __name__ == "__main__":
    setup_e2e_user()
