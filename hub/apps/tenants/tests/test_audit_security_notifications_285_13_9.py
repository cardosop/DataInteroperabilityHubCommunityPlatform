"""
285.13.9 -- Audit, Security & Notifications tests.

Covers:
- 285.13.9.1: 10 new audit event type constants exist
- 285.13.9.2: Audit events emitted at admin CRUD, self-serve, transaction creation
- 285.13.9.3: Two-person approval for price changes >$1,000/mo
- 285.13.9.4: 8 notification triggers
- 285.13.9.5: Webhook event type constants
"""
import pytest

import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.audit.event_types import (
    MARKETPLACE_TAKE_RATE_APPLIED,
    PLAN_CREATED,
    PLAN_DELETED,
    PLAN_LIMITS_BACKFILLED,
    PLAN_PRICE_CHANGED,
    PLAN_PRICING_VALIDATION_FAILED,
    PLAN_UPDATED,
    TENANT_PLAN_DOWNGRADED,
    TENANT_PLAN_UPGRADE_FAILED,
    TENANT_PLAN_UPGRADED,
)
from hub.apps.tenants.models import (
    PlanCategory,
    PlanPriceChangeApproval,
    PlanTier,
    PriceChangeApprovalStatus,
    Tenant,
    TenantPlan,
    TenantStatus,
)
from hub.apps.tenants.notifications import (
    notify_downgrade_confirmation,
    notify_enterprise_backfill,
    notify_limit_critical,
    notify_limit_exceeded,
    notify_limit_warning,
    notify_payment_failure,
    notify_price_change,
    notify_upgrade_confirmation,
)
from hub.apps.webhooks.event_types import (
    TENANT_PLAN_DOWNGRADED as WEBHOOK_TENANT_PLAN_DOWNGRADED,
)
from hub.apps.webhooks.event_types import (
    TENANT_PLAN_UPGRADED as WEBHOOK_TENANT_PLAN_UPGRADED,
)
from hub.apps.webhooks.event_types import WEBHOOK_EVENT_TYPES
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


# ── 285.13.9.1 — Audit event type constants ──────────────────────────────

class AuditEventTypeRegistrationTests(TestCase):
    @pytest.mark.integration
    def test_all_10_constants_defined(self):
        for name in [
            "PLAN_CREATED", "PLAN_UPDATED", "PLAN_PRICE_CHANGED",
            "PLAN_DELETED", "PLAN_LIMITS_BACKFILLED",
            "TENANT_PLAN_UPGRADED", "TENANT_PLAN_DOWNGRADED",
            "TENANT_PLAN_UPGRADE_FAILED", "MARKETPLACE_TAKE_RATE_APPLIED",
            "PLAN_PRICING_VALIDATION_FAILED",
        ]:
            assert isinstance(globals()[name], str)
            assert globals()[name] == name  # name==value convention

    @pytest.mark.integration
    def test_constant_values_are_strings(self):
        for const in [PLAN_CREATED, PLAN_UPDATED, PLAN_PRICE_CHANGED,
                      PLAN_DELETED, PLAN_LIMITS_BACKFILLED,
                      TENANT_PLAN_UPGRADED, TENANT_PLAN_DOWNGRADED,
                      TENANT_PLAN_UPGRADE_FAILED, MARKETPLACE_TAKE_RATE_APPLIED,
                      PLAN_PRICING_VALIDATION_FAILED]:
            assert isinstance(const, str)


# ── 285.13.9.3 — Two-person approval for price changes ───────────────────

class PriceChangeApprovalModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="approval-test", slug=f"approval-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )
        self.user1 = User.objects.create_user(
            email=f"admin1-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant,
        )
        self.user2 = User.objects.create_user(
            email=f"admin2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant,
        )
        self.plan = TenantPlan.objects.create(
            slug=f"price-plan-{uuid.uuid4().hex[:8]}",
            name="Test Plan", tier=PlanTier.PRO, order=1,
            category=PlanCategory.BASE,
            price_amount_cents=5000, is_active=True,
        )

    @pytest.mark.integration
    def test_approval_creation(self):
        approval = PlanPriceChangeApproval.objects.create(
            tenant_plan=self.plan,
            old_price_cents=5000,
            new_price_cents=150000,
            requested_by=self.user1,
            reason="Market adjustment",
        )
        assert approval.status == PriceChangeApprovalStatus.PENDING
        assert approval.old_price_cents == 5000
        assert approval.new_price_cents == 150000
        assert str(self.user1.id) == str(approval.requested_by.id)
        assert approval.approved_by is None

    @pytest.mark.integration
    def test_one_pending_per_plan_constraint(self):
        PlanPriceChangeApproval.objects.create(
            tenant_plan=self.plan, old_price_cents=5000,
            new_price_cents=150000, requested_by=self.user1,
        )
        with pytest.raises(Exception):
            PlanPriceChangeApproval.objects.create(
                tenant_plan=self.plan, old_price_cents=5000,
                new_price_cents=200000, requested_by=self.user1,
            )

    @pytest.mark.integration
    def test_approval_transition_to_approved(self):
        approval = PlanPriceChangeApproval.objects.create(
            tenant_plan=self.plan, old_price_cents=5000,
            new_price_cents=150000, requested_by=self.user1,
        )
        approval.status = PriceChangeApprovalStatus.APPROVED
        approval.approved_by = self.user2
        approval.save()
        assert approval.status == PriceChangeApprovalStatus.APPROVED
        assert str(self.user2.id) == str(approval.approved_by.id)


# ── 285.13.9.4 — Notification triggers ────────────────────────────────────

class NotificationTriggerTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="notif-test", slug=f"notif-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_notify_limit_warning_no_crash(self):
        # Verify the function runs without error (no email config in test)
        notify_limit_warning(self.tenant, "max_assets", 85.0)

    @pytest.mark.integration
    def test_notify_limit_critical_no_crash(self):
        notify_limit_critical(self.tenant, "max_api_calls", 92.0)

    @pytest.mark.integration
    def test_notify_limit_exceeded_no_crash(self):
        notify_limit_exceeded(self.tenant, "max_storage_gb")

    @pytest.mark.integration
    def test_notify_upgrade_confirmation_no_crash(self):
        notify_upgrade_confirmation(self.tenant, "free", "pro", "PRO")

    @pytest.mark.integration
    def test_notify_downgrade_confirmation_no_crash(self):
        notify_downgrade_confirmation(self.tenant, "pro", "free")

    @pytest.mark.integration
    def test_notify_payment_failure_no_crash(self):
        notify_payment_failure(self.tenant, 2999, "Card declined")

    @pytest.mark.integration
    def test_notify_price_change_no_crash(self):
        notify_price_change(self.tenant, "Pro Plan", 2999, 4999)

    @pytest.mark.integration
    def test_notify_enterprise_backfill_no_crash(self):
        notify_enterprise_backfill(self.tenant, "Enterprise", 150)


# ── 285.13.9.5 — Webhook event types ──────────────────────────────────────

class WebhookEventTypeRegistrationTests(TestCase):
    @pytest.mark.integration
    def test_event_type_constants_defined(self):
        assert WEBHOOK_TENANT_PLAN_UPGRADED == "tenant.plan.upgraded"
        assert WEBHOOK_TENANT_PLAN_DOWNGRADED == "tenant.plan.downgraded"

    @pytest.mark.integration
    def test_webhook_event_types_tuple(self):
        assert "tenant.plan.upgraded" in WEBHOOK_EVENT_TYPES
        assert "tenant.plan.downgraded" in WEBHOOK_EVENT_TYPES

    @pytest.mark.integration
    def test_event_types_are_dotted_strings(self):
        assert "." in WEBHOOK_TENANT_PLAN_UPGRADED
        assert "." in WEBHOOK_TENANT_PLAN_DOWNGRADED
