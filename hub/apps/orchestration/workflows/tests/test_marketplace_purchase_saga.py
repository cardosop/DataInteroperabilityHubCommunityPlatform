"""
Tests for Marketplace Purchase Saga workflow.

These tests verify:
- Saga step execution (order creation, entitlement creation, notification)
- Compensation logic (cancel order, revoke entitlement)
- Error handling and rollback scenarios
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock

from hub.apps.orchestration.workflows.marketplace_purchase_saga import (
    create_order,
    compensate_order_creation,
    create_entitlement,
    compensate_entitlement_creation,
    send_notification,
    execute_marketplace_purchase,
    create_marketplace_purchase_saga
)
from hub.apps.orchestration.saga import (
    SagaStep,
    SagaStepResult,
    SagaOrchestrator,
    SagaExecutionError
)
from hub.apps.marketplace.models import Order, OrderStatus, Entitlement, EntitlementStatus, Listing, ListingStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
import uuid


class MarketplacePurchaseSagaTest(TestCase):
    """Test Marketplace Purchase Saga workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.seller_tenant = Tenant.objects.create(
            name="Seller Tenant",
            slug="seller-tenant",
            kyc_status="VERIFIED"
        )
        self.buyer = User.objects.create_user(
            email=f"buyer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.seller = User.objects.create_user(
            email=f"seller-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.seller_tenant
        )

        # Create an asset first (required for listing)
        from hub.apps.assets.models import Asset, AssetStatus
        self.asset = Asset.objects.create(
            name="Test Asset",
            key="test-asset",
            tenant=self.seller_tenant,
            status=AssetStatus.ACTIVE
        )

        # Create listing
        self.listing = Listing.objects.create(
            asset=self.asset,
            tenant=self.seller_tenant,
            metadata_json={
                "title": "Test Listing",
                "price": 100.00,
                "currency": "USD"
            },
            status=ListingStatus.PUBLISHED
        )

    def test_create_order_success(self):
        """Test order creation step succeeds."""
        result = create_order({
            "listing_id": str(self.listing.id),
            "buyer_id": str(self.buyer.id),
            "tenant_id": str(self.tenant.id)
        })

        self.assertTrue(result.success)
        self.assertIn("order_id", result.output)
        self.assertEqual(result.output["order_status"], OrderStatus.REQUESTED)
        self.assertEqual(float(result.output["price"]), 100.00)

        # Verify order was created
        order = Order.objects.get(id=result.output["order_id"])
        self.assertEqual(order.listing, self.listing)
        self.assertEqual(order.created_by_id, self.buyer.id)
        self.assertEqual(order.status, OrderStatus.REQUESTED)

    def test_create_order_missing_fields(self):
        """Test order creation fails when required fields are missing."""
        result = create_order({
            "listing_id": str(self.listing.id)
            # Missing buyer_id and tenant_id
        })

        self.assertFalse(result.success)
        self.assertIn("required", result.error)

    def test_compensate_order_creation_success(self):
        """Test order creation compensation cancels order."""
        # Create order first
        order = Order.objects.create(
            listing=self.listing,
            tenant_id=self.tenant.id,
            created_by_id=self.buyer.id,
            status=OrderStatus.REQUESTED
        )

        result = compensate_order_creation({
            "order_id": str(order.id),
            "step_output": {
                "order_id": str(order.id),
                "order_status": OrderStatus.REQUESTED
            }
        })

        self.assertTrue(result.success)
        self.assertIn("cancelled", result.output)

        # Verify order was cancelled
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_create_entitlement_success(self):
        """Test entitlement creation step succeeds."""
        # Create order first
        order = Order.objects.create(
            listing=self.listing,
            tenant_id=self.tenant.id,
            created_by_id=self.buyer.id,
            status=OrderStatus.REQUESTED
        )

        result = create_entitlement({
            "order_id": str(order.id),
            "listing_id": str(self.listing.id),
            "buyer_id": str(self.buyer.id),
            "tenant_id": str(self.tenant.id)
        })

        self.assertTrue(result.success)
        self.assertIn("entitlement_id", result.output)
        self.assertEqual(result.output["entitlement_status"], EntitlementStatus.ACTIVE.value)

        # Verify entitlement was created
        entitlement = Entitlement.objects.get(id=result.output["entitlement_id"])
        self.assertEqual(entitlement.order_id, order.id)
        self.assertEqual(entitlement.listing, self.listing)
        self.assertEqual(entitlement.user_id, self.buyer.id)
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)

    def test_create_entitlement_missing_fields(self):
        """Test entitlement creation fails when required fields are missing."""
        result = create_entitlement({
            "order_id": "test-order-id"
            # Missing other fields
        })

        self.assertFalse(result.success)
        self.assertIn("required", result.error)

    def test_compensate_entitlement_creation_success(self):
        """Test entitlement creation compensation revokes entitlement."""
        # Create order and entitlement first
        order = Order.objects.create(
            listing=self.listing,
            tenant_id=self.tenant.id,
            created_by_id=self.buyer.id,
            status=OrderStatus.REQUESTED
        )

        entitlement = Entitlement.objects.create(
            order=order,
            listing=self.listing,
            user_id=self.buyer.id,
            tenant_id=self.tenant.id,
            status=EntitlementStatus.ACTIVE
        )

        result = compensate_entitlement_creation({
            "entitlement_id": str(entitlement.id),
            "step_output": {
                "entitlement_id": str(entitlement.id),
                "entitlement_status": EntitlementStatus.ACTIVE.value
            }
        })

        self.assertTrue(result.success)
        self.assertIn("revoked", result.output)

        # Verify entitlement was revoked
        entitlement.refresh_from_db()
        self.assertEqual(entitlement.status, EntitlementStatus.REVOKED)

    def test_send_notification_success(self):
        """Test notification step succeeds."""
        order = Order.objects.create(
            listing=self.listing,
            tenant_id=self.tenant.id,
            created_by_id=self.buyer.id,
            status=OrderStatus.REQUESTED
        )

        entitlement = Entitlement.objects.create(
            order=order,
            listing=self.listing,
            user_id=self.buyer.id,
            tenant_id=self.tenant.id,
            status=EntitlementStatus.ACTIVE
        )

        result = send_notification({
            "order_id": str(order.id),
            "entitlement_id": str(entitlement.id),
            "buyer_id": str(self.buyer.id),
            "tenant_id": str(self.tenant.id)
        })

        self.assertTrue(result.success)
        self.assertIn("notified", result.output)
        self.assertTrue(result.output["notified"])

    def test_send_notification_failure_non_critical(self):
        """Test notification failure doesn't fail the saga."""
        order = Order.objects.create(
            listing=self.listing,
            tenant_id=self.tenant.id,
            created_by_id=self.buyer.id,
            status=OrderStatus.REQUESTED
        )

        # Mock notification creation to fail
        with patch('hub.apps.orchestration.workflows.marketplace_purchase_saga.Notification.objects.create') as mock_create:
            mock_create.side_effect = Exception("Notification service unavailable")

            result = send_notification({
                "order_id": str(order.id),
                "buyer_id": str(self.buyer.id),
                "tenant_id": str(self.tenant.id)
            })

            # Notification failure is non-critical
            self.assertTrue(result.success)
            self.assertFalse(result.output["notified"])
            self.assertIn("warning", result.output)

    def test_full_saga_execution_success(self):
        """Test full saga execution succeeds when all steps pass."""
        result = execute_marketplace_purchase(
            listing_id=str(self.listing.id),
            buyer_id=str(self.buyer.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("saga_id", result)
        self.assertIn("order_id", result["context"])
        self.assertIn("entitlement_id", result["context"])

        # Verify order was created
        order = Order.objects.get(id=result["context"]["order_id"])
        self.assertEqual(order.status, OrderStatus.REQUESTED)

        # Verify entitlement was created
        entitlement = Entitlement.objects.get(id=result["context"]["entitlement_id"])
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)

    def test_full_saga_execution_failure_order_creation(self):
        """Test saga execution fails and compensates when order creation fails."""
        # Mock order creation to fail
        with patch('hub.apps.orchestration.workflows.marketplace_purchase_saga.Order.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")

            result = execute_marketplace_purchase(
                listing_id=str(self.listing.id),
                buyer_id=str(self.buyer.id),
                tenant_id=str(self.tenant.id)
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "COMPENSATED")
            self.assertIn("error", result)

    def test_full_saga_execution_failure_entitlement_creation(self):
        """Test saga execution fails and compensates when entitlement creation fails."""
        # Mock entitlement creation to fail
        with patch('hub.apps.orchestration.workflows.marketplace_purchase_saga.Entitlement.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")

            result = execute_marketplace_purchase(
                listing_id=str(self.listing.id),
                buyer_id=str(self.buyer.id),
                tenant_id=str(self.tenant.id)
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "COMPENSATED")

            # Verify order was cancelled (compensated)
            orders = Order.objects.filter(listing=self.listing, buyer_id=self.buyer.id)
            if orders.exists():
                order = orders.first()
                self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_create_marketplace_purchase_saga(self):
        """Test saga creation."""
        orchestrator = create_marketplace_purchase_saga(
            listing_id=str(self.listing.id),
            buyer_id=str(self.buyer.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(orchestrator, SagaOrchestrator)
        self.assertEqual(orchestrator.context.state["listing_id"], str(self.listing.id))
        self.assertEqual(orchestrator.context.state["buyer_id"], str(self.buyer.id))
        self.assertEqual(orchestrator.context.state["tenant_id"], str(self.tenant.id))

