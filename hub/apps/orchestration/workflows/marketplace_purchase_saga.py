"""
Marketplace Purchase Saga Workflow

Implements marketplace purchase using the Saga pattern with the following steps:
1. Order creation
2. Entitlement creation
3. Notification

Compensation:
- Cancel order
- Revoke entitlement
"""
import logging
from typing import Dict, Any

from hub.apps.orchestration.saga import (
    SagaStep,
    SagaStepResult,
    SagaOrchestrator,
    SagaExecutionError
)
from hub.apps.marketplace.models import Order, OrderStatus, Entitlement, EntitlementStatus, ListingStatus

logger = logging.getLogger(__name__)


def create_order(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 1: Create order for marketplace purchase.

    Args:
        input_data: Contains 'listing_id', 'buyer_id', 'tenant_id', and order details

    Returns:
        SagaStepResult with order creation result
    """
    listing_id = input_data.get('listing_id')
    buyer_id = input_data.get('buyer_id')
    tenant_id = input_data.get('tenant_id')

    if not listing_id:
        return SagaStepResult.failure_result("listing_id is required")
    if not buyer_id:
        return SagaStepResult.failure_result("buyer_id is required")
    if not tenant_id:
        return SagaStepResult.failure_result("tenant_id is required")

    try:
        from hub.apps.marketplace.models import Listing

        listing = Listing.objects.get(id=listing_id)

        # Get price from listing metadata for logging
        price = 0
        currency = "USD"
        if listing.metadata_json:
            price = listing.metadata_json.get("price", 0) or 0
            currency = listing.metadata_json.get("currency", "USD") or "USD"

        # Create order (Order model doesn't have amount/currency fields directly)
        order = Order.objects.create(
            listing=listing,
            tenant_id=tenant_id,
            created_by_id=buyer_id,
            status=OrderStatus.REQUESTED
        )

        logger.info(
            "marketplace_purchase_order_created",
            extra={
                "order_id": str(order.id),
                "listing_id": str(listing_id),
                "buyer_id": str(buyer_id),
                "tenant_id": str(tenant_id),
                "price": price,
                "currency": currency
            }
        )

        return SagaStepResult.success_result({
            "order_id": str(order.id),
            "listing_id": str(listing_id),
            "order_status": order.status,
            "price": float(price),
            "currency": currency
        })

    except Exception as e:
        logger.exception("marketplace_purchase_order_creation_error")
        return SagaStepResult.failure_result(
            f"Order creation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_order_creation(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for order creation: cancel order.

    Args:
        input_data: Contains 'order_id' and step output

    Returns:
        SagaStepResult with compensation result
    """
    order_id = input_data.get('order_id') or input_data.get('step_output', {}).get('order_id')

    if not order_id:
        return SagaStepResult.success_result({
            "warning": "No order_id found for compensation"
        })

    try:
        order = Order.objects.get(id=order_id)

        # Cancel order
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=['status', 'updated_at'])

        logger.info(
            "marketplace_purchase_order_cancelled",
            extra={
                "order_id": str(order_id),
                "original_status": input_data.get('step_output', {}).get('order_status'),
                "new_status": order.status.value
            }
        )

        return SagaStepResult.success_result({
            "order_id": str(order_id),
            "cancelled": True,
            "status": order.status.value
        })

    except Order.DoesNotExist:
        logger.warning(
            "marketplace_purchase_order_compensation_not_found",
            extra={"order_id": str(order_id)}
        )
        return SagaStepResult.success_result({
            "warning": "Order not found during compensation",
            "order_id": str(order_id)
        })
    except Exception as e:
        logger.exception("marketplace_purchase_order_compensation_error")
        return SagaStepResult.failure_result(
            f"Order cancellation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def create_entitlement(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 2: Create entitlement for the purchase.

    Args:
        input_data: Contains 'order_id', 'listing_id', 'buyer_id', 'tenant_id'

    Returns:
        SagaStepResult with entitlement creation result
    """
    order_id = input_data.get('order_id')
    listing_id = input_data.get('listing_id')
    buyer_id = input_data.get('buyer_id')
    tenant_id = input_data.get('tenant_id')

    if not order_id:
        return SagaStepResult.failure_result("order_id is required")
    if not listing_id:
        return SagaStepResult.failure_result("listing_id is required")
    if not buyer_id:
        return SagaStepResult.failure_result("buyer_id is required")
    if not tenant_id:
        return SagaStepResult.failure_result("tenant_id is required")

    try:
        from hub.apps.marketplace.models import Listing

        listing = Listing.objects.get(id=listing_id)

        # Create entitlement
        entitlement = Entitlement.objects.create(
            order_id=order_id,
            listing=listing,
            asset=listing.asset,
            tenant_id=tenant_id,
            status=EntitlementStatus.ACTIVE,
            expires_at=None  # Can be set based on listing configuration
        )

        logger.info(
            "marketplace_purchase_entitlement_created",
            extra={
                "entitlement_id": str(entitlement.id),
                "order_id": str(order_id),
                "listing_id": str(listing_id),
                "buyer_id": str(buyer_id),
                "tenant_id": str(tenant_id)
            }
        )

        return SagaStepResult.success_result({
            "entitlement_id": str(entitlement.id),
            "order_id": str(order_id),
            "entitlement_status": entitlement.status.value
        })

    except Exception as e:
        logger.exception("marketplace_purchase_entitlement_creation_error")
        return SagaStepResult.failure_result(
            f"Entitlement creation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def compensate_entitlement_creation(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for entitlement creation: revoke entitlement.

    Args:
        input_data: Contains 'entitlement_id' and step output

    Returns:
        SagaStepResult with compensation result
    """
    entitlement_id = input_data.get('entitlement_id') or input_data.get('step_output', {}).get('entitlement_id')

    if not entitlement_id:
        return SagaStepResult.success_result({
            "warning": "No entitlement_id found for compensation"
        })

    try:
        entitlement = Entitlement.objects.get(id=entitlement_id)

        # Revoke entitlement
        entitlement.status = EntitlementStatus.REVOKED
        entitlement.save(update_fields=['status', 'updated_at'])

        logger.info(
            "marketplace_purchase_entitlement_revoked",
            extra={
                "entitlement_id": str(entitlement_id),
                "original_status": input_data.get('step_output', {}).get('entitlement_status'),
                "new_status": entitlement.status.value
            }
        )

        return SagaStepResult.success_result({
            "entitlement_id": str(entitlement_id),
            "revoked": True,
            "status": entitlement.status.value
        })

    except Entitlement.DoesNotExist:
        logger.warning(
            "marketplace_purchase_entitlement_compensation_not_found",
            extra={"entitlement_id": str(entitlement_id)}
        )
        return SagaStepResult.success_result({
            "warning": "Entitlement not found during compensation",
            "entitlement_id": str(entitlement_id)
        })
    except Exception as e:
        logger.exception("marketplace_purchase_entitlement_compensation_error")
        return SagaStepResult.failure_result(
            f"Entitlement revocation failed: {str(e)}",
            {"exception_type": type(e).__name__}
        )


def send_notification(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Step 3: Send notification about the purchase.

    Args:
        input_data: Contains 'order_id', 'entitlement_id', 'buyer_id', 'tenant_id'

    Returns:
        SagaStepResult with notification result
    """
    order_id = input_data.get('order_id')
    entitlement_id = input_data.get('entitlement_id')
    buyer_id = input_data.get('buyer_id')
    tenant_id = input_data.get('tenant_id')

    if not order_id:
        return SagaStepResult.failure_result("order_id is required")
    if not buyer_id:
        return SagaStepResult.failure_result("buyer_id is required")

    try:
        # Log notification (actual notification can be sent via event bus or email service)
        logger.info(
            "marketplace_purchase_notification",
            extra={
                "order_id": str(order_id),
                "entitlement_id": str(entitlement_id) if entitlement_id else None,
                "buyer_id": str(buyer_id),
                "tenant_id": str(tenant_id),
                "detail": f"Purchase completed for Order #{order_id[:8]}"
            }
        )

        # In a real implementation, this would trigger an event or send an email
        # For now, we just log it as the notification step is non-critical

        return SagaStepResult.success_result({
            "order_id": str(order_id),
            "entitlement_id": str(entitlement_id) if entitlement_id else None,
            "notified": True
        })

    except Exception as e:
        logger.exception("marketplace_purchase_notification_error")
        # Notification failure is not critical - log but don't fail the saga
        return SagaStepResult.success_result({
            "order_id": str(order_id),
            "notified": False,
            "warning": f"Notification failed but continuing: {str(e)}"
        })


def compensate_notification(input_data: Dict[str, Any]) -> SagaStepResult:
    """
    Compensation for notification step.

    Notifications are idempotent and don't require compensation.
    Optionally, we could send a cancellation notification.
    """
    order_id = input_data.get('order_id') or input_data.get('step_output', {}).get('order_id')

    if order_id:
        logger.info(
            "marketplace_purchase_notification_compensated",
            extra={
                "order_id": str(order_id),
                "message": "Purchase notification compensation logged"
            }
        )

    return SagaStepResult.success_result()


def create_marketplace_purchase_saga(
    listing_id: str,
    buyer_id: str,
    tenant_id: str
) -> SagaOrchestrator:
    """
    Create and configure marketplace purchase saga.

    Args:
        listing_id: ID of the listing being purchased
        buyer_id: ID of the buyer
        tenant_id: ID of the buyer's tenant

    Returns:
        Configured SagaOrchestrator instance
    """
    orchestrator = SagaOrchestrator()
    orchestrator.context.state = {
        "listing_id": listing_id,
        "buyer_id": buyer_id,
        "tenant_id": tenant_id
    }

    return orchestrator


def execute_marketplace_purchase(
    listing_id: str,
    buyer_id: str,
    tenant_id: str
) -> Dict[str, Any]:
    """
    Execute marketplace purchase saga workflow.

    Args:
        listing_id: ID of the listing being purchased
        buyer_id: ID of the buyer
        tenant_id: ID of the buyer's tenant

    Returns:
        Dictionary with execution results

    Raises:
        SagaExecutionError: If purchase fails
    """
    orchestrator = create_marketplace_purchase_saga(listing_id, buyer_id, tenant_id)

    steps = [
        SagaStep(
            name="create_order",
            forward_action=create_order,
            compensation_action=compensate_order_creation,
            description="Create order for marketplace purchase"
        ),
        SagaStep(
            name="create_entitlement",
            forward_action=create_entitlement,
            compensation_action=compensate_entitlement_creation,
            description="Create entitlement for the purchase"
        ),
        SagaStep(
            name="send_notification",
            forward_action=send_notification,
            compensation_action=compensate_notification,
            description="Send notification about the purchase"
        )
    ]

    try:
        context = orchestrator.execute(
            steps,
            initial_state={
                "listing_id": listing_id,
                "buyer_id": buyer_id,
                "tenant_id": tenant_id
            }
        )

        return {
            "success": True,
            "saga_id": orchestrator.saga_id,
            "status": orchestrator.status.value,
            "context": {
                "order_id": context.state.get("order_id"),
                "entitlement_id": context.state.get("entitlement_id"),
                "final_state": context.state
            }
        }
    except SagaExecutionError as e:
        logger.error(
            "marketplace_purchase_saga_failed",
            extra={
                "saga_id": orchestrator.saga_id,
                "listing_id": listing_id,
                "buyer_id": buyer_id,
                "error": str(e)
            }
        )
        return {
            "success": False,
            "saga_id": orchestrator.saga_id,
            "status": orchestrator.status.value,
            "error": str(e),
            "context": orchestrator.context
        }

