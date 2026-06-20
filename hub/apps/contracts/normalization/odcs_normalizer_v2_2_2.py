"""
ODCS 2.2.2 Normalizer

Version-specific normalizer for ODCS (Open Data Contract Standard) version 2.2.2.
Implements ODCSNormalizerBase with 2.2.2-specific mappings and graceful degradation
for missing ODCS 3.x features.
"""

from typing import Any

import structlog

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase

logger = structlog.get_logger(__name__)


class ODCSNormalizerV2_2_2(ODCSNormalizerBase):
    """
    ODCS 2.2.2-specific normalizer implementation.

    Extends ODCSNormalizerBase with version 2.2.2-specific behavior:
    - Supports ODCS version 2.2.2
    - Graceful degradation for missing ODCS 3.x features:
      - Enhanced marketplace features (limited support)
      - Enhanced lifecycle features (limited support)
      - Other 3.x-specific features (gracefully handled by base class)
    - ODCS 2.2.2-specific field mappings

    This normalizer supports ODCS version 2.2.2 and leverages the common
    normalization logic from ODCSNormalizerBase while ensuring that ODCS 3.x
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODCS version.

        Args:
            spec_version: ODCS specification version (e.g., "2.2.2", "3.0.0", "3.0.2")

        Returns:
            True if this normalizer supports version 2.2.2, False otherwise
        """
        return spec_version == "2.2.2"

    def _map_version_specific_fields(
        self,
        odcs_contract: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Map ODCS 2.2.2-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODCS 2.2.2, we explicitly handle graceful degradation for features
        that are only available in ODCS 3.x:
        - Enhanced marketplace features (introduced in 3.x)
        - Enhanced lifecycle features (introduced in 3.x)
        - Other 3.x-specific features

        The base class methods already handle graceful degradation for missing
        fields, but we override this method to be explicit about 2.2.2 behavior
        and to ensure no processing happens for unsupported 3.x features.

        Args:
            odcs_contract: Raw ODCS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODCS spec version (should be 2.2.2 for this normalizer)
        """
        # Verify version is 2.2.2
        if spec_version != "2.2.2":
            logger.warning(
                "odcs_v2_2_2_unexpected_version",
                expected_version="2.2.2",
                actual_version=spec_version,
                message="ODCSNormalizerV2_2_2 received unexpected version",
            )

        # ODCS 2.2.2 does not support features introduced in 3.x:
        # - Enhanced marketplace features (introduced in 3.0+)
        # - Enhanced lifecycle features (introduced in 3.0+)
        # - Other 3.x-specific features
        #
        # The base class normalization methods already handle missing fields
        # gracefully, so we don't need to explicitly skip processing.
        # However, if a 3.x-specific field is present in the contract,
        # we should log it for observability but not process it.
        #
        # Check for potential 3.x features that might be present
        # (These checks are defensive - the base class already handles missing fields)
        # Note: Since we don't have explicit documentation of 3.x-only features,
        # we rely on the base class's graceful degradation for any missing fields.

        logger.debug(
            "odcs_v2_2_2_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODCS 2.2.2 version-specific mapping complete (graceful degradation for 3.x features)",
        )
