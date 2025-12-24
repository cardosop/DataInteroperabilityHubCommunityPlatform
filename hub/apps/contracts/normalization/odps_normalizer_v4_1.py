"""
ODPS 4.1 Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 4.1.
Implements ODPSNormalizerBase with 4.1-specific mappings, focusing on:
- Enhanced marketplace support (paymentGateways)
- Product strategy support
- ODPS 4.1-specific field mappings
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odps_normalizer_base import ODPSNormalizerBase

logger = structlog.get_logger(__name__)


class ODPSNormalizerV4_1(ODPSNormalizerBase):
    """
    ODPS 4.1-specific normalizer implementation.

    Extends ODPSNormalizerBase with version 4.1-specific mappings:
    - Enhanced marketplace support (paymentGateways - ODPS 4.1 only)
    - Product strategy normalization (objectives, strategicAlignment, productKPIs)
    - ODPS 4.1-specific field mappings

    This normalizer supports ODPS version 4.1 and leverages the common
    normalization logic from ODPSNormalizerBase while adding 4.1-specific
    enhancements, particularly for marketplace features.
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        Args:
            spec_version: ODPS specification version (e.g., "4.1", "4.0")

        Returns:
            True if this normalizer supports version 4.1, False otherwise
        """
        return spec_version == "4.1"

    def _map_version_specific_fields(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Map ODPS 4.1-specific fields to HubContract format.

        This method is called after all common normalization methods.
        It handles:
        - Product strategy normalization (objectives, strategicAlignment, productKPIs)
        - Any additional ODPS 4.1-specific mappings

        Note: Marketplace paymentGateways is already handled in the common
        _normalize_marketplace method, which supports ODPS 4.1 features.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (should be "4.1" for this normalizer)
        """
        # Product strategy is handled by the base class _normalize_product_strategy
        # which is called in the base class _map_version_specific_fields
        # We call the parent implementation to ensure product strategy is normalized
        super()._map_version_specific_fields(contract_data, hub_contract, warnings, spec_version)

        # Additional ODPS 4.1-specific mappings can be added here
        # For now, product strategy and enhanced marketplace (paymentGateways)
        # are the main 4.1-specific features, and they're already handled
        # by the common normalization methods

