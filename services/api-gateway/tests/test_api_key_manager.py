"""
Unit tests for API key manager using real database.

These tests require Django database to be available and will use real database operations.
No mocks or stubs are used - all tests use real database connections.
"""
import pytest
import os
import sys
from django.utils import timezone
from datetime import timedelta

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant, TenantStatus
from django.contrib.auth import get_user_model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from api_key_manager import APIKeyManager, APIKeyInfo

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestAPIKeyManager:
    """Test API key manager functionality with real database"""

    @pytest.fixture
    def api_key_manager(self):
        """Create API key manager instance"""
        return APIKeyManager()

    @pytest.fixture
    def tenant(self):
        """Create a test tenant"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return Tenant.objects.create(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return User.objects.create_user(
            email=f"test-user-{unique_id}@example.com",
            password="testpass123",
            tenant=tenant,
        )

    @pytest.fixture
    def api_key(self, tenant, user):
        """Create a test API key"""
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        api_key_obj = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name="Test API Key",
            scopes=['read', 'write']
        )
        return api_key_obj, plaintext_key

    def test_hash_key(self, api_key_manager):
        """Test API key hashing"""
        key = "test-api-key-123"
        hash1 = api_key_manager.hash_key(key)
        hash2 = api_key_manager.hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length
        assert hash1 != key  # Should be hashed

    def test_validate_api_key_success(self, api_key_manager, api_key):
        """Test successful API key validation"""
        api_key_obj, plaintext_key = api_key

        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is not None
        assert isinstance(result, APIKeyInfo)
        assert result.api_key_id == str(api_key_obj.id)
        assert result.tenant_id == str(api_key_obj.tenant.id)
        assert result.user_id == str(api_key_obj.user.id)
        assert result.scopes == ['read', 'write']
        assert result.name == "Test API Key"
        assert result.tier == 'FREE'  # Default tier

    def test_validate_api_key_not_found(self, api_key_manager):
        """Test API key validation when key not found"""
        invalid_key = "invalid-key-that-does-not-exist"
        result = api_key_manager.validate_api_key(invalid_key)

        assert result is None

    def test_validate_api_key_expired(self, api_key_manager, tenant, user):
        """Test API key validation when key is expired"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Create expired API key
        expired_key = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name=f"Expired Key {unique_id}",
            expires_at=timezone.now() - timedelta(days=1)  # Expired yesterday
        )

        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is None

    def test_validate_api_key_inactive_tenant(self, api_key_manager, user):
        """Test API key validation when tenant is inactive"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        # Create inactive tenant
        inactive_tenant = Tenant.objects.create(
            name=f"Inactive Tenant {unique_id}",
            slug=f"inactive-tenant-{unique_id}",
            status=TenantStatus.SUSPENDED,  # Suspended tenant
        )

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        api_key_obj = APIKey.objects.create(
            tenant=inactive_tenant,
            user=user,
            key_hash=key_hash,
            name="Inactive Tenant Key"
        )

        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is None

    def test_validate_api_key_non_expiring(self, api_key_manager, tenant, user):
        """Test API key validation for non-expiring key"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        api_key_obj = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name=f"Non-expiring Key {unique_id}",
            expires_at=None  # No expiration
        )

        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is not None
        assert result.api_key_id == str(api_key_obj.id)

    def test_validate_api_key_updates_last_used(self, api_key_manager, api_key):
        """Test that API key validation updates last_used_at"""
        api_key_obj, plaintext_key = api_key

        # Initially last_used_at should be None
        assert api_key_obj.last_used_at is None

        # Validate the key
        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is not None

        # Refresh from database
        api_key_obj.refresh_from_db()

        # last_used_at should be updated
        assert api_key_obj.last_used_at is not None
        assert api_key_obj.last_used_at <= timezone.now()

    def test_get_api_key_info(self, api_key_manager, api_key):
        """Test getting API key info by ID"""
        api_key_obj, plaintext_key = api_key

        result = api_key_manager.get_api_key_info(str(api_key_obj.id))

        assert result is not None
        assert isinstance(result, APIKeyInfo)
        assert result.api_key_id == str(api_key_obj.id)
        assert result.tenant_id == str(api_key_obj.tenant.id)
        assert result.user_id == str(api_key_obj.user.id)

    def test_get_api_key_info_not_found(self, api_key_manager):
        """Test getting API key info for non-existent key"""
        import uuid
        non_existent_id = str(uuid.uuid4())

        result = api_key_manager.get_api_key_info(non_existent_id)

        assert result is None

    def test_validate_api_key_without_user(self, api_key_manager, tenant):
        """Test API key validation for key without user (tenant-scoped)"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        api_key_obj = APIKey.objects.create(
            tenant=tenant,
            user=None,  # No user
            key_hash=key_hash,
            name=f"Tenant-scoped Key {unique_id}"
        )

        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is not None
        assert result.api_key_id == str(api_key_obj.id)
        assert result.user_id is None
