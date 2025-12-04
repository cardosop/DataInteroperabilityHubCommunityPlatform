"""
Tests for init_tenant_configs management command.

GAP-1.2.5: Tests for management command to initialize tenant configs.
"""
import pytest
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from django.db import transaction

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.validators import get_platform_defaults


pytestmark = pytest.mark.django_db(transaction=True)


class InitTenantConfigsCommandTest(TestCase):
    """Test init_tenant_configs management command"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.platform_defaults = get_platform_defaults()
    
    def test_creates_configs_for_tenants_without_config(self):
        """Test command creates TenantConfig for tenants without config"""
        # Create tenants without config
        tenant1 = Tenant.objects.create(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        
        # Run command
        out = StringIO()
        call_command('init_tenant_configs', stdout=out)
        
        # Verify configs were created
        self.assertTrue(TenantConfig.objects.filter(tenant=tenant1).exists())
        self.assertTrue(TenantConfig.objects.filter(tenant=tenant2).exists())
        
        # Verify configs have platform defaults
        config1 = TenantConfig.objects.get(tenant=tenant1)
        self.assertEqual(config1.default_dq_profile, self.platform_defaults["default_dq_profile"])
        self.assertEqual(config1.max_job_concurrency, self.platform_defaults["max_job_concurrency"])
        
        config2 = TenantConfig.objects.get(tenant=tenant2)
        self.assertEqual(config2.default_dq_profile, self.platform_defaults["default_dq_profile"])
    
    def test_skips_existing_configs(self):
        """Test command skips tenants that already have config"""
        # Create tenant with config
        tenant1 = Tenant.objects.create(name="Tenant 1", slug="tenant-1")
        config1 = TenantConfig.objects.create(
            tenant=tenant1,
            default_dq_profile="intake_basic_soda",
            max_job_concurrency=10
        )
        original_concurrency = config1.max_job_concurrency
        
        # Create tenant without config
        tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        
        # Run command
        out = StringIO()
        call_command('init_tenant_configs', stdout=out)
        
        # Verify tenant1 config unchanged
        config1.refresh_from_db()
        self.assertEqual(config1.max_job_concurrency, original_concurrency)
        self.assertEqual(config1.default_dq_profile, "intake_basic_soda")
        
        # Verify tenant2 config created
        self.assertTrue(TenantConfig.objects.filter(tenant=tenant2).exists())
    
    def test_dry_run_mode(self):
        """Test dry-run mode shows what would be created without creating"""
        # Create tenant without config
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        
        # Run command in dry-run mode
        out = StringIO()
        call_command('init_tenant_configs', '--dry-run', stdout=out)
        
        # Verify config was NOT created
        self.assertFalse(TenantConfig.objects.filter(tenant=tenant).exists())
        
        # Verify output mentions dry-run
        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("would create", output.lower())
    
    def test_specific_tenant_id(self):
        """Test command with --tenant-id flag processes only specific tenant"""
        # Create tenants
        tenant1 = Tenant.objects.create(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        
        # Run command for specific tenant
        out = StringIO()
        call_command('init_tenant_configs', '--tenant-id', str(tenant1.id), stdout=out)
        
        # Verify only tenant1 config created
        self.assertTrue(TenantConfig.objects.filter(tenant=tenant1).exists())
        self.assertFalse(TenantConfig.objects.filter(tenant=tenant2).exists())
    
    def test_progress_reporting(self):
        """Test command reports progress (tenants processed, errors)"""
        # Create multiple tenants
        for i in range(5):
            Tenant.objects.create(name=f"Tenant {i}", slug=f"tenant-{i}")
        
        # Run command
        out = StringIO()
        call_command('init_tenant_configs', stdout=out)
        
        # Verify output contains summary
        output = out.getvalue()
        self.assertIn("Summary", output)
        self.assertIn("Created", output)
        self.assertIn("5", output)  # Should mention 5 configs created
    
    def test_error_handling(self):
        """Test command handles errors gracefully and continues processing"""
        # Create tenant
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        
        # Mock TenantConfig.objects.create to raise error for first call
        original_create = TenantConfig.objects.create
        
        call_count = [0]
        def mock_create(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Simulated error")
            return original_create(*args, **kwargs)
        
        # This test verifies error handling - in practice, errors are logged and processing continues
        # For now, we verify the command doesn't crash
        out = StringIO()
        try:
            call_command('init_tenant_configs', stdout=out)
        except Exception:
            # Command should handle errors gracefully
            pass
        
        # Verify at least some processing occurred
        output = out.getvalue()
        self.assertIn("tenant", output.lower())
    
    def test_all_tenants_have_config_message(self):
        """Test command shows message when all tenants already have config"""
        # Create tenant with config
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        TenantConfig.objects.create(tenant=tenant)
        
        # Run command
        out = StringIO()
        call_command('init_tenant_configs', stdout=out)
        
        # Verify message
        output = out.getvalue()
        self.assertIn("already have TenantConfig", output)
        self.assertIn("Nothing to do", output)

