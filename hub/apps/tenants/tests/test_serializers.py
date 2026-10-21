"""
Unit tests for Tenant serializers (hub.apps.tenants.serializers).

Tests TenantSerializer, TenantCreateSerializer, TenantUpdateSerializer,
TenantOnboardingSerializer, TenantSuspendSerializer, TenantReactivateSerializer,
RateLimitsSerializer with real validation. No mocks/stubs.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.tenants.serializers import (
    RateLimitsSerializer,
    TenantCreateSerializer,
    TenantOnboardingSerializer,
    TenantSerializer,
    TenantSuspendSerializer,
    TenantUpdateSerializer,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TenantSerializerTest(TestCase):
    """Test TenantSerializer."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

    def test_serialize_tenant_success(self):
        """Success: serializes tenant instance with status and kyc_status."""
        serializer = TenantSerializer(self.tenant)
        data = serializer.data
        self.assertEqual(data["name"], self.tenant.name)
        self.assertEqual(data["slug"], self.tenant.slug)
        self.assertEqual(data["status"], TenantStatus.ACTIVE)
        self.assertEqual(data["kyc_status"], KYCStatus.UNVERIFIED)

    def test_validate_kyc_status_choice(self):
        """Success: kyc_status accepts VERIFIED."""
        serializer = TenantSerializer(
            self.tenant,
            data={"kyc_status": KYCStatus.VERIFIED},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["kyc_status"],
            KYCStatus.VERIFIED,
        )

    def test_validate_kyc_status_rejects_invalid(self):
        """Failure: kyc_status rejects invalid values."""
        serializer = TenantSerializer(
            self.tenant,
            data={"kyc_status": "BOGUS"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("kyc_status", serializer.errors)


class TenantCreateSerializerTest(TestCase):
    """Test TenantCreateSerializer."""

    def test_valid_data_success(self):
        """Success: valid name, slug, optional region creates tenant."""
        import uuid as _uuid

        _uid = _uuid.uuid4().hex[:8]
        data = {"name": f"New Tenant {_uid}", "slug": f"new-tenant-{_uid}", "region": "us-east-1"}
        serializer = TenantCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        tenant = serializer.save()
        self.assertEqual(tenant.name, f"New Tenant {_uid}")
        self.assertEqual(tenant.slug, f"new-tenant-{_uid}")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)

    def test_slug_normalized_to_lowercase(self):
        """Success: slug is normalized to lowercase."""
        import uuid as _uuid

        _uid = _uuid.uuid4().hex[:8]
        data = {"name": f"New Tenant {_uid}", "slug": f"New-Tenant-{_uid}"}
        serializer = TenantCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        tenant = serializer.save()
        self.assertEqual(tenant.slug, f"new-tenant-{_uid}")

    def test_failure_invalid_slug_rejected(self):
        """Failure: slug with invalid characters fails validation."""
        data = {"name": "New Tenant", "slug": "invalid slug!"}
        serializer = TenantCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("slug", serializer.errors)

    def test_failure_missing_required_field(self):
        """Failure: missing name or slug fails validation."""
        serializer = TenantCreateSerializer(data={"slug": "only-slug"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)


class TenantUpdateSerializerTest(TestCase):
    """Test TenantUpdateSerializer."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

    def test_valid_partial_update_success(self):
        """Success: partial update of name and kyc_status."""
        data = {"name": "Updated Name", "kyc_status": KYCStatus.VERIFIED}
        serializer = TenantUpdateSerializer(self.tenant, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Updated Name")
        self.assertEqual(self.tenant.kyc_status, KYCStatus.VERIFIED)

    def test_failure_invalid_slug_rejected(self):
        """Failure: invalid slug format fails validation."""
        data = {"slug": "Invalid Slug!"}
        serializer = TenantUpdateSerializer(self.tenant, data=data, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("slug", serializer.errors)


class TenantOnboardingSerializerTest(TestCase):
    """Test TenantOnboardingSerializer."""

    def test_valid_data_success(self):
        """Success: valid name, slug, first_user with email and password."""
        data = {
            "name": "Onboard Tenant",
            "slug": "onboard-tenant",
            "plan_slug": "free",
            "first_user": {"email": "admin@example.com", "password": "securepass123"},
        }
        serializer = TenantOnboardingSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_failure_first_user_missing_email(self):
        """Failure: first_user without email fails validation."""
        data = {
            "name": "Onboard Tenant",
            "slug": "onboard-tenant",
            "first_user": {"password": "securepass123"},
        }
        serializer = TenantOnboardingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("first_user", serializer.errors)

    def test_failure_first_user_missing_password(self):
        """Failure: first_user without password fails validation."""
        data = {
            "name": "Onboard Tenant",
            "slug": "onboard-tenant",
            "first_user": {"email": "admin@example.com"},
        }
        serializer = TenantOnboardingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("first_user", serializer.errors)

    def test_failure_invalid_slug_rejected(self):
        """Failure: slug with invalid characters fails validation."""
        data = {
            "name": "Onboard Tenant",
            "slug": "invalid slug!",
            "first_user": {"email": "a@b.com", "password": "pass"},
        }
        serializer = TenantOnboardingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("slug", serializer.errors)


class TenantSuspendSerializerTest(TestCase):
    """Test TenantSuspendSerializer."""

    def test_valid_optional_reason_success(self):
        """Success: reason optional, can be blank."""
        serializer = TenantSuspendSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_with_reason_success(self):
        """Success: reason provided is valid."""
        serializer = TenantSuspendSerializer(data={"reason": "Terms violation"})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class RateLimitsSerializerTest(TestCase):
    """Test RateLimitsSerializer."""

    def test_valid_at_least_one_limit_success(self):
        """Success: at least one of burst_per_10s, sustained_per_min, daily_cap."""
        serializer = RateLimitsSerializer(data={"burst_per_10s": 10})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_failure_empty_dict_fails(self):
        """Failure: empty dict fails (at least one limit required)."""
        serializer = RateLimitsSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
