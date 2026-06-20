"""
ODPS 2.x Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 2.x.
Implements ODPSNormalizerBase with 2.x-specific mappings and graceful degradation
for missing ODPS 3.0+ features (enhanced marketplace, lifecycle features).
"""

from typing import Any

import structlog

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase

logger = structlog.get_logger(__name__)


class ODPSNormalizerV2_X(ODPSNormalizerBase):
    """
    ODPS 2.x-specific normalizer implementation.

    Extends ODPSNormalizerBase with version 2.x-specific behavior:
    - Supports ODPS version 2.x (2.0 through 2.9)
    - Graceful degradation for missing ODPS 3.0+ features:
      - Enhanced marketplace features (limited support)
      - Enhanced lifecycle features (limited support)
      - productStrategy (not available in 2.x, silently skipped)
      - paymentGateways (not available in 2.x, gracefully handled by base class)
    - ODPS 2.x-specific field mappings

    This normalizer supports ODPS version 2.x and leverages the common
    normalization logic from ODPSNormalizerBase while ensuring that ODPS 3.0+
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        Args:
            spec_version: ODPS specification version (e.g., "2.9", "2.0", "2.x")

        Returns:
            True if this normalizer supports version 2.x, False otherwise
        """
        # Support versions 2.0 through 2.9
        if spec_version.startswith("2."):
            return True

        # Also support "2.x" as a generic version identifier
        if spec_version == "2.x":
            return True

        return False

    def _map_version_specific_fields(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Map ODPS 2.x-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODPS 2.x, we explicitly skip features that are only available in
        ODPS 3.0+:
        - Enhanced marketplace features
        - Enhanced lifecycle features
        - productStrategy (4.1+)
        - paymentGateways (4.1+)

        The base class methods already handle graceful degradation, but we
        override this method to be explicit about 2.x behavior and to ensure
        no processing happens for unsupported features.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (should be 2.x for this normalizer)
        """
        # Verify version is 2.x
        if not spec_version.startswith("2.") and spec_version != "2.x":
            logger.warning(
                "odps_v2_x_unexpected_version",
                expected_version="2.x",
                actual_version=spec_version,
                message="ODPSNormalizerV2_X received unexpected version",
            )

        # ODPS 2.x does not support:
        # - productStrategy (introduced in 4.1)
        # - paymentGateways (introduced in 4.1)
        # - Enhanced marketplace features (introduced in 3.0+)
        # - Enhanced lifecycle features (introduced in 3.0+)

        # The base class methods already check version and skip processing
        # for unsupported features, but we're being explicit here

        # All other normalization is handled by the base class
        # Marketplace and lifecycle normalization gracefully handle missing
        # features (they're optional, so no special handling needed)

        # ODPS 2.x may have different field structures, but the base class
        # normalization methods handle missing fields gracefully

        logger.debug(
            "odps_v2_x_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODPS 2.x version-specific mapping complete (no 3.0+ features to process)",
        )
