"""
Unit tests for Tenant model.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus


class TenantModelTest(TestCase):
    """Test Tenant model"""
    
    def test_create_tenant(self):
        """Test tenant creation"""
        tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.assertEqual(tenant.name, "Test Tenant")
        self.assertEqual(tenant.slug, "test-tenant")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        self.assertIsNone(tenant.deleted_at)
    
    def test_tenant_status_choices(self):
        """Test tenant status enum"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)
        
        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
    
    def test_kyc_status_choices(self):
        """Test KYC status enum"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save()
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)
    
    def test_tenant_is_active(self):
        """Test is_active method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertTrue(tenant.is_active())
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertFalse(tenant.is_active())
    
    def test_tenant_is_suspended(self):
        """Test is_suspended method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertFalse(tenant.is_suspended())
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertTrue(tenant.is_suspended())
    
    def test_tenant_is_deleted(self):
        """Test is_deleted method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        self.assertFalse(tenant.is_deleted())
        
        tenant.status = TenantStatus.DELETED
        tenant.save()
        self.assertTrue(tenant.is_deleted())
    
    def test_can_publish_to_marketplace(self):
        """Test can_publish_to_marketplace method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        
        # Unverified tenant cannot publish
        self.assertFalse(tenant.can_publish_to_marketplace())
        
        # Verified but suspended cannot publish
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.status = TenantStatus.SUSPENDED
        tenant.save()
        self.assertFalse(tenant.can_publish_to_marketplace())
        
        # Verified and active can publish
        tenant.status = TenantStatus.ACTIVE
        tenant.save()
        self.assertTrue(tenant.can_publish_to_marketplace())
    
    def test_suspend_tenant(self):
        """Test suspend method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        
        tenant.suspend()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)
        
        # Cannot suspend deleted tenant
        tenant.status = TenantStatus.DELETED
        tenant.save()
        with self.assertRaises(ValueError):
            tenant.suspend()
    
    def test_reactivate_tenant(self):
        """Test reactivate method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        tenant.suspend()
        
        tenant.reactivate()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        
        # Can only reactivate suspended tenants
        tenant.status = TenantStatus.ACTIVE
        tenant.save()
        with self.assertRaises(ValueError):
            tenant.reactivate()
    
    def test_soft_delete_tenant(self):
        """Test soft_delete method"""
        tenant = Tenant.objects.create(name="Test", slug="test")
        
        tenant.soft_delete()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)
    
    def test_slug_uniqueness(self):
        """Test slug uniqueness constraint"""
        Tenant.objects.create(name="Test 1", slug="test-tenant")
        
        with self.assertRaises(Exception):  # IntegrityError
            Tenant.objects.create(name="Test 2", slug="test-tenant")
    
    def test_name_uniqueness(self):
        """Test name uniqueness constraint"""
        Tenant.objects.create(name="Test Tenant", slug="test-tenant-1")
        
        with self.assertRaises(Exception):  # IntegrityError
            Tenant.objects.create(name="Test Tenant", slug="test-tenant-2")

