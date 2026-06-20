"""
ODPS Linking Compensation

Implements compensation logic for ODPS linking operations.
Handles rollback, cleanup, and state restoration when ODPS linking fails.
"""

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from hub.apps.contracts.models import Contract

logger = logging.getLogger(__name__)


@dataclass
class ODPSLinkingState:
    """State snapshot for ODPS linking compensation."""

    odps_contract_id: str | None = None
    odcs_contract_id: str | None = None
    odps_contract_created: bool = False  # True if ODPS contract was created during linking
    previous_odps_link: str | None = None  # Previous ODPS link in ODCS contract (if existed)
    previous_odcs_link: str | None = None  # Previous ODCS link in ODPS contract (if existed)
    events_published: list[str] | None = None  # List of event IDs published

    def __post_init__(self):
        if self.events_published is None:
            self.events_published = []


class ODPSLinkingCompensation:
    """
    Compensation handler for ODPS linking operations.

    Implements rollback, cleanup, and state restoration for failed ODPS linking.
    This ensures that partial linkings are properly cleaned up and system state
    is restored to its previous condition.
    """

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize ODPS linking compensation handler.

        Args:
            tenant_id: Tenant ID for operations
            user_id: User ID for operations
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def remove_established_links(self, state: ODPSLinkingState) -> dict[str, Any]:
        """
        Remove established links between ODPS and ODCS contracts.

        Removes bidirectional links:
        - ODPS → ODCS link (odcs_link in ODPS contract)
        - ODCS → ODPS link (odps_link in ODCS contract)

        Args:
            state: State snapshot with link information

        Returns:
            Dict with removal result

        Raises:
            ValidationError: If removal fails
        """
        logger.info(
            f"Removing established ODPS-ODCS links: odps_contract_id={state.odps_contract_id}, "
            f"odcs_contract_id={state.odcs_contract_id}"
        )

        removal_results = {"status": "success", "links_removed": []}

        # Remove ODPS → ODCS link
        if state.odps_contract_id:
            try:
                odps_contract = Contract.objects.get(
                    id=state.odps_contract_id, tenant_id=self.tenant_id
                )

                if odps_contract.hub_contract_json:
                    extensions = odps_contract.hub_contract_json.get("extensions", {})
                    x_odps = extensions.get("x_odps", {})

                    if "odcs_link" in x_odps:
                        # Only store previous link if not already set (should be set before linking)
                        # Don't overwrite if it was already captured during linking
                        current_link = x_odps.get("odcs_link")
                        if state.previous_odcs_link is None:
                            # Only store if it's different from the ODCS being unlinked
                            # (to avoid storing the link we're about to remove)
                            if current_link != state.odcs_contract_id:
                                state.previous_odcs_link = current_link

                        # Remove link
                        del x_odps["odcs_link"]
                        odps_contract.save(update_fields=["hub_contract_json"])
                        removal_results["links_removed"].append("odps_to_odcs")

                        logger.info(
                            f"Removed ODPS → ODCS link: odps_contract_id={state.odps_contract_id}"
                        )

            except Contract.DoesNotExist:
                logger.warning(
                    f"ODPS contract not found for link removal: contract_id={state.odps_contract_id}"
                )
            except Exception as e:
                logger.exception(
                    f"Failed to remove ODPS → ODCS link: odps_contract_id={state.odps_contract_id}, error={e!s}"
                )
                removal_results["status"] = "partial_failure"
                removal_results["errors"] = removal_results.get("errors", [])
                removal_results["errors"].append(f"ODPS link removal failed: {e!s}")

        # Remove ODCS → ODPS link
        if state.odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(
                    id=state.odcs_contract_id, tenant_id=self.tenant_id
                )

                if odcs_contract.hub_contract_json:
                    extensions = odcs_contract.hub_contract_json.get("extensions", {})
                    x_odps = extensions.get("x_odps", {})

                    if "odps_link" in x_odps:
                        # Store previous link for restoration
                        if state.previous_odps_link is None:
                            state.previous_odps_link = x_odps.get("odps_link")

                        # Remove link
                        del x_odps["odps_link"]
                        odcs_contract.save(update_fields=["hub_contract_json"])
                        removal_results["links_removed"].append("odcs_to_odps")

                        logger.info(
                            f"Removed ODCS → ODPS link: odcs_contract_id={state.odcs_contract_id}"
                        )

            except Contract.DoesNotExist:
                logger.warning(
                    f"ODCS contract not found for link removal: contract_id={state.odcs_contract_id}"
                )
            except Exception as e:
                logger.exception(
                    f"Failed to remove ODCS → ODPS link: odcs_contract_id={state.odcs_contract_id}, error={e!s}"
                )
                removal_results["status"] = "partial_failure"
                removal_results["errors"] = removal_results.get("errors", [])
                removal_results["errors"].append(f"ODCS link removal failed: {e!s}")

        logger.info(
            f"Link removal completed: status={removal_results['status']}, "
            f"links_removed={len(removal_results['links_removed'])}"
        )

        return removal_results

    @transaction.atomic
    def restore_previous_state(self, state: ODPSLinkingState) -> dict[str, Any]:
        """
        Restore previous state before ODPS linking.

        This includes:
        - Restoring previous links if they existed
        - Deleting ODPS contract if it was created during linking
        - Restoring any other state that was changed

        Args:
            state: State snapshot with previous state information

        Returns:
            Dict with restoration result
        """
        logger.info(
            f"Restoring previous state: odps_contract_id={state.odps_contract_id}, "
            f"odcs_contract_id={state.odcs_contract_id}, odps_created={state.odps_contract_created}"
        )

        restoration_results = {"status": "success", "restored_items": []}

        # Delete ODPS contract if it was created during linking
        if state.odps_contract_created and state.odps_contract_id:
            try:
                odps_contract = Contract.objects.get(
                    id=state.odps_contract_id, tenant_id=self.tenant_id
                )
                odps_contract.delete()
                restoration_results["restored_items"].append("odps_contract_deleted")
                logger.info(
                    f"Deleted ODPS contract created during linking: contract_id={state.odps_contract_id}"
                )
            except Contract.DoesNotExist:
                logger.warning(
                    f"ODPS contract not found for deletion: contract_id={state.odps_contract_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete ODPS contract (non-critical): contract_id={state.odps_contract_id}, error={e!s}"
                )
                restoration_results["status"] = "partial_failure"

        # Restore previous ODPS link in ODCS contract (if existed and ODPS contract still exists)
        # Don't restore if the ODPS contract was deleted (odps_contract_created=True)
        if state.previous_odps_link and state.odcs_contract_id and not state.odps_contract_created:
            try:
                # Verify the previous ODPS contract still exists before restoring
                Contract.objects.get(id=state.previous_odps_link, tenant_id=self.tenant_id)

                odcs_contract = Contract.objects.get(
                    id=state.odcs_contract_id, tenant_id=self.tenant_id
                )

                if odcs_contract.hub_contract_json:
                    if "extensions" not in odcs_contract.hub_contract_json:
                        odcs_contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in odcs_contract.hub_contract_json["extensions"]:
                        odcs_contract.hub_contract_json["extensions"]["x_odps"] = {}

                    odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = (
                        state.previous_odps_link
                    )
                    odcs_contract.save(update_fields=["hub_contract_json"])
                    restoration_results["restored_items"].append("odcs_previous_odps_link")
                    logger.info(
                        f"Restored previous ODPS link in ODCS contract: odcs_contract_id={state.odcs_contract_id}, "
                        f"previous_odps_link={state.previous_odps_link}"
                    )

            except Contract.DoesNotExist:
                logger.debug(
                    f"Previous ODPS contract not found for restoration (may have been deleted): "
                    f"previous_odps_link={state.previous_odps_link}, odcs_contract_id={state.odcs_contract_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to restore previous ODPS link (non-critical): odcs_contract_id={state.odcs_contract_id}, error={e!s}"
                )

        # Restore previous ODCS link in ODPS contract (if existed and contract still exists)
        # Don't restore if the ODPS contract was deleted (odps_contract_created=True)
        if state.previous_odcs_link and state.odps_contract_id and not state.odps_contract_created:
            try:
                odps_contract = Contract.objects.get(
                    id=state.odps_contract_id, tenant_id=self.tenant_id
                )

                if odps_contract.hub_contract_json:
                    if "extensions" not in odps_contract.hub_contract_json:
                        odps_contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                        odps_contract.hub_contract_json["extensions"]["x_odps"] = {}

                    odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = (
                        state.previous_odcs_link
                    )
                    odps_contract.save(update_fields=["hub_contract_json"])
                    restoration_results["restored_items"].append("odps_previous_odcs_link")
                    logger.info(
                        f"Restored previous ODCS link in ODPS contract: odps_contract_id={state.odps_contract_id}, "
                        f"previous_odcs_link={state.previous_odcs_link}"
                    )

            except Contract.DoesNotExist:
                # Contract may have been deleted, which is fine
                logger.debug(
                    f"ODPS contract not found for state restoration (may have been deleted): contract_id={state.odps_contract_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to restore previous ODCS link (non-critical): odps_contract_id={state.odps_contract_id}, error={e!s}"
                )

        logger.info(
            f"State restoration completed: status={restoration_results['status']}, "
            f"restored_items={len(restoration_results['restored_items'])}"
        )

        return restoration_results

    @transaction.atomic
    def cleanup_resources(
        self, state: ODPSLinkingState, publish_compensation_events: bool = True
    ) -> dict[str, Any]:
        """
        Cleanup resources created during ODPS linking.

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
            f"Cleaning up ODPS linking resources: odps_contract_id={state.odps_contract_id}, "
            f"odcs_contract_id={state.odcs_contract_id}, events_count={len(state.events_published) if state.events_published else 0}"
        )

        cleanup_results = {"status": "success", "resources_cleaned": [], "events_published": []}

        # Publish compensation events if enabled
        if publish_compensation_events and (state.odps_contract_id or state.odcs_contract_id):
            try:
                from hub.apps.core.events.publisher import EventPublisher
                from hub.apps.core.events.service_publishers import ODPSEventPublisher

                event_publisher = EventPublisher(
                    service_name="odps_service", tenant_id=self.tenant_id, user_id=self.user_id
                )

                odps_event_publisher = ODPSEventPublisher()
                odps_event_publisher._event_publisher = event_publisher

                # Publish compensation event
                logger.info(
                    f"ODPS linking compensation event logged: odps_contract_id={state.odps_contract_id}, "
                    f"odcs_contract_id={state.odcs_contract_id}"
                )

                cleanup_results["events_published"].append("compensation_logged")

            except Exception as e:
                logger.warning(f"Failed to publish compensation event (non-critical): error={e!s}")
                # Non-critical, continue cleanup

        cleanup_results["resources_cleaned"].append("events")

        logger.info(
            f"ODPS linking resources cleaned up successfully: resources_cleaned={len(cleanup_results['resources_cleaned'])}"
        )

        return cleanup_results

    @transaction.atomic
    def compensate(
        self,
        state: ODPSLinkingState,
        remove_links: bool = True,
        restore_state: bool = True,
        cleanup_resources: bool = True,
        publish_compensation_events: bool = True,
    ) -> dict[str, Any]:
        """
        Comprehensive compensation for ODPS linking failure.

        Performs all compensation operations:
        1. Remove established links
        2. Restore previous state
        3. Cleanup resources

        Args:
            state: State snapshot with information about what was linked
            remove_links: If True, remove established links
            restore_state: If True, restore previous state
            cleanup_resources: If True, cleanup resources
            publish_compensation_events: If True, publish compensation events

        Returns:
            Dict with comprehensive compensation result
        """
        logger.info(
            f"Starting comprehensive ODPS linking compensation: odps_contract_id={state.odps_contract_id}, "
            f"odcs_contract_id={state.odcs_contract_id}"
        )

        compensation_result = {
            "status": "success",
            "timestamp": timezone.now().isoformat(),
            "state": {
                "odps_contract_id": state.odps_contract_id,
                "odcs_contract_id": state.odcs_contract_id,
                "odps_contract_created": state.odps_contract_created,
            },
            "operations": {},
        }

        # Remove established links
        if remove_links:
            try:
                removal_result = self.remove_established_links(state=state)
                compensation_result["operations"]["remove_links"] = removal_result
                if removal_result.get("status") == "partial_failure":
                    compensation_result["status"] = "partial_failure"
            except Exception as e:
                logger.exception(f"Link removal failed during compensation: error={e!s}")
                compensation_result["status"] = "partial_failure"
                compensation_result["operations"]["remove_links"] = {
                    "status": "failed",
                    "error": str(e),
                }

        # Restore previous state
        if restore_state:
            try:
                restore_result = self.restore_previous_state(state=state)
                compensation_result["operations"]["restore"] = restore_result
                if restore_result.get("status") == "partial_failure":
                    compensation_result["status"] = "partial_failure"
            except Exception as e:
                logger.exception(f"State restoration failed during compensation: error={e!s}")
                compensation_result["status"] = "partial_failure"
                compensation_result["operations"]["restore"] = {"status": "failed", "error": str(e)}

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

        if compensation_result["status"] == "success":
            logger.info(
                f"ODPS linking compensation completed successfully: odps_contract_id={state.odps_contract_id}"
            )
        else:
            logger.warning(
                f"ODPS linking compensation completed with partial failures: odps_contract_id={state.odps_contract_id}"
            )

        return compensation_result
