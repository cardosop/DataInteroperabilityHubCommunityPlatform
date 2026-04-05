"""
ODPS Event Subscribers

Event subscribers for ODPS (Open Data Product Standard) events.
Handles subscriptions for:
- Semantic service (odps.created, odps.updated)
- Marketplace service (odps.linked, odps.updated)
- Asset service (odps.linked)
- Notification service (odps.*)
- Audit service (odps.*)
"""
from typing import Dict, Any, Optional
import structlog
from django.db import transaction

from .subscriber import event_subscriber

logger = structlog.get_logger(__name__)


# Semantic Service Subscriber
@event_subscriber("semantic_service", "odps.created")
def handle_odps_created_for_semantic(event: Dict[str, Any]) -> None:
    """
    Handle odps.created event for semantic service.

    Maps the ODPS product to RDF and stores it in the triple store.
    """
    try:
        event_data = event.get("data", {})
        contract_id = event_data.get("contract_id")
        asset_id = event_data.get("asset_id")

        if not contract_id:
            logger.warning(
                "odps_created_missing_contract_id",
                event_id=event.get("event_id"),
                event_type=event.get("event_type")
            )
            return

        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.semantic.service_client import SemanticServiceClient

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            logger.warning(
                "odps_created_contract_not_found",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )
            return

        # Extract ODPS product from contract
        # ODPS contracts have the product in hub_contract_json.product
        hub_contract = contract.hub_contract_json or {}
        product = hub_contract.get("product")

        if not product:
            logger.warning(
                "odps_created_no_product_in_contract",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )
            return

        # Get linked ODCS contract ID if available
        odcs_contract_id = None
        if contract.hub_contract_json:
            extensions = contract.hub_contract_json.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            odcs_link = x_odps.get("odcs_link")
            if odcs_link:
                odcs_contract_id = str(odcs_link)

        # Map ODPS to RDF via semantic service
        client = SemanticServiceClient()
        result = client.map_odps(
            product=product,
            product_uuid=str(contract_id),
            odcs_contract_uuid=odcs_contract_id
        )

        if result.get("semantic_status") == "OK":
            logger.info(
                "odps_semantic_mapping_success",
                contract_id=contract_id,
                product_uri=result.get("product_uri"),
                triples_count=result.get("triples_count"),
                event_id=event.get("event_id")
            )
        else:
            logger.warning(
                "odps_semantic_mapping_degraded",
                contract_id=contract_id,
                semantic_status=result.get("semantic_status"),
                error=result.get("error"),
                event_id=event.get("event_id")
            )

    except Exception as e:
        logger.error(
            "odps_created_semantic_handler_error",
            contract_id=event_data.get("contract_id") if 'event_data' in locals() else None,
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


@event_subscriber("semantic_service", "odps.updated")
def handle_odps_updated_for_semantic(event: Dict[str, Any]) -> None:
    """
    Handle odps.updated event for semantic service.

    Re-maps the updated ODPS product to RDF.
    """
    try:
        event_data = event.get("data", {})
        contract_id = event_data.get("contract_id")

        if not contract_id:
            logger.warning(
                "odps_updated_missing_contract_id",
                event_id=event.get("event_id"),
                event_type=event.get("event_type")
            )
            return

        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.semantic.service_client import SemanticServiceClient

        # Get contract
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            logger.warning(
                "odps_updated_contract_not_found",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )
            return

        # Extract ODPS product from contract
        hub_contract = contract.hub_contract_json or {}
        product = hub_contract.get("product")

        if not product:
            logger.warning(
                "odps_updated_no_product_in_contract",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )
            return

        # Get linked ODCS contract ID if available
        odcs_contract_id = None
        if contract.hub_contract_json:
            extensions = contract.hub_contract_json.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            odcs_link = x_odps.get("odcs_link")
            if odcs_link:
                odcs_contract_id = str(odcs_link)

        # Re-map ODPS to RDF via semantic service
        client = SemanticServiceClient()
        result = client.map_odps(
            product=product,
            product_uuid=str(contract_id),
            odcs_contract_uuid=odcs_contract_id
        )

        if result.get("semantic_status") == "OK":
            logger.info(
                "odps_updated_semantic_mapping_success",
                contract_id=contract_id,
                product_uri=result.get("product_uri"),
                triples_count=result.get("triples_count"),
                event_id=event.get("event_id")
            )
        else:
            logger.warning(
                "odps_updated_semantic_mapping_degraded",
                contract_id=contract_id,
                semantic_status=result.get("semantic_status"),
                error=result.get("error"),
                event_id=event.get("event_id")
            )

    except Exception as e:
        logger.error(
            "odps_updated_semantic_handler_error",
            contract_id=event_data.get("contract_id") if 'event_data' in locals() else None,
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


# Marketplace Service Subscriber
@event_subscriber("marketplace_service", "odps.linked")
def handle_odps_linked_for_marketplace(event: Dict[str, Any]) -> None:
    """
    Handle odps.linked event for marketplace service.

    Updates marketplace listings when ODPS contracts are linked to ODCS contracts.
    """
    try:
        event_data = event.get("data", {})
        odps_contract_id = event_data.get("odps_contract_id")
        odcs_contract_id = event_data.get("odcs_contract_id")

        if not odps_contract_id or not odcs_contract_id:
            logger.warning(
                "odps_linked_missing_contract_ids",
                event_id=event.get("event_id"),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id
            )
            return

        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.marketplace.models import Listing
        from hub.apps.marketplace.services import MarketplaceService

        # Get ODPS contract to find associated asset
        try:
            odps_contract = Contract.objects.get(id=odps_contract_id)
        except Contract.DoesNotExist:
            logger.warning(
                "odps_linked_odps_contract_not_found",
                odps_contract_id=odps_contract_id,
                event_id=event.get("event_id")
            )
            return

        # Find marketplace listings for the asset
        if odps_contract.asset:
            listings = Listing.objects.filter(
                asset=odps_contract.asset,
                status__in=["PUBLISHED", "DRAFT"]
            )

            # Update listings to reflect ODPS-ODCS linkage
            # This could trigger listing metadata updates, pricing sync, etc.
            for listing in listings:
                # Marketplace service can handle listing updates
                # For now, we just log the linkage
                logger.info(
                    "odps_linked_marketplace_listing_updated",
                    listing_id=str(listing.id),
                    asset_id=str(odps_contract.asset.id),
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=odcs_contract_id,
                    event_id=event.get("event_id")
                )
        else:
            logger.debug(
                "odps_linked_no_asset",
                odps_contract_id=odps_contract_id,
                event_id=event.get("event_id")
            )

    except Exception as e:
        logger.error(
            "odps_linked_marketplace_handler_error",
            odps_contract_id=event_data.get("odps_contract_id") if 'event_data' in locals() else None,
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


@event_subscriber("marketplace_service", "odps.updated")
def handle_odps_updated_for_marketplace(event: Dict[str, Any]) -> None:
    """
    Handle odps.updated event for marketplace service.

    Updates marketplace listings when ODPS contracts are updated.
    """
    try:
        event_data = event.get("data", {})
        contract_id = event_data.get("contract_id")

        if not contract_id:
            logger.warning(
                "odps_updated_marketplace_missing_contract_id",
                event_id=event.get("event_id"),
                event_type=event.get("event_type")
            )
            return

        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.marketplace.models import Listing

        # Get contract to find associated asset
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            logger.warning(
                "odps_updated_marketplace_contract_not_found",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )
            return

        # Find marketplace listings for the asset
        if contract.asset:
            listings = Listing.objects.filter(
                asset=contract.asset,
                status__in=["PUBLISHED", "DRAFT"]
            )

            # Update listings to reflect ODPS changes
            for listing in listings:
                logger.info(
                    "odps_updated_marketplace_listing_updated",
                    listing_id=str(listing.id),
                    asset_id=str(contract.asset.id),
                    contract_id=contract_id,
                    changes=event_data.get("changes", {}),
                    event_id=event.get("event_id")
                )
        else:
            logger.debug(
                "odps_updated_marketplace_no_asset",
                contract_id=contract_id,
                event_id=event.get("event_id")
            )

    except Exception as e:
        logger.error(
            "odps_updated_marketplace_handler_error",
            contract_id=event_data.get("contract_id") if 'event_data' in locals() else None,
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


# Asset Service Subscriber
@event_subscriber("asset_service", "odps.linked")
def handle_odps_linked_for_asset(event: Dict[str, Any]) -> None:
    """
    Handle odps.linked event for asset service.

    Updates asset metadata when ODPS contracts are linked to ODCS contracts.
    """
    try:
        event_data = event.get("data", {})
        odps_contract_id = event_data.get("odps_contract_id")
        odcs_contract_id = event_data.get("odcs_contract_id")

        if not odps_contract_id or not odcs_contract_id:
            logger.warning(
                "odps_linked_asset_missing_contract_ids",
                event_id=event.get("event_id"),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id
            )
            return

        # Import here to avoid circular imports
        from hub.apps.contracts.models import Contract
        from hub.apps.assets.models import Asset

        # Get ODPS contract to find associated asset
        try:
            odps_contract = Contract.objects.get(id=odps_contract_id)
        except Contract.DoesNotExist:
            logger.warning(
                "odps_linked_asset_odps_contract_not_found",
                odps_contract_id=odps_contract_id,
                event_id=event.get("event_id")
            )
            return

        # Update asset metadata if asset exists
        if odps_contract.asset:
            asset = odps_contract.asset

            # Log the linkage for asset tracking
            logger.info(
                "odps_linked_asset_updated",
                asset_id=str(asset.id),
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                event_id=event.get("event_id")
            )

            # Asset service can perform additional updates if needed
            # For example, updating asset status, metadata, etc.
        else:
            logger.debug(
                "odps_linked_asset_no_asset",
                odps_contract_id=odps_contract_id,
                event_id=event.get("event_id")
            )

    except Exception as e:
        logger.error(
            "odps_linked_asset_handler_error",
            odps_contract_id=event_data.get("odps_contract_id") if 'event_data' in locals() else None,
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


# Notification Service Subscriber
@event_subscriber("notification_service", "odps.*")
def handle_odps_events_for_notification(event: Dict[str, Any]) -> None:
    """
    Handle all ODPS events for notification service.

    Sends notifications for ODPS-related events.
    """
    try:
        event_type = event.get("event_type")
        event_data = event.get("data", {})
        source = event.get("source", {})
        tenant_id = source.get("tenant_id")
        user_id = source.get("user_id")

        # Import here to avoid circular imports
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Create notification message
        contract_id = event_data.get("contract_id") or event_data.get("odps_contract_id")
        message = f"ODPS event: {event_type}"
        if contract_id:
            message += f" (Contract: {contract_id[:8]}...)"

        # Get tenant and user if available
        tenant = None
        user = None
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                pass

        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        # Log notification event
        # In the future, this could integrate with a notification service
        # that sends emails, in-app notifications, etc.
        logger.info(
            "odps_notification_event",
            event_type=event_type,
            user_id=user_id,
            tenant_id=tenant_id,
            contract_id=contract_id,
            message=message,
            event_id=event.get("event_id"),
            metadata={
                "event_type": event_type,
                "event_id": event.get("event_id"),
                "contract_id": contract_id,
                **event_data
            }
        )

    except Exception as e:
        logger.error(
            "odps_notification_handler_error",
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient


# Audit Service Subscriber
@event_subscriber("audit_service", "odps.*")
def handle_odps_events_for_audit(event: Dict[str, Any]) -> None:
    """
    Handle all ODPS events for audit service.

    Creates audit log entries for all ODPS-related events.
    """
    try:
        event_type = event.get("event_type")
        event_data = event.get("data", {})
        source = event.get("source", {})
        tenant_id = source.get("tenant_id")
        user_id = source.get("user_id")

        # Import here to avoid circular imports
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Map event type to audit action
        action_map = {
            "odps.created": "ODPS_CREATED",
            "odps.updated": "ODPS_UPDATED",
            "odps.deleted": "ODPS_DELETED",
            "odps.linked": "ODPS_LINKED",
            "odps.unlinked": "ODPS_UNLINKED",
            "odps.normalized": "ODPS_NORMALIZED",
            "odps.export.completed": "ODPS_EXPORT_COMPLETED",
            "odps.export.failed": "ODPS_EXPORT_FAILED",
        }

        action = action_map.get(event_type or "", "ODPS_EVENT")

        # Get tenant and user if available
        tenant = None
        user = None
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                pass

        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        # Get resource ID
        resource_id = event_data.get("contract_id") or event_data.get("odps_contract_id") or None

        # Create audit event
        with transaction.atomic():
            create_audit_event(
                resource_type="ODPS",
                action=action,
                actor_user=user,
                tenant=tenant,
                resource_id=resource_id,
                result="SUCCESS",
                details={
                    "event_type": event_type,
                    "event_id": event.get("event_id"),
                    **event_data
                }
            )

        logger.info(
            "odps_audit_event_created",
            event_type=event_type,
            action=action,
            resource_id=resource_id,
            event_id=event.get("event_id")
        )

    except Exception as e:
        logger.error(
            "odps_audit_handler_error",
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
            error=str(e),
            exc_info=True
        )
        # Don't raise - event processing should be resilient

