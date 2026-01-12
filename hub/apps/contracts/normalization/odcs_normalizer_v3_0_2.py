"""
ODCS 3.0.2 Normalizer

Version-specific normalizer for ODCS (Open Data Contract Standard) version 3.0.2.
Implements ODCSNormalizerBase with 3.0.2-specific support, focusing on:
- Explicit support for ODCS 3.0.2 and 3.0.2+ versions
- ODCS 3.0.2-specific field mappings (if any)
"""
import structlog
from typing import Dict, Any, List

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase

logger = structlog.get_logger(__name__)


class ODCSNormalizerV3_0_2(ODCSNormalizerBase):
    """
    ODCS 3.0.2-specific normalizer implementation.

    Extends ODCSNormalizerBase with version 3.0.2-specific support:
    - Explicit support for ODCS version 3.0.2 and 3.0.2+ (patch versions)
    - ODCS 3.0.2-specific field mappings (if any)

    This normalizer supports ODCS version 3.0.2 and leverages the common
    normalization logic from ODCSNormalizerBase while providing explicit
    version-specific handling for 3.0.2 contracts.
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODCS version.

        Supports:
        - Exact version "3.0.2"
        - Version "3.0.2+" (explicit patch version indicator)
        - Versions starting with "3.0.2" (e.g., "3.0.2.1", "3.0.2.5")

        Args:
            spec_version: ODCS specification version (e.g., "3.0.2", "3.0.2+", "3.0.2.1")

        Returns:
            True if this normalizer supports the version, False otherwise
        """
        # Handle None case gracefully
        if spec_version is None:
            return False

        # Support exact version 3.0.2
        if spec_version == "3.0.2":
            return True

        # Support explicit patch version indicator "3.0.2+"
        if spec_version == "3.0.2+":
            return True

        # Support patch versions starting with "3.0.2" (e.g., "3.0.2.1", "3.0.2.5")
        if isinstance(spec_version, str) and spec_version.startswith("3.0.2"):
            return True

        return False

    def _map_version_specific_fields(
        self,
        odcs_contract: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Map ODCS 3.0.2-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODCS 3.0.2, all common mappings are handled by the base class,
        so this method currently serves as a placeholder for any future
        3.0.2-specific mappings that may be needed.

        Args:
            odcs_contract: Raw ODCS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODCS spec version (should be "3.0.2" or "3.0.2+" for this normalizer)
        """
        # Verify version is 3.0.2 or 3.0.2+
        if not (spec_version and (spec_version == "3.0.2" or spec_version == "3.0.2+" or (isinstance(spec_version, str) and spec_version.startswith("3.0.2")))):
            logger.warning(
                "odcs_v3_0_2_unexpected_version",
                expected_version="3.0.2 or 3.0.2+",
                actual_version=spec_version,
                message="ODCSNormalizerV3_0_2 received unexpected version"
            )

        # ODCS 3.0.2 uses the standard normalization logic from the base class.
        # All common mappings are handled by ODCSNormalizerBase methods.
        # If any 3.0.2-specific mappings are needed in the future, they should be
        # added here.

        logger.debug(
            "odcs_v3_0_2_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODCS 3.0.2 version-specific mapping complete"
        )

