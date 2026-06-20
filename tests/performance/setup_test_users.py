#!/usr/bin/env python
"""
Setup script to create test users for performance testing

Usage:
    python tests/performance/setup_test_users.py
"""

import os
import sys
from pathlib import Path

import django

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


def create_test_users():
    """Create test users for performance testing"""
    print("Creating performance test users...")

    # Create or get tenant
    tenant, created = Tenant.objects.get_or_create(
        slug="perf-test",
        defaults={"name": "Performance Test Tenant", "status": "ACTIVE", "kyc_status": "VERIFIED"},
    )
    if created:
        print(f"✅ Created tenant: {tenant.name}")
    else:
        print(f"✅ Using existing tenant: {tenant.name}")

    # Create default test user
    email = os.getenv("PERF_TEST_USER_EMAIL", "perf-test@example.com")
    password = os.getenv("PERF_TEST_USER_PASSWORD", "perf-test-password-123")

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "tenant": tenant,
            "status": UserStatus.ACTIVE,
            "display_name": "Performance Test User",
        },
    )

    if created:
        user.set_password(password)
        user.save()
        print(f"✅ Created user: {email}")
    else:
        # Update password in case it changed
        user.set_password(password)
        user.save()
        print(f"✅ Updated user: {email}")

    print()
    print("=" * 60)
    print("Test user credentials:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print("=" * 60)
    print()
    print("You can now run performance tests:")
    print("  ./tests/performance/run_performance_tests.sh")
    print()
    print("Or set environment variables:")
    print(f"  export PERF_TEST_USER_EMAIL={email}")
    print(f"  export PERF_TEST_USER_PASSWORD={password}")


if __name__ == "__main__":
    try:
        create_test_users()
    except Exception as e:
        print(f"❌ Error creating test users: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
