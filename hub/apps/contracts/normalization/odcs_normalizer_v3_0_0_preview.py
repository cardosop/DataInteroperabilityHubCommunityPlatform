"""
ODCS 3.0.0-Preview Normalizer

Version-specific normalizer for ODCS (Open Data Contract Standard) version 3.0.0-preview.
Implements ODCSNormalizerBase with 3.0.0-preview-specific support, focusing on:
- Explicit support for ODCS 3.0.0-preview version
- Graceful degradation for missing features (preview versions may have incomplete features)
- ODCS 3.0.0-preview-specific field mappings (if any)
"""

from typing import Any

import structlog

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase

logger = structlog.get_logger(__name__)


class ODCSNormalizerV3_0_0_Preview(ODCSNormalizerBase):
    """
    ODCS 3.0.0-preview-specific normalizer implementation.

    Extends ODCSNormalizerBase with version 3.0.0-preview-specific support:
    - Explicit support for ODCS version 3.0.0-preview
    - Graceful degradation for missing features (preview versions may have incomplete features)
    - ODCS 3.0.0-preview-specific field mappings (if any)

    This normalizer supports ODCS version 3.0.0-preview and leverages the common
    normalization logic from ODCSNormalizerBase while providing explicit
    version-specific handling for 3.0.0-preview contracts. Preview versions
    may have incomplete feature sets, so this normalizer ensures graceful
    degradation for any missing features.
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODCS version.

        Supports:
        - Exact version "3.0.0-preview"

        Args:
            spec_version: ODCS specification version (e.g., "3.0.0-preview", "3.0.0", "3.0.1")

        Returns:
            True if this normalizer supports the version, False otherwise
        """
        # Support exact version 3.0.0-preview
        return spec_version == "3.0.0-preview"

    def _map_version_specific_fields(
        self,
        odcs_contract: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Map ODCS 3.0.0-preview-specific fields to HubContract format.

        This method is called after all common normalization methods.
        For ODCS 3.0.0-preview, we handle graceful degradation for features
        that may be missing or incomplete in the preview version.

        Preview versions may have:
        - Incomplete feature sets
        - Experimental features that may change
        - Missing optional fields that are present in stable versions

        The base class methods already handle graceful degradation for missing
        fields, but we override this method to be explicit about 3.0.0-preview
        behavior and to ensure proper handling of preview-specific characteristics.

        Args:
            odcs_contract: Raw ODCS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODCS spec version (should be "3.0.0-preview" for this normalizer)
        """
        # Verify version is 3.0.0-preview
        if spec_version != "3.0.0-preview":
            logger.warning(
                "odcs_v3_0_0_preview_unexpected_version",
                expected_version="3.0.0-preview",
                actual_version=spec_version,
                message="ODCSNormalizerV3_0_0_Preview received unexpected version",
            )

        # ODCS 3.0.0-preview is a preview version and may have:
        # - Incomplete feature sets (some features may be missing)
        # - Experimental features that may change
        # - Different field structures compared to stable versions

        # The base class normalization methods already handle missing fields
        # gracefully, so we don't need to explicitly skip processing.
        # However, we can add preview-specific handling here if needed.

        # For preview versions, we ensure that:
        # 1. All available fields are normalized correctly
        # 2. Missing optional fields don't cause errors
        # 3. Any preview-specific experimental features are handled appropriately

        # Check for potential preview-specific characteristics
        # (These checks are defensive - the base class already handles missing fields)
        # Note: Since preview versions may have experimental features, we rely on
        # the base class's graceful degradation for any missing or unexpected fields.

        # Add a warning if the contract seems incomplete (optional, for observability)
        if not odcs_contract.get("schema") and not odcs_contract.get("models"):
            warnings.append(
                "ODCS 3.0.0-preview contract may be incomplete - schema/models section is missing"
            )

        logger.debug(
            "odcs_v3_0_0_preview_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODCS 3.0.0-preview version-specific mapping complete (graceful degradation for missing features)",
        )
