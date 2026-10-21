"""Unit tests for TenantOnboardingService.

Covers create_tenant_with_first_user() with real DB — no mocks at the
service boundary.  Previously this code path was only exercised through
API views and signal handlers.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase, override_settings

from hub.apps.core.events.models import Event
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import (
    KYCStatus,
    TenantConfig,
    TenantStatus,
)
from hub.apps.tenants.services import TenantOnboardingService

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class CreateTenantWithFirstUserTests(TestCase):
    """Tests for TenantOnboardingService.create_tenant_with_first_user()."""

    def setUp(self):
        super().setUp()
        self.service = TenantOnboardingService(tenant_id=None, user_id=None)
        self.uid = uuid.uuid4().hex[:8]
        self.email = f"onboard-{self.uid}@example.com"

    def test_success_creates_tenant_user_and_subscription(self):
        """Success: returns dict with tenant, user, subscription, and plan."""
        result = self.service.create_tenant_with_first_user(
            name=f"Onboard {self.uid}",
            slug=f"onboard-{self.uid}",
            plan_slug="free",
            first_user_email=self.email,
            first_user_password="testpass123",
            first_user_display_name="Test User",
        )
        self.assertIn("tenant", result)
        self.assertIn("user", result)
        self.assertIn("subscription", result)
        self.assertIn("plan", result)
        tenant = result["tenant"]
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        # Asset creation starts gated for new onboarding tenants.
        self.assertFalse(tenant.asset_creation_enabled)
        # TenantConfig should be created automatically.
        self.assertTrue(
            TenantConfig.objects.filter(tenant=tenant).exists(),
        )
        # Event should be published.
        self.assertTrue(
            Event.objects.filter(event_type="tenant.created").exists(),
        )

    def test_missing_email_raises_validation_error(self):
        """Failure: first_user_email is required."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.create_tenant_with_first_user(
                name="Test",
                slug=f"test-{self.uid}",
                first_user_password="testpass123",
            )
        self.assertIn("email", str(exc_info.value).lower())

    def test_missing_password_raises_validation_error(self):
        """Failure: first_user_password is required."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.create_tenant_with_first_user(
                name="Test",
                slug=f"test-{self.uid}",
                first_user_email=self.email,
            )
        self.assertIn("password", str(exc_info.value).lower())

    def test_plan_not_found_raises_not_found(self):
        """Failure: nonexistent plan_slug raises NotFoundError."""
        with pytest.raises(NotFoundError):
            self.service.create_tenant_with_first_user(
                name="Test",
                slug=f"test-{self.uid}",
                plan_slug="nonexistent-plan-999",
                first_user_email=self.email,
                first_user_password="testpass123",
            )

    def test_duplicate_slug_raises_validation_error(self):
        """Failure: duplicate slug raises ValidationError with SLUG_EXISTS."""
        self.service.create_tenant_with_first_user(
            name="First",
            slug=f"dup-{self.uid}",
            first_user_email=f"first-{self.uid}@example.com",
            first_user_password="testpass123",
        )
        with pytest.raises(ValidationError) as exc_info:
            self.service.create_tenant_with_first_user(
                name="Second",
                slug=f"dup-{self.uid}",
                first_user_email=f"second-{self.uid}@example.com",
                first_user_password="testpass123",
            )
        self.assertIn("already exists", str(exc_info.value).lower())

    def test_duplicate_email_raises_validation_error(self):
        """Failure: duplicate email raises ValidationError with EMAIL_EXISTS."""
        self.service.create_tenant_with_first_user(
            name="First",
            slug=f"first-{self.uid}",
            first_user_email=self.email,
            first_user_password="testpass123",
        )
        with pytest.raises(ValidationError) as exc_info:
            self.service.create_tenant_with_first_user(
                name="Second",
                slug=f"second-{self.uid}",
                first_user_email=self.email,
                first_user_password="testpass123",
            )
        self.assertIn("already registered", str(exc_info.value).lower())
