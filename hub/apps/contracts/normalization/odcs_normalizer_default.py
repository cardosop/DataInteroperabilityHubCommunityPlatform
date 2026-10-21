"""
ODCS Default Normalizer

Default implementation of ODCSNormalizerBase that supports all ODCS versions.
This maintains backward compatibility with the existing ODCSNormalizer behavior.
"""

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase


class ODCSNormalizerDefault(ODCSNormalizerBase):
    """
    Default ODCS normalizer that supports all ODCS versions.

    This is used for backward compatibility with the existing ODCSNormalizer
    behavior, which did not have version-specific logic.

    For version-specific behavior, use version-specific normalizers like:
    - ODCSNormalizerV3_0_2
    - ODCSNormalizerV3_0_1
    - ODCSNormalizerV3_0_0
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Support all ODCS versions (backward compatibility).

        This maintains the original behavior where ODCSNormalizer supported
        all ODCS versions without version-specific logic.

        Args:
            spec_version: ODCS specification version (e.g., "3.0.2", "3.0.1", "3.0.0")

        Returns:
            True for all ODCS versions
        """
        # Support all versions for backward compatibility
        return True
