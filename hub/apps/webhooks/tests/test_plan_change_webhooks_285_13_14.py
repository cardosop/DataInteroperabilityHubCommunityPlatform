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
        self.assertEqual(TENANT_PLAN_UPGRADED, "tenant.plan.upgraded")
        self.assertIsInstance(TENANT_PLAN_UPGRADED, str)

    @pytest.mark.integration
    def test_downgrade_event_type_defined(self):
        self.assertEqual(TENANT_PLAN_DOWNGRADED, "tenant.plan.downgraded")
        self.assertIsInstance(TENANT_PLAN_DOWNGRADED, str)

    @pytest.mark.integration
    def test_both_in_webhook_event_types_tuple(self):
        self.assertIn("tenant.plan.upgraded", WEBHOOK_EVENT_TYPES)
        self.assertIn("tenant.plan.downgraded", WEBHOOK_EVENT_TYPES)

    @pytest.mark.integration
    def test_event_types_are_distinct(self):
        self.assertNotEqual(TENANT_PLAN_UPGRADED, TENANT_PLAN_DOWNGRADED)

    @pytest.mark.integration
    def test_plan_change_event_types_follow_dotted_convention(self):
        """Plan-change event types follow the ``tenant.plan.<action>`` convention."""
        plan_types = [TENANT_PLAN_UPGRADED, TENANT_PLAN_DOWNGRADED]
        for ev_type in plan_types:
            self.assertIn(".", ev_type)
            self.assertTrue(
                ev_type.startswith("tenant.plan."),
                f"Expected {ev_type} to start with 'tenant.plan.'",
            )
