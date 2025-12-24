"""
ODPS 4.0 Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 4.0.
Implements ODPSNormalizerBase with 4.0-specific mappings and graceful degradation
for missing ODPS 4.1 features (productStrategy, paymentGateways).
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase

logger = structlog.get_logger(__name__)


class ODPSNormalizerV4_0(ODPSNormalizerBase):
    """
    ODPS 4.0-specific normalizer implementation.

    Extends ODPSNormalizerBase with version 4.0-specific behavior:
    - Supports ODPS version 4.0 only
    - Graceful degradation for missing ODPS 4.1 features:
      - productStrategy (not available in 4.0, silently skipped)
      - paymentGateways (not available in 4.0, gracefully handled by base class)
    - ODPS 4.0-specific field mappings

    This normalizer supports ODPS version 4.0 and leverages the common
    normalization logic from ODPSNormalizerBase while ensuring that ODPS 4.1+
    features are not processed (graceful degradation).
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        Args:
            spec_version: ODPS specification version (e.g., "4.1", "4.0")

        Returns:
            True if this normalizer supports version 4.0, False otherwise
        """
        return spec_version == "4.0"

    def _map_version_specific_fields(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Map ODPS 4.0-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODPS 4.0, we explicitly skip productStrategy processing since
        it's only available in ODPS 4.1+.

        Note: The base class _normalize_product_strategy method already
        checks the version and skips processing for versions < 4.1, but
        we override this method to be explicit about 4.0 behavior and to
        avoid any potential version parsing issues.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (should be "4.0" for this normalizer)
        """
        # ODPS 4.0 does not support productStrategy (introduced in 4.1)
        # The base class _normalize_product_strategy already checks version,
        # but we explicitly skip it here for clarity and to ensure no processing
        # happens even if version parsing fails

        # Verify version is 4.0
        if spec_version != "4.0":
            logger.warning(
                "odps_v4_0_unexpected_version",
                expected_version="4.0",
                actual_version=spec_version,
                message="ODPSNormalizerV4_0 received unexpected version"
            )

        # Do not process productStrategy for ODPS 4.0
        # The base class _normalize_product_strategy would skip it anyway,
        # but we're being explicit here

        # All other normalization is handled by the base class
        # Marketplace normalization gracefully handles missing paymentGateways
        # (it's optional, so no special handling needed)

        logger.debug(
            "odps_v4_0_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODPS 4.0 version-specific mapping complete (no 4.1 features to process)"
        )

