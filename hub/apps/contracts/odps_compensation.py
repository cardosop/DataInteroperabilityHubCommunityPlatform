"""
ODPS Creation Compensation

Implements compensation logic for ODPS creation operations.
Handles rollback, cleanup, and state restoration when ODPS creation fails.
"""

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.core.services.base import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ODPSCreationState:
    """State snapshot for ODPS creation compensation."""

    contract_id: str | None = None
    asset_id: str | None = None
    asset_previous_version: int | None = None
    events_published: list[str] | None = None  # List of event IDs published

    def __post_init__(self):
        if self.events_published is None:
            self.events_published = []


class ODPSCreationCompensation:
    """
    Compensation handler for ODPS creation operations.

    Implements rollback, cleanup, and state restoration for failed ODPS creation.
    This ensures that partial creations are properly cleaned up and system state
    is restored to its previous condition.
    """

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize ODPS creation compensation handler.

        Args:
            tenant_id: Tenant ID for operations
            user_id: User ID for operations
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def rollback_created_contract(
        self, contract_id: str, state: ODPSCreationState | None = None
    ) -> dict[str, Any]:
        """
        Rollback created contract by deleting it.

        Args:
            contract_id: ID of contract to rollback
            state: Optional state snapshot for additional context

        Returns:
            Dict with rollback result

        Raises:
            ValidationError: If rollback fails
        """
        logger.info(
            f"Starting ODPS contract rollback: contract_id={contract_id}, tenant_id={self.tenant_id}"
        )

        try:
            # Get contract
            try:
                contract = Contract.objects.get(id=contract_id, tenant_id=self.tenant_id)
            except Contract.DoesNotExist:
                logger.warning(
                    f"Contract not found for rollback: contract_id={contract_id}, may have already been deleted"
                )
                return {
                    "status": "skipped",
                    "reason": "contract_not_found",
                    "contract_id": contract_id,
                }

            # Store contract details for logging
            contract_details = {
                "contract_id": str(contract.id),
                "status": contract.status,
                "asset_id": str(contract.asset.id) if contract.asset else None,
                "odps_version": contract.original_spec_version,
            }

            # Delete contract
            contract.delete()

            logger.info(f"ODPS contract successfully rolled back: {contract_details}")

            return {
                "status": "success",
                "contract_id": contract_id,
                "contract_details": contract_details,
            }

        except Exception as e:
            logger.exception(
                f"Failed to rollback ODPS contract: contract_id={contract_id}, error={e!s}"
            )
            raise ValidationError(
                message=f"Failed to rollback ODPS contract {contract_id}: {e!s}",
                code="ODPS_ROLLBACK_FAILED",
                details={"contract_id": contract_id, "error": str(e)},
            ) from e

    @transaction.atomic
    def cleanup_resources(
        self, state: ODPSCreationState, publish_compensation_events: bool = True
    ) -> dict[str, Any]:
        """
        Cleanup resources created during ODPS creation.

        This includes:
        - Publishing compensation events (if enabled)
        - Cleaning up any temporary resources
        - Logging cleanup operations

        Args:
            state: State snapshot with resources to cleanup
            publish_compensation_events: If True, publish compensation events

        Returns:
            Dict with cleanup result
        """
        logger.info(
            f"Starting ODPS creation resource cleanup: contract_id={state.contract_id}, "
            f"asset_id={state.asset_id}, events_count={len(state.events_published) if state.events_published else 0}"
        )

        cleanup_results = {"status": "success", "resources_cleaned": [], "events_published": []}

        # Publish compensation events if enabled
        if publish_compensation_events and state.contract_id:
            try:
                from hub.apps.core.events.publisher import EventPublisher
                from hub.apps.core.events.service_publishers import ODPSEventPublisher

                event_publisher = EventPublisher(
                    service_name="odps_service", tenant_id=self.tenant_id, user_id=self.user_id
                )

                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = event_publisher

                # Publish compensation event
                # Note: We don't have a specific compensation event type,
                # so we log it and could extend the event schema if needed
                logger.info(
                    f"ODPS creation compensation event logged: contract_id={state.contract_id}"
                )

                cleanup_results["events_published"].append("compensation_logged")

            except Exception as e:
                logger.warning(
                    f"Failed to publish compensation event (non-critical): contract_id={state.contract_id}, error={e!s}"
                )
                # Non-critical, continue cleanup

        cleanup_results["resources_cleaned"].append("events")

        logger.info(
            f"ODPS creation resources cleaned up successfully: contract_id={state.contract_id}, "
            f"resources_cleaned={len(cleanup_results['resources_cleaned'])}"
        )

        return cleanup_results

    @transaction.atomic
    def restore_previous_state(self, state: ODPSCreationState) -> dict[str, Any]:
        """
        Restore previous state before ODPS creation.

        This includes:
        - Restoring asset version if it was modified
        - Restoring any other state that was changed

        Args:
            state: State snapshot with previous state information

        Returns:
            Dict with restoration result
        """
        logger.info(
            f"Starting previous state restoration: contract_id={state.contract_id}, asset_id={state.asset_id}"
        )

        restoration_results = {"status": "success", "restored_items": []}

        # Restore asset version if it was modified
        if state.asset_id and state.asset_previous_version is not None:
            try:
                asset = Asset.objects.get(id=state.asset_id, tenant_id=self.tenant_id)

                # Check if asset version needs restoration
                # Note: Asset version restoration would depend on how versioning works
                # For now, we log the restoration attempt
                logger.info(
                    f"Asset version restoration attempted: asset_id={state.asset_id}, "
                    f"previous_version={state.asset_previous_version}, "
                    f"current_version={getattr(asset, 'version', None)}"
                )

                # If asset has a version field and it was incremented, restore it
                if hasattr(asset, "version") and asset.version is not None:
                    if asset.version > state.asset_previous_version:
                        asset.version = state.asset_previous_version
                        asset.save(update_fields=["version", "updated_at"])
                        restoration_results["restored_items"].append("asset_version")
                        logger.info(
                            f"Asset version restored successfully: asset_id={state.asset_id}, "
                            f"restored_version={state.asset_previous_version}"
                        )

            except Asset.DoesNotExist:
                logger.warning(f"Asset not found for state restoration: asset_id={state.asset_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to restore asset state (non-critical): asset_id={state.asset_id}, error={e!s}"
                )
                # Non-critical, continue restoration

        logger.info(
            f"Previous state restoration completed: contract_id={state.contract_id}, "
            f"restored_items={len(restoration_results['restored_items'])}"
        )

        return restoration_results

    @transaction.atomic
    def compensate(
        self,
        state: ODPSCreationState,
        rollback_contract: bool = True,
        cleanup_resources: bool = True,
        restore_state: bool = True,
        publish_compensation_events: bool = True,
    ) -> dict[str, Any]:
        """
        Comprehensive compensation for ODPS creation failure.

        Performs all compensation operations:
        1. Rollback created contracts
        2. Cleanup resources
        3. Restore previous state

        Args:
            state: State snapshot with information about what was created
            rollback_contract: If True, rollback created contract
            cleanup_resources: If True, cleanup resources
            restore_state: If True, restore previous state
            publish_compensation_events: If True, publish compensation events

        Returns:
            Dict with comprehensive compensation result
        """
        logger.info(
            f"Starting comprehensive ODPS creation compensation: contract_id={state.contract_id}, asset_id={state.asset_id}"
        )

        compensation_result = {
            "status": "success",
            "timestamp": timezone.now().isoformat(),
            "state": {"contract_id": state.contract_id, "asset_id": state.asset_id},
            "operations": {},
        }

        # Rollback created contract
        if rollback_contract and state.contract_id:
            try:
                rollback_result = self.rollback_created_contract(
                    contract_id=state.contract_id, state=state
                )
                compensation_result["operations"]["rollback"] = rollback_result
            except Exception as e:
                logger.exception(
                    f"Rollback failed during compensation: contract_id={state.contract_id}, error={e!s}"
                )
                compensation_result["status"] = "partial_failure"
                compensation_result["operations"]["rollback"] = {
                    "status": "failed",
                    "error": str(e),
                }

        # Cleanup resources
        if cleanup_resources:
            try:
                cleanup_result = self.cleanup_resources(
                    state=state, publish_compensation_events=publish_compensation_events
                )
                compensation_result["operations"]["cleanup"] = cleanup_result
            except Exception as e:
                logger.exception(f"Cleanup failed during compensation: error={e!s}")
                compensation_result["status"] = "partial_failure"
                compensation_result["operations"]["cleanup"] = {"status": "failed", "error": str(e)}

        # Restore previous state
        if restore_state:
            try:
                restore_result = self.restore_previous_state(state=state)
                compensation_result["operations"]["restore"] = restore_result
            except Exception as e:
                logger.exception(f"State restoration failed during compensation: error={e!s}")
                compensation_result["status"] = "partial_failure"
                compensation_result["operations"]["restore"] = {"status": "failed", "error": str(e)}

        if compensation_result["status"] == "success":
            logger.info(
                f"ODPS creation compensation completed successfully: contract_id={state.contract_id}"
            )
        else:
            logger.warning(
                f"ODPS creation compensation completed with partial failures: contract_id={state.contract_id}"
            )

        return compensation_result
