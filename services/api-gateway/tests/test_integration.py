"""
Integration tests for API Gateway service.

These tests require Redis and database to be available.
All tests use real services - no mocks or stubs.
"""
import pytest
import os
import sys
import time
from django.utils import timezone

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant, TenantStatus
from django.contrib.auth import get_user_model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from rate_limiter import RateLimiter
from api_key_manager import APIKeyManager, APIKeyInfo

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestRateLimiterIntegration:
    """Integration tests for rate limiter with Redis"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance"""
        redis_url = os.getenv('REDIS_CACHE_URL', 'redis://localhost:6379/0')
        limiter = RateLimiter(redis_url=redis_url)

        # Skip if Redis is not available
        if limiter.redis_client is None:
            pytest.skip("Redis not available - cannot run integration tests without Redis")

        # Test connection
        try:
            if limiter.redis_client:
                limiter.redis_client.ping()
        except Exception as e:
            pytest.skip(f"Redis connection failed: {e}")

        yield limiter

        # Cleanup: Remove test keys
        if limiter.redis_client:
            try:
                test_keys = limiter.redis_client.keys("rate_limit:test_*")
                if test_keys:
                    limiter.redis_client.delete(*test_keys)
            except Exception:
                pass

    def test_rate_limiter_redis_connection(self, rate_limiter):
        """Test rate limiter can connect to Redis"""
        result = rate_limiter.redis_client.ping()
        assert result is True

    def test_rate_limit_check_integration(self, rate_limiter):
        """Test rate limit check with real Redis"""
        key = f"rate_limit:test_integration_{int(time.time() * 1000000)}"

        # First request should be allowed
        allowed1, count1, reset1 = rate_limiter.check_rate_limit(key, 10, window=3600)
        assert allowed1 is True
        assert count1 == 1

        # Second request should be allowed
        allowed2, count2, reset2 = rate_limiter.check_rate_limit(key, 10, window=3600)
        assert allowed2 is True
        assert count2 == 2

        # Cleanup
        rate_limiter.redis_client.delete(key)

    def test_tier_limit_integration(self, rate_limiter):
        """Test tier limit check with real Redis"""
        # Test FREE tier
        allowed, count, reset = rate_limiter.check_tier_limit('FREE')
        assert allowed is True
        assert count >= 0
        assert reset > 0

    def test_tenant_limit_integration(self, rate_limiter):
        """Test tenant limit check with real Redis"""
        tenant_id = f"test-tenant-{int(time.time() * 1000000)}"
        limit = 100

        allowed, count, reset = rate_limiter.check_tenant_limit(tenant_id, limit=limit)
        assert allowed is True
        assert count == 1

        # Cleanup
        key = f"rate_limit:tenant:{tenant_id}"
        rate_limiter.redis_client.delete(key)


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestAPIKeyManagerIntegration:
    """Integration tests for API key manager with database"""

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
            name=f"Integration Test Tenant {unique_id}",
            slug=f"integration-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return User.objects.create_user(
            email=f"integration-test-user-{unique_id}@example.com",
            password="testpass123",
            tenant=tenant,
        )

    def test_api_key_validation_integration(self, api_key_manager, tenant, user):
        """Test API key validation with real database"""
        # Create API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        api_key_obj = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name="Integration Test Key",
            scopes=['read', 'write']
        )

        # Validate the key
        result = api_key_manager.validate_api_key(plaintext_key)

        assert result is not None
        assert isinstance(result, APIKeyInfo)
        assert result.api_key_id == str(api_key_obj.id)
        assert result.tenant_id == str(tenant.id)
        assert result.user_id == str(user.id)
        assert result.scopes == ['read', 'write']

    def test_hash_key_consistency(self, api_key_manager):
        """Test that key hashing is consistent"""
        key = "test-api-key-123"
        hash1 = api_key_manager.hash_key(key)
        hash2 = api_key_manager.hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_api_key_validation_with_expired_key(self, api_key_manager, tenant, user):
        """Test API key validation with expired key"""
        import uuid
        from datetime import timedelta
        unique_id = str(uuid.uuid4())[:8]

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Create expired API key
        expired_key = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name=f"Expired Integration Key {unique_id}",
            expires_at=timezone.now() - timedelta(days=1)
        )

        # Validation should fail
        result = api_key_manager.validate_api_key(plaintext_key)
        assert result is None

    def test_api_key_validation_with_inactive_tenant(self, api_key_manager, user):
        """Test API key validation with inactive tenant"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        # Create suspended tenant
        inactive_tenant = Tenant.objects.create(
            name=f"Inactive Integration Tenant {unique_id}",
            slug=f"inactive-integration-tenant-{unique_id}",
            status=TenantStatus.SUSPENDED,
        )

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        api_key_obj = APIKey.objects.create(
            tenant=inactive_tenant,
            user=user,
            key_hash=key_hash,
            name="Inactive Tenant Key"
        )

        # Validation should fail
        result = api_key_manager.validate_api_key(plaintext_key)
        assert result is None


@pytest.mark.integration
class TestRoutingConfigurationIntegration:
    """Integration tests for routing configuration"""

    def test_route_config_loading(self):
        """Test that route configuration loads correctly"""
        from routing import ROUTE_CONFIG, validate_route_config

        # Route config should be loaded
        assert ROUTE_CONFIG is not None
        assert len(ROUTE_CONFIG) > 0

        # Should validate successfully
        validate_route_config(ROUTE_CONFIG)

        # Check that all routes have valid URLs
        for route, url in ROUTE_CONFIG.items():
            assert url.startswith('http://')
            assert ':' in url.split('//')[1]  # Has port

    def test_get_backend_url_integration(self):
        """Test get_backend_url function with real configuration"""
        from routing import get_backend_url, ROUTE_CONFIG

        # Test known routes
        for route_prefix in ROUTE_CONFIG.keys():
            url = get_backend_url(route_prefix)
            assert url == ROUTE_CONFIG[route_prefix]

            # Test with subpath
            url = get_backend_url(f"{route_prefix}/subpath/123")
            assert url == ROUTE_CONFIG[route_prefix]

        # Test unknown route
        url = get_backend_url('/api/v1/unknown')
        assert url is None


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestUsageTrackingIntegration:
    """Integration tests for usage tracking"""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return Tenant.objects.create(
            name=f"Usage Tracking Test Tenant {unique_id}",
            slug=f"usage-tracking-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.fixture
    def user(self, tenant):
        """Create a test user"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        return User.objects.create_user(
            email=f"usage-tracking-user-{unique_id}@example.com",
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
            name="Usage Tracking Test Key",
            scopes=['read', 'write']
        )
        return api_key_obj, plaintext_key

    def test_usage_tracking_service_track_request(self, tenant, user):
        """Test UsageTrackingService.track_request()"""
        from hub.apps.baas.services import UsageTrackingService
        from hub.apps.baas.models import APIKey as BaaSAPIKey, APITierModel
        from django.db import connection

        # Check if BaaS tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'baas_api_tier'
                );
            """)
            table_exists = cursor.fetchone()[0]

        if not table_exists:
            pytest.skip("BaaS tables not available - migrations may not be applied")

        # Create or get a tier (required for BaaS APIKey)
        tier, _ = APITierModel.objects.get_or_create(
            name='FREE',
            defaults={
                'max_requests_per_month': 1000,
                'max_requests_per_hour': 100,
            }
        )

        # Create BaaS API key (required by UsageTrackingService)
        plaintext_key = BaaSAPIKey.generate_key()
        key_hash = BaaSAPIKey.hash_key(plaintext_key)
        baas_api_key = BaaSAPIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            tier=tier,
            name="Usage Tracking Test Key"
        )

        usage_tracker = UsageTrackingService(
            tenant_id=str(tenant.id),
            user_id=str(user.id)
        )

        # Track a request
        usage_record = usage_tracker.track_request(
            api_key_id=str(baas_api_key.id),
            endpoint='/api/v1/test',
            method='GET',
            status_code=200,
            response_time_ms=150,
            request_size_bytes=100,
            response_size_bytes=500
        )

        # Verify usage record was created
        assert usage_record is not None
        assert usage_record.api_key_id == baas_api_key.id
        assert usage_record.endpoint == '/api/v1/test'
        assert usage_record.method == 'GET'
        assert usage_record.status_code == 200
        assert usage_record.response_time_ms == 150
        assert usage_record.request_size_bytes == 100
        assert usage_record.response_size_bytes == 500
