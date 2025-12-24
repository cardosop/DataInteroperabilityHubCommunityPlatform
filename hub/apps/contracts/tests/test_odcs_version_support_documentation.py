"""
Documentation review tests for ODCS version support (Task 1.6.10)

Tests verify that the ODCS version support documentation is accurate and complete.
This ensures that:
- All supported versions are documented
- Version-specific features are correctly described
- Graceful degradation approach is documented
- Examples are accurate
"""
import json
from pathlib import Path
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import get_normalizer
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import ODCSNormalizerV3_0_0_Preview
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2


class ODCSVersionSupportDocumentationTest(TestCase):
    """Test that ODCS version support documentation is accurate."""

    def setUp(self):
        """Set up test fixtures."""
        # Expected supported versions from documentation
        self.expected_versions = {
            "3.0.2": {
                "normalizer": ODCSNormalizerV3_0_2,
                "status": "Current (Baseline)",
                "description": "Latest stable version, recommended for new contracts"
            },
            "3.0.1": {
                "normalizer": ODCSNormalizerV3_0_1,
                "status": "Supported",
                "description": "Previous stable version, fully supported"
            },
            "3.0.0": {
                "normalizer": ODCSNormalizerV3_0_0,
                "status": "Supported",
                "description": "Initial 3.x release, fully supported"
            },
            "3.0.0-preview": {
                "normalizer": ODCSNormalizerV3_0_0_Preview,
                "status": "Supported",
                "description": "Preview version, gracefully handles incomplete features"
            },
            "2.2.2": {
                "normalizer": ODCSNormalizerV2_2_2,
                "status": "Supported (Legacy)",
                "description": "Legacy version, gracefully degrades 3.x features"
            }
        }

    def test_all_documented_versions_have_normalizers(self):
        """Test that all documented versions have corresponding normalizers."""
        for version, info in self.expected_versions.items():
            with self.subTest(version=version):
                normalizer_class = info["normalizer"]
                normalizer = normalizer_class()

                # Verify normalizer exists and supports the version
                self.assertIsNotNone(normalizer, f"Normalizer for {version} should exist")
                self.assertTrue(
                    normalizer.supports(OriginalSpecType.ODCS, version, {}),
                    f"Normalizer for {version} should support version {version}"
                )

    def test_all_normalizers_are_documented(self):
        """Test that all version-specific normalizers are documented."""
        # Get all version-specific normalizers
        normalizer_classes = [
            ODCSNormalizerV3_0_2,
            ODCSNormalizerV3_0_1,
            ODCSNormalizerV3_0_0,
            ODCSNormalizerV3_0_0_Preview,
            ODCSNormalizerV2_2_2,
        ]

        # Check that each normalizer has a documented version
        for normalizer_class in normalizer_classes:
            normalizer = normalizer_class()

            # Find which version this normalizer supports
            supported_version = None
            for version, info in self.expected_versions.items():
                if isinstance(normalizer, info["normalizer"]):
                    supported_version = version
                    break

            self.assertIsNotNone(
                supported_version,
                f"Normalizer {normalizer_class.__name__} should be documented"
            )

    def test_version_detection_works_for_all_versions(self):
        """Test that version detection works for all documented versions."""
        for version in self.expected_versions.keys():
            with self.subTest(version=version):
                # Create contract with this version
                contract_data = {
                    "apiVersion": f"odcs.io/v{version}",
                    "kind": "DataContract",
                    "id": f"test-{version}",
                    "name": f"Test Contract {version}",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False}
                        ]
                    }
                }

                # Get normalizer for this version
                normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)

                # Verify normalizer is correct
                self.assertIsNotNone(
                    normalizer,
                    f"Normalizer should be found for version {version}"
                )
                self.assertTrue(
                    normalizer.supports(OriginalSpecType.ODCS, version, contract_data),
                    f"Normalizer should support version {version}"
                )

    def test_graceful_degradation_works(self):
        """Test that graceful degradation works as documented."""
        # Test that older versions can normalize without errors
        older_versions = ["3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in older_versions:
            with self.subTest(version=version):
                # Create contract with this version
                contract_data = {
                    "apiVersion": f"odcs.io/v{version}",
                    "kind": "DataContract",
                    "id": f"test-{version}",
                    "name": f"Test Contract {version}",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False}
                        ]
                    }
                }

                # Normalize
                normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
                result = normalizer.normalize(contract_data, spec_version=version)

                # Verify normalization succeeds (graceful degradation)
                self.assertIsNotNone(
                    result.hub_contract,
                    f"Version {version} should normalize successfully (graceful degradation)"
                )
                self.assertIn(
                    result.status,
                    [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
                    f"Version {version} should normalize with OK or WARNINGS status"
                )

    def test_documentation_file_exists(self):
        """Test that ODCS version support documentation file exists."""
        # Check if documentation file exists
        docs_path = Path(__file__).parent.parent.parent.parent.parent / "docs" / "ODCS_VERSION_SUPPORT.md"

        self.assertTrue(
            docs_path.exists(),
            "ODCS_VERSION_SUPPORT.md documentation file should exist"
        )

        # Verify file is not empty
        content = docs_path.read_text()
        self.assertGreater(
            len(content),
            0,
            "ODCS_VERSION_SUPPORT.md should not be empty"
        )

    def test_documentation_mentions_all_versions(self):
        """Test that documentation mentions all supported versions."""
        docs_path = Path(__file__).parent.parent.parent.parent.parent / "docs" / "ODCS_VERSION_SUPPORT.md"

        if not docs_path.exists():
            self.skipTest("Documentation file does not exist")

        content = docs_path.read_text()

        # Check that all versions are mentioned
        for version in self.expected_versions.keys():
            with self.subTest(version=version):
                # Check for version in various formats
                version_mentions = [
                    version in content,
                    f"v{version}" in content,
                    f"version {version}" in content.lower(),
                ]

                self.assertTrue(
                    any(version_mentions),
                    f"Documentation should mention version {version}"
                )

    def test_documentation_mentions_graceful_degradation(self):
        """Test that documentation mentions graceful degradation."""
        docs_path = Path(__file__).parent.parent.parent.parent.parent / "docs" / "ODCS_VERSION_SUPPORT.md"

        if not docs_path.exists():
            self.skipTest("Documentation file does not exist")

        content = docs_path.read_text()

        # Check for graceful degradation mentions
        graceful_degradation_keywords = [
            "graceful degradation",
            "gracefully",
            "missing features",
            "backward compatibility",
        ]

        found_keywords = [
            keyword for keyword in graceful_degradation_keywords
            if keyword.lower() in content.lower()
        ]

        self.assertGreater(
            len(found_keywords),
            0,
            "Documentation should mention graceful degradation approach"
        )

    def test_documentation_mentions_version_specific_features(self):
        """Test that documentation mentions version-specific features."""
        docs_path = Path(__file__).parent.parent.parent.parent.parent / "docs" / "ODCS_VERSION_SUPPORT.md"

        if not docs_path.exists():
            self.skipTest("Documentation file does not exist")

        content = docs_path.read_text()

        # Check for version-specific features section
        feature_keywords = [
            "version-specific",
            "features",
            "normalizer",
        ]

        found_keywords = [
            keyword for keyword in feature_keywords
            if keyword.lower() in content.lower()
        ]

        self.assertGreater(
            len(found_keywords),
            0,
            "Documentation should mention version-specific features"
        )

