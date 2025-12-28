#!/usr/bin/env python
"""
Helper script to generate API key for SDK integration tests.
Can be run from Docker container to create test API key.
"""
import sys
import os

# Add /app to path so hub module can be found
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

# Change to hub directory for Django setup
original_cwd = os.getcwd()
try:
    os.chdir('/app/hub')
except OSError:
    pass  # Directory may not exist, continue anyway

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey

# Create or get tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='virtualization-sdk-test-tenant',
    defaults={'name': 'Virtualization SDK Test Tenant'}
)

# Create or get DATA_PROVIDER role
provider_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='DATA_PROVIDER',
    defaults={'description': 'Data Provider'}
)

# Create or get user
user, _ = User.objects.get_or_create(
    email='virtualization-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign role
UserRole.objects.get_or_create(user=user, role=provider_role)

# Delete existing API key
APIKey.objects.filter(user=user, name='virtualization-sdk-test-key').delete()

# Create new API key
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='virtualization-sdk-test-key',
    key_hash=api_key_hash,
    scopes=['virtualization:write', 'virtualization:read']
)

# Print API key (no newline)
print(api_key_value, end='')

