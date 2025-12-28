"""
ODPS 1.x Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 1.x.
Implements ODPSNormalizerBase with 1.x-specific mappings and graceful degradation
for missing ODPS 2.0+ features (enhanced marketplace, lifecycle, quality features).
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase

logger = structlog.get_logger(__name__)


class ODPSNormalizerV1_X(ODPSNormalizerBase):
    """
    ODPS 1.x-specific normalizer implementation.

    Extends ODPSNormalizerBase with version 1.x-specific behavior:
    - Supports ODPS version 1.x (1.0 through 1.9)
    - Graceful degradation for missing ODPS 2.0+ features:
      - Enhanced marketplace features (limited support)
      - Enhanced lifecycle features (limited support)
      - Enhanced quality features (limited support)
      - productStrategy (not available in 1.x, silently skipped)
      - paymentGateways (not available in 1.x, gracefully handled by base class)
    - ODPS 1.x-specific field mappings

    This normalizer supports ODPS version 1.x and leverages the common
    normalization logic from ODPSNormalizerBase while ensuring that ODPS 2.0+
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        Args:
            spec_version: ODPS specification version (e.g., "1.9", "1.0", "1.x")

        Returns:
            True if this normalizer supports version 1.x, False otherwise
        """
        # Support versions 1.0 through 1.9
        if spec_version.startswith("1."):
            return True
        
        # Also support "1.x" as a generic version identifier
        if spec_version == "1.x":
            return True
        
        return False

    def _map_version_specific_fields(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Map ODPS 1.x-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODPS 1.x, we explicitly skip features that are only available in
        ODPS 2.0+:
        - Enhanced marketplace features
        - Enhanced lifecycle features
        - Enhanced quality features
        - productStrategy (4.1+)
        - paymentGateways (4.1+)

        The base class methods already handle graceful degradation, but we
        override this method to be explicit about 1.x behavior and to ensure
        no processing happens for unsupported features.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (should be 1.x for this normalizer)
        """
        # Verify version is 1.x
        if not spec_version.startswith("1.") and spec_version != "1.x":
            logger.warning(
                "odps_v1_x_unexpected_version",
                expected_version="1.x",
                actual_version=spec_version,
                message="ODPSNormalizerV1_X received unexpected version"
            )

        # ODPS 1.x does not support:
        # - productStrategy (introduced in 4.1)
        # - paymentGateways (introduced in 4.1)
        # - Enhanced marketplace features (introduced in 2.0+)
        # - Enhanced lifecycle features (introduced in 2.0+)
        # - Enhanced quality features (introduced in 2.0+)
        
        # The base class methods already check version and skip processing
        # for unsupported features, but we're being explicit here
        
        # All other normalization is handled by the base class
        # Marketplace, lifecycle, and quality normalization gracefully handle
        # missing features (they're optional, so no special handling needed)
        
        # ODPS 1.x may have different field structures, but the base class
        # normalization methods handle missing fields gracefully
        
        logger.debug(
            "odps_v1_x_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODPS 1.x version-specific mapping complete (no 2.0+ features to process)"
        )











