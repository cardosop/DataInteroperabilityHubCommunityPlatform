#!/usr/bin/env python3
"""
Django management script to set up tenant and API key for SDK tests.

This script should be run inside the Docker container where Django is available:
  docker-compose exec hub python /app/scripts/setup_sdk_test_tenant_and_api_key.py

Or via manage.py shell:
  python manage.py shell < scripts/setup_sdk_test_tenant_and_api_key.py
"""
import os
import sys

# Add the hub directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()

from hub.apps.users.models import User
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.auth.models import APIKey

def main():
    print("Setting up SDK test tenant and API key...")

    # Step 1: Get or create test user
    print("1. Getting/creating test user...")
    user, created = User.objects.get_or_create(
        email='sdk-test@example.com',
        defaults={'display_name': 'SDK Test User', 'status': 'ACTIVE'}
    )
    if created:
        user.set_password('TestPass123!')
        user.save()
        print(f"   ✓ Created user: {user.email}")
    else:
        print(f"   ✓ Found existing user: {user.email}")

    # Step 2: Get or create tenant
    print("2. Getting/creating tenant...")
    tenant, created = Tenant.objects.get_or_create(
        slug='sdk-test-tenant',
        defaults={
            'name': 'SDK Test Tenant',
            'status': TenantStatus.ACTIVE,
            'kyc_status': KYCStatus.UNVERIFIED,
            'region': 'us-east-1'
        }
    )
    if created:
        print(f"   ✓ Created tenant: {tenant.name} (ID: {tenant.id})")
    else:
        print(f"   ✓ Found existing tenant: {tenant.name} (ID: {tenant.id})")

    # Step 3: Assign user to tenant
    print("3. Assigning user to tenant...")
    if user.tenant != tenant:
        user.tenant = tenant
        user.save()
        print(f"   ✓ Assigned user to tenant")
    else:
        print(f"   ✓ User already assigned to tenant")

    # Step 4: Delete existing API key if it exists (we can't retrieve the original key)
    print("4. Creating API key...")
    existing_key = APIKey.objects.filter(user=user, name='SDK Test API Key').first()
    if existing_key:
        print("   Removing existing API key (cannot retrieve original key)...")
        existing_key.delete()

    # Step 5: Generate new API key
    api_key_value = APIKey.generate_key()
    api_key_hash = APIKey.hash_key(api_key_value)

    api_key_obj = APIKey.objects.create(
        tenant=tenant,
        user=user,
        name='SDK Test API Key',
        key_hash=api_key_hash,
        scopes=[],
        expires_at=None
    )

    print(f"   ✓ Created API key")
    print(f"\n{'='*60}")
    print("TEST_API_KEY for use in tests:")
    print(f"{'='*60}")
    print(api_key_value)
    print(f"{'='*60}")
    print("\nTo use this in tests, run:")
    print(f"export TEST_API_KEY='{api_key_value}'")

    return api_key_value

if __name__ == "__main__":
    try:
        api_key = main()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

