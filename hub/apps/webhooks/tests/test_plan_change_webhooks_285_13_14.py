"""
285.13.14.16 — Plan change webhook emission tests.

Verifies that webhook event type constants for plan changes
are properly defined and can be imported by webhook dispatchers.
"""
import pytest

from django.test import TestCase

from hub.apps.webhooks.event_types import (
    TENANT_PLAN_DOWNGRADED,
    TENANT_PLAN_UPGRADED,
    WEBHOOK_EVENT_TYPES,
)

pytestmark = pytest.mark.django_db(transaction=True)


class PlanChangeWebhookEmissionTests(TestCase):
    @pytest.mark.integration
    def test_upgrade_event_type_defined(self):
        assert TENANT_PLAN_UPGRADED == "tenant.plan.upgraded"
        assert isinstance(TENANT_PLAN_UPGRADED, str)
        assert "tenant.plan" in TENANT_PLAN_UPGRADED

    @pytest.mark.integration
    def test_downgrade_event_type_defined(self):
        assert TENANT_PLAN_DOWNGRADED == "tenant.plan.downgraded"
        assert isinstance(TENANT_PLAN_DOWNGRADED, str)
        assert "tenant.plan" in TENANT_PLAN_DOWNGRADED

    @pytest.mark.integration
    def test_both_in_webhook_event_types_tuple(self):
        assert "tenant.plan.upgraded" in WEBHOOK_EVENT_TYPES
        assert "tenant.plan.downgraded" in WEBHOOK_EVENT_TYPES

    @pytest.mark.integration
    def test_event_types_are_distinct(self):
        assert TENANT_PLAN_UPGRADED != TENANT_PLAN_DOWNGRADED

    @pytest.mark.integration
    def test_event_types_follow_dotted_convention(self):
        for ev_type in WEBHOOK_EVENT_TYPES:
            assert "." in ev_type
            assert ev_type.startswith("tenant.")
