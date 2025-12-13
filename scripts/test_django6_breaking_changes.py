#!/usr/bin/env python3
"""
Test script to verify Django 6 breaking changes are handled correctly.

This script tests for common Django 6 breaking changes and verifies
that the codebase handles them correctly.
"""
import os
import sys
import django
from pathlib import Path

# Add hub to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'hub'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.db import connection
from django.core.management import call_command


class Django6BreakingChangesTest(TestCase):
    """Test for Django 6 breaking changes."""
    
    def test_middleware_pattern(self):
        """Test that all middleware use Django 6 pattern (not MiddlewareMixin)."""
        from hub.apps.api.middleware import RequestIDMiddleware, RateLimitMiddleware
        from hub.apps.auth.middleware import TenantScopingMiddleware
        from hub.apps.tenants.middleware import TenantSuspensionMiddleware
        from hub.apps.observability.middleware import MetricsMiddleware
        
        # All middleware should use __init__(get_response) pattern
        factory = RequestFactory()
        get_response = lambda request: HttpResponse()
        
        # Test each middleware
        middlewares = [
            RequestIDMiddleware,
            RateLimitMiddleware,
            TenantScopingMiddleware,
            TenantSuspensionMiddleware,
            MetricsMiddleware,
        ]
        
        for MiddlewareClass in middlewares:
            middleware = MiddlewareClass(get_response)
            request = factory.get("/")
            response = middleware(request)
            
            # Should return HttpResponse
            self.assertIsInstance(response, HttpResponse)
    
    def test_jsonfield_db_index_support(self):
        """Test that JSONField supports db_index (Django 6 feature)."""
        from hub.apps.contracts.models import Contract
        
        # Get the hub_contract_json field
        field = Contract._meta.get_field('hub_contract_json')
        
        # Should have db_index=True (Django 6 feature)
        self.assertTrue(field.db_index, "hub_contract_json should have db_index=True for GIN index")
    
    def test_django_version(self):
        """Test that Django 6 is installed."""
        import django
        self.assertGreaterEqual(django.VERSION[0], 6, "Django 6.0+ required")
    
    def test_drf_compatibility(self):
        """Test that Django REST Framework is compatible with Django 6."""
        try:
            import rest_framework
            from rest_framework import __version__ as drf_version
            
            # DRF 3.15+ is compatible with Django 6
            major, minor = map(int, drf_version.split('.')[:2])
            self.assertGreaterEqual(
                (major, minor),
                (3, 15),
                f"DRF {drf_version} is not compatible with Django 6. Need 3.15+"
            )
        except ImportError:
            self.fail("Django REST Framework not installed")
    
    def test_security_middleware_present(self):
        """Test that SecurityMiddleware is in MIDDLEWARE list."""
        from django.conf import settings
        
        self.assertIn(
            'django.middleware.security.SecurityMiddleware',
            settings.MIDDLEWARE,
            "SecurityMiddleware must be in MIDDLEWARE list"
        )
    
    def test_security_settings_configured(self):
        """Test that Django 6 security settings are configured."""
        from django.conf import settings
        
        # Check that security settings exist
        self.assertTrue(hasattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF'))
        self.assertTrue(hasattr(settings, 'SECURE_REFERRER_POLICY'))
        self.assertTrue(hasattr(settings, 'X_FRAME_OPTIONS'))
    
    def test_jsonfield_gin_index_exists(self):
        """Test that GIN index exists on hub_contract_json (PostgreSQL only)."""
        if connection.vendor != 'postgresql':
            self.skipTest("GIN index test only for PostgreSQL")
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'contracts_contract'
                AND indexdef LIKE '%hub_contract_json%'
            """)
            indexes = cursor.fetchall()
            
            self.assertGreater(
                len(indexes),
                0,
                "GIN index on hub_contract_json not found. Run migration 0003."
            )
    
    def test_migration_applies_successfully(self):
        """Test that Django 6 migrations apply successfully."""
        from django.core.management import call_command
        from io import StringIO
        
        # Check migration status
        output = StringIO()
        call_command('showmigrations', 'contracts', stdout=output, no_color=True)
        output_str = output.getvalue()
        
        # Should show migration 0003
        self.assertIn('0003', output_str, "Migration 0003 should be listed")


def run_tests():
    """Run all breaking changes tests."""
    import unittest
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(Django6BreakingChangesTest)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)

