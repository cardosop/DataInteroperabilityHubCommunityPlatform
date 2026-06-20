"""
Unit tests for PersonalTenantService (hub.apps.tenants.services).

Tests create_personal_tenant_for_user with real DB. No mocks/stubs.
"""

import uuid

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.core.events.models import Event
from hub.apps.core.services.base import NotFoundError
from hub.apps.tenants.models import (
    KYCStatus,
    PlanTier,
    Tenant,
    TenantConfig,
    TenantPlan,
    TenantStatus,
)
from hub.apps.tenants.services import PersonalTenantService
from hub.apps.users.models import Role

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class PersonalTenantServiceTest(TestCase):
    """Test PersonalTenantService.create_personal_tenant_for_user with real DB."""

    def setUp(self):
        """Ensure FREE plan exists (no mocks - use real seed or create)."""
        call_command("seed_default_plans")

    def test_create_personal_tenant_creates_tenant(self):
        """Success: create_personal_tenant_for_user creates a Tenant."""
        service = PersonalTenantService()
        email = f"alice-{uuid.uuid4().hex[:8]}@example.com"
        tenant = service.create_personal_tenant_for_user(
            email=email,
            display_name="Alice",
        )
        self.assertIsInstance(tenant, Tenant)
        self.assertEqual(tenant.name, f"Personal - {email}")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        self.assertIsNotNone(tenant.id)
        self.assertTrue(tenant.slug.startswith("personal-"))

    def test_assigns_free_plan(self):
        """Success: tenant is assigned FREE plan."""
        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"bob-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Bob",
        )
        self.assertIsNotNone(tenant.plan)
        self.assertEqual(tenant.plan.slug, "free")
        self.assertEqual(tenant.plan.tier, PlanTier.FREE)

    def test_creates_tenant_config(self):
        """Success: TenantConfig is created with platform defaults."""
        from hub.apps.tenants.validators import get_platform_defaults

        defaults = get_platform_defaults()

        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"carol-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Carol",
        )
        config = TenantConfig.objects.get(tenant=tenant)
        self.assertIsNotNone(config)
        self.assertEqual(
            config.default_dq_profile,
            defaults["default_dq_profile"],
        )
        self.assertEqual(
            config.allowed_compliance_regimes,
            defaults["allowed_compliance_regimes"],
        )
        self.assertIsInstance(config.rate_limits, dict)
        self.assertGreater(len(config.rate_limits), 0)

    def test_creates_subscription(self):
        """Success: Subscription is created with ACTIVE status."""
        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"dave-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Dave",
        )
        subscription = Subscription.objects.get(tenant=tenant)
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(subscription.plan.slug, "free")

    def test_slug_format(self):
        """Success: slug follows personal-{uuid8} format (lowercase, 8 hex chars)."""
        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"eve-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Eve",
        )
        self.assertTrue(tenant.slug.startswith("personal-"))
        suffix = tenant.slug[len("personal-") :]
        self.assertEqual(len(suffix), 8)
        hex_chars = "0123456789abcdef"
        self.assertTrue(
            all(c in hex_chars for c in suffix),
            f"Slug suffix {suffix} must be 8 hex chars",
        )

    def test_roles_exist(self):
        """Success: DATA_PROVIDER and DATA_CONSUMER roles exist for the tenant."""
        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"frank-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Frank",
        )
        data_provider = Role.objects.filter(tenant=tenant, name="DATA_PROVIDER").first()
        data_consumer = Role.objects.filter(tenant=tenant, name="DATA_CONSUMER").first()
        self.assertIsNotNone(data_provider, "DATA_PROVIDER role must exist")
        self.assertIsNotNone(data_consumer, "DATA_CONSUMER role must exist")

    def test_free_plan_missing_raises_clear_error(self):
        """Failure: when no FREE plan exists, service raises NotFoundError."""
        from unittest.mock import patch

        # Bypass the conftest auto-seed patch by making the real
        # TenantPlan.objects.get raise DoesNotExist for slug="free".
        def fake_get(*args, **kwargs):
            if kwargs.get("slug") == "free":
                raise TenantPlan.DoesNotExist("No FREE plan")
            return TenantPlan.objects.filter(**kwargs).get()

        service = PersonalTenantService()
        with (
            patch.object(
                type(TenantPlan.objects),
                "get",
                fake_get,
            ),
            self.assertRaises(NotFoundError) as cm,
        ):
            service.create_personal_tenant_for_user(
                email=f"no-plan-{uuid.uuid4().hex[:8]}@x.com",
                display_name="NoPlan",
            )
        self.assertIn(
            "free",
            str(cm.exception).lower(),
            "Error should mention the missing free plan",
        )

    def test_publishes_tenant_created_event(self):
        """Success: create_personal_tenant_for_user publishes tenant.created event."""
        service = PersonalTenantService()
        tenant = service.create_personal_tenant_for_user(
            email=f"event-test-{uuid.uuid4().hex[:8]}@example.com",
            display_name="EventTest",
        )
        events = Event.objects.filter(
            event_type="tenant.created",
            data__tenant_id=str(tenant.id),
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertEqual(event.data["name"], tenant.name)
        self.assertEqual(event.data["slug"], tenant.slug)
        self.assertEqual(event.data["status"], tenant.status)
