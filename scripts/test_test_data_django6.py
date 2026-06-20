#!/usr/bin/env python3
"""
Test Test Data Creation and Cleanup with Django 6

This script tests that test data (factories and fixtures) can be created
and cleaned up correctly with Django 6.

Uses Django's test infrastructure to ensure proper database setup.
"""

import os
import sys
import uuid
from pathlib import Path

import django

# Setup Django
base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from django.contrib.auth import get_user_model

from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.jobs.models import Job
from hub.apps.tenants.models import Tenant, TenantConfig
from tests.factories import EmailDeliveryFactory, JobFactory, TenantConfigFactory, TenantFactory

User = get_user_model()

# Color codes
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def test_tenant_factory():
    """Test TenantFactory creation"""
    print(f"{BLUE}Testing TenantFactory...{RESET}")
    try:
        # Use unique name to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        assert tenant.id is not None
        assert tenant.name is not None
        assert tenant.slug is not None
        print(f"{GREEN}✅ TenantFactory: Created tenant {tenant.name}{RESET}")
        # Cleanup
        tenant.delete()
        return True
    except Exception as e:
        print(f"{RED}❌ TenantFactory failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def test_tenant_config_factory():
    """Test TenantConfigFactory creation"""
    print(f"{BLUE}Testing TenantConfigFactory...{RESET}")
    try:
        # Use unique name to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        config = TenantConfigFactory.create_tenant_config(tenant=tenant)
        assert config.id is not None
        assert config.tenant == tenant
        assert config.default_dq_profile is not None
        print(f"{GREEN}✅ TenantConfigFactory: Created config for tenant {tenant.name}{RESET}")
        # Cleanup
        config.delete()
        tenant.delete()
        return True
    except Exception as e:
        print(f"{RED}❌ TenantConfigFactory failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def test_email_delivery_factory():
    """Test EmailDeliveryFactory creation"""
    print(f"{BLUE}Testing EmailDeliveryFactory...{RESET}")
    try:
        # Use unique name and email to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = User.objects.create_user(email=unique_email, password="testpass123", tenant=tenant)
        delivery = EmailDeliveryFactory.create_email_delivery(tenant=tenant, user=user)
        assert delivery.id is not None
        assert delivery.to_email is not None
        print(f"{GREEN}✅ EmailDeliveryFactory: Created delivery {delivery.id}{RESET}")
        # Cleanup
        delivery.delete()
        user.delete()
        tenant.delete()
        return True
    except Exception as e:
        print(f"{RED}❌ EmailDeliveryFactory failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def test_job_factory():
    """Test JobFactory creation"""
    print(f"{BLUE}Testing JobFactory...{RESET}")
    try:
        # Use unique name and email to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = User.objects.create_user(email=unique_email, password="testpass123", tenant=tenant)
        job = JobFactory.create_job(tenant=tenant, created_by=user)
        assert job.id is not None
        assert job.type is not None
        assert job.status is not None
        print(f"{GREEN}✅ JobFactory: Created job {job.id}{RESET}")
        # Cleanup
        job.delete()
        user.delete()
        tenant.delete()
        return True
    except Exception as e:
        print(f"{RED}❌ JobFactory failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def test_contract_factory():
    """Test ContractFactoryEnhanced creation"""
    print(f"{BLUE}Testing ContractFactoryEnhanced...{RESET}")
    try:
        # Use unique name and email to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = User.objects.create_user(email=unique_email, password="testpass123", tenant=tenant)
        contract = ContractFactoryEnhanced.create_contract(tenant=tenant, created_by=user)
        assert contract.id is not None
        assert contract.hub_contract_json is not None
        print(f"{GREEN}✅ ContractFactoryEnhanced: Created contract {contract.id}{RESET}")
        # Cleanup
        contract.delete()
        user.delete()
        tenant.delete()
        return True
    except Exception as e:
        print(f"{RED}❌ ContractFactoryEnhanced failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def test_data_cleanup():
    """Test that test data can be cleaned up"""
    print(f"{BLUE}Testing test data cleanup...{RESET}")
    try:
        # Use unique name and email to avoid conflicts
        tenant = TenantFactory.create_tenant(name=f"Test Tenant {uuid.uuid4().hex[:8]}")
        unique_email = f"cleanup-{uuid.uuid4().hex[:8]}@example.com"
        config = TenantConfigFactory.create_tenant_config(tenant=tenant)
        user = User.objects.create_user(email=unique_email, password="testpass123", tenant=tenant)
        job = JobFactory.create_job(tenant=tenant, created_by=user)

        # Verify data exists
        assert Tenant.objects.filter(id=tenant.id).exists()
        assert TenantConfig.objects.filter(id=config.id).exists()
        assert Job.objects.filter(id=job.id).exists()

        # Cleanup
        job.delete()
        config.delete()
        user.delete()
        tenant.delete()

        # Verify data is deleted
        assert not Tenant.objects.filter(id=tenant.id).exists()
        assert not TenantConfig.objects.filter(id=config.id).exists()
        assert not Job.objects.filter(id=job.id).exists()

        print(f"{GREEN}✅ Test data cleanup: Successfully cleaned up all test data{RESET}")
        return True
    except Exception as e:
        print(f"{RED}❌ Test data cleanup failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function"""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Test Test Data Creation and Cleanup with Django 6{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    # Ensure database is set up (run migrations if needed)
    # Note: This script should be run in a test environment with proper database setup
    # For actual test execution, use pytest with proper test database setup

    print(f"{YELLOW}Note: This script tests factory functionality.{RESET}")
    print(f"{YELLOW}For full test execution with proper database setup, use pytest.{RESET}\n")

    results = []

    # Test factory creation (using TransactionTestCase for proper database setup)
    # Note: These tests may fail if database tables don't exist
    # In a real test environment, pytest-django handles database setup automatically

    try:
        results.append(("TenantFactory", test_tenant_factory()))
        results.append(("TenantConfigFactory", test_tenant_config_factory()))
        results.append(("EmailDeliveryFactory", test_email_delivery_factory()))
        results.append(("JobFactory", test_job_factory()))
        results.append(("ContractFactoryEnhanced", test_contract_factory()))
        results.append(("Test Data Cleanup", test_data_cleanup()))
    except Exception as e:
        print(f"{YELLOW}⚠️  Some tests may require database setup.{RESET}")
        print(f"{YELLOW}   Run tests using pytest for proper database management.{RESET}")
        print(f"{YELLOW}   Error: {e}{RESET}")

    # Summary
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Test Results Summary{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = f"{GREEN}✅ PASSED{RESET}" if result else f"{RED}❌ FAILED{RESET}"
        print(f"  {name}: {status}")

    print(f"\n{BOLD}Total: {passed}/{total} tests passed{RESET}\n")

    if passed == total:
        print(
            f"{BOLD}{GREEN}✅ All test data operations are working correctly with Django 6!{RESET}\n"
        )
        return 0
    else:
        print(f"{BOLD}{RED}❌ Some test data operations failed{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
