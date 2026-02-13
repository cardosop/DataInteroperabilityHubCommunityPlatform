"""
Quick test to validate fixtures work correctly
"""

import pytest
from django.test import TestCase

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.integration,
]


class TestFixturesValidation(TestCase):
    """Test that our centralized fixtures work"""

    def test_tenant_with_plan_fixture(self, tenant_with_plan):
        """Test tenant_with_plan fixture"""
        assert tenant_with_plan is not None
        assert tenant_with_plan.plan is not None
        assert tenant_with_plan.plan.tier == "FREE"
        assert tenant_with_plan.subscriptions.exists()
        subscription = tenant_with_plan.subscriptions.first()
        assert subscription.status == "ACTIVE"

    def test_subscription_fixture(self, tenant_with_plan, subscription):
        """Test subscription fixture"""
        assert subscription is not None
        assert subscription.tenant == tenant_with_plan
        assert subscription.plan == tenant_with_plan.plan
        assert subscription.status == "ACTIVE"

    def test_erasure_request_fixture(self, tenant_with_plan, erasure_request):
        """Test erasure_request fixture"""
        assert erasure_request is not None
        assert erasure_request.tenant == tenant_with_plan
        assert erasure_request.status == "PENDING"

    def test_scheduled_export_factory(self, tenant_with_plan, scheduled_export_factory):
        """Test scheduled_export_factory fixture"""
        export = scheduled_export_factory(tenant=tenant_with_plan)
        assert export is not None
        assert export.tenant == tenant_with_plan
        assert export.status == "ACTIVE"
