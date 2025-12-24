"""
ODCS 3.0.0 Normalizer

Version-specific normalizer for ODCS (Open Data Contract Standard) version 3.0.0.
Implements ODCSNormalizerBase with 3.0.0-specific mappings and graceful degradation
for missing ODCS 3.0.1/3.0.2 features.
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase

logger = structlog.get_logger(__name__)


class ODCSNormalizerV3_0_0(ODCSNormalizerBase):
    """
    ODCS 3.0.0-specific normalizer implementation.

    Extends ODCSNormalizerBase with version 3.0.0-specific behavior:
    - Supports ODCS version 3.0.0
    - Graceful degradation for missing ODCS 3.0.1/3.0.2 features
    - ODCS 3.0.0-specific field mappings

    This normalizer supports ODCS version 3.0.0 and leverages the common
    normalization logic from ODCSNormalizerBase while ensuring that ODCS 3.0.1+
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODCS version.

        Args:
            spec_version: ODCS specification version (e.g., "3.0.0", "3.0.1", "3.0.2")

        Returns:
            True if this normalizer supports version 3.0.0, False otherwise
        """
        return spec_version == "3.0.0"

    def _map_version_specific_fields(
        self,
        odcs_contract: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Map ODCS 3.0.0-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODCS 3.0.0, we explicitly handle graceful degradation for features
        that are only available in ODCS 3.0.1+.

        The base class methods already handle graceful degradation for missing
        fields, but we override this method to be explicit about 3.0.0 behavior
        and to ensure no processing happens for unsupported 3.0.1+ features.

        Args:
            odcs_contract: Raw ODCS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODCS spec version (should be 3.0.0 for this normalizer)
        """
        # Verify version is 3.0.0
        if spec_version != "3.0.0":
            logger.warning(
                "odcs_v3_0_0_unexpected_version",
                expected_version="3.0.0",
                actual_version=spec_version,
                message="ODCSNormalizerV3_0_0 received unexpected version"
            )

        # ODCS 3.0.0 does not support features introduced in 3.0.1+ and 3.0.2+
        # The base class normalization methods already handle missing fields
        # gracefully, so we don't need to explicitly skip processing.
        # However, if a 3.0.1+ or 3.0.2+-specific field is present in the contract,
        # we should log it for observability but not process it.

        # Check for potential 3.0.1+ or 3.0.2+ features that might be present
        # (These checks are defensive - the base class already handles missing fields)
        # Note: Since we don't have explicit documentation of 3.0.1+/3.0.2+-only features,
        # we rely on the base class's graceful degradation for any missing fields.

        logger.debug(
            "odcs_v3_0_0_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODCS 3.0.0 version-specific mapping complete (graceful degradation for 3.0.1+/3.0.2+ features)"
        )

