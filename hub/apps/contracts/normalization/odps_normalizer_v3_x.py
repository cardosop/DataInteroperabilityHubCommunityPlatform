"""
ODPS 3.x Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 3.x.
Implements ODPSNormalizerBase with 3.x-specific mappings and graceful degradation
for missing ODPS 4.0+ features (productStrategy, paymentGateways, enhanced marketplace).
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase

logger = structlog.get_logger(__name__)


class ODPSNormalizerV3_X(ODPSNormalizerBase):
    """
    ODPS 3.x-specific normalizer implementation.

    Extends ODPSNormalizerBase with version 3.x-specific behavior:
    - Supports ODPS version 3.x (3.0 through 3.9)
    - Graceful degradation for missing ODPS 4.0+ features:
      - productStrategy (not available in 3.x, silently skipped)
      - paymentGateways (not available in 3.x, gracefully handled by base class)
      - Enhanced marketplace features (limited support)
    - ODPS 3.x-specific field mappings

    This normalizer supports ODPS version 3.x and leverages the common
    normalization logic from ODPSNormalizerBase while ensuring that ODPS 4.0+
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        Args:
            spec_version: ODPS specification version (e.g., "3.9", "3.0", "3.x")

        Returns:
            True if this normalizer supports version 3.x, False otherwise
        """
        # Support versions 3.0 through 3.9
        if spec_version.startswith("3."):
            return True
        
        # Also support "3.x" as a generic version identifier
        if spec_version == "3.x":
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
        Map ODPS 3.x-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODPS 3.x, we explicitly skip features that are only available in
        ODPS 4.0+:
        - productStrategy (4.1+)
        - paymentGateways (4.1+)
        - Some enhanced marketplace features

        The base class methods already handle graceful degradation, but we
        override this method to be explicit about 3.x behavior and to ensure
        no processing happens for unsupported features.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (should be 3.x for this normalizer)
        """
        # Verify version is 3.x
        if not spec_version.startswith("3.") and spec_version != "3.x":
            logger.warning(
                "odps_v3_x_unexpected_version",
                expected_version="3.x",
                actual_version=spec_version,
                message="ODPSNormalizerV3_X received unexpected version"
            )

        # ODPS 3.x does not support:
        # - productStrategy (introduced in 4.1)
        # - paymentGateways (introduced in 4.1)
        # - Some enhanced marketplace features
        
        # The base class _normalize_product_strategy already checks version
        # and skips processing for versions < 4.1, but we're being explicit here
        
        # All other normalization is handled by the base class
        # Marketplace normalization gracefully handles missing paymentGateways
        # (it's optional, so no special handling needed)
        
        # ODPS 3.x may have different field structures, but the base class
        # normalization methods handle missing fields gracefully
        
        logger.debug(
            "odps_v3_x_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODPS 3.x version-specific mapping complete (no 4.0+ features to process)"
        )





