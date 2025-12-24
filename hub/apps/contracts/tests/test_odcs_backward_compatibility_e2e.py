"""
End-to-end tests for ODCS backward compatibility.

Tests the complete normalization flow for all ODCS versions:
- Full contract ingestion and normalization
- Integration with normalize_contract() function
- Real-world contract scenarios
- Complete normalization pipeline

These tests verify that the entire system works correctly for all ODCS versions
without any mocks or stubs.
"""
from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract


class ODCSBackwardCompatibilityE2ETest(TestCase):
    """End-to-end tests for ODCS backward compatibility across all versions."""

    def _create_yaml_contract(self, version: str, include_advanced: bool = True) -> str:
        """Create a YAML contract string for the given version.

        Ensures the contract is detected as ODCS by including required ODCS fields
        (apiVersion and kind) and avoiding ODPS-specific fields.
        Note: The 'version' field in ODCS is the contract version (e.g., "1.0.0"),
        not the spec version. The spec version comes from apiVersion.
        """
        # Use contract_version to avoid confusion with spec version
        base_yaml = f"""apiVersion: odcs.io/v{version}
kind: DataContract
id: e2e-test-{version}
name: E2E Test Contract {version}
version: 1.0.0
description: End-to-end test contract for ODCS {version}
schema:
  fields:
    - name: id
      type: string
      nullable: false
      description: Unique identifier
    - name: name
      type: string
      nullable: false
      description: Name field
    - name: value
      type: number
      nullable: true
      description: Numeric value
info:
  owners:
    - name: Test Owner
      email: owner@example.com
  tags:
    - test
    - e2e
    - {version}
quality:
  default_profile_key: default_profile
  rules:
    - id: rule1
      name: Completeness Check
      type: completeness
      rule: id IS NOT NULL
lifecycle:
  data_source: database
  refresh_cadence: daily"""
        if include_advanced and version in ["3.0.2", "3.0.1"]:
            base_yaml += """
marketplace:
  pricing:
    model: free"""
        return base_yaml

    def test_e2e_odcs_3_0_2_full_normalization(self):
        """E2E test: Full normalization flow for ODCS 3.0.2."""
        raw_contract = self._create_yaml_contract("3.0.2", include_advanced=True)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.2")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(errors), 0)

        # Verify critical fields
        self.assertEqual(hub_contract["id"], "e2e-test-3.0.2")
        self.assertEqual(hub_contract["info"]["name"], "E2E Test Contract 3.0.2")
        self.assertEqual(hub_contract["info"]["version"], "1.0.0")

        # Verify all sections
        self.assertIn("schema", hub_contract)
        self.assertIn("info", hub_contract)
        self.assertIn("quality", hub_contract)
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("marketplace", hub_contract)

        # Verify schema fields
        self.assertIn("fields", hub_contract["schema"])
        self.assertEqual(len(hub_contract["schema"]["fields"]), 3)

    def test_e2e_odcs_3_0_1_full_normalization(self):
        """E2E test: Full normalization flow for ODCS 3.0.1."""
        raw_contract = self._create_yaml_contract("3.0.1", include_advanced=True)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.1")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(errors), 0)

        # Verify critical fields
        self.assertEqual(hub_contract["id"], "e2e-test-3.0.1")
        self.assertEqual(hub_contract["info"]["name"], "E2E Test Contract 3.0.1")

        # Verify marketplace section (3.0.1 feature)
        self.assertIn("marketplace", hub_contract)

    def test_e2e_odcs_3_0_0_full_normalization(self):
        """E2E test: Full normalization flow for ODCS 3.0.0."""
        raw_contract = self._create_yaml_contract("3.0.0", include_advanced=False)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.0")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(errors), 0)

        # Verify critical fields
        self.assertEqual(hub_contract["id"], "e2e-test-3.0.0")
        self.assertEqual(hub_contract["info"]["name"], "E2E Test Contract 3.0.0")

        # Verify core sections
        self.assertIn("schema", hub_contract)
        self.assertIn("info", hub_contract)
        self.assertIn("quality", hub_contract)
        self.assertIn("lifecycle", hub_contract)

    def test_e2e_odcs_3_0_0_preview_full_normalization(self):
        """E2E test: Full normalization flow for ODCS 3.0.0-preview."""
        raw_contract = self._create_yaml_contract("3.0.0-preview", include_advanced=False)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.0-preview")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(errors), 0)

        # Verify critical fields
        self.assertEqual(hub_contract["id"], "e2e-test-3.0.0-preview")
        self.assertEqual(hub_contract["info"]["name"], "E2E Test Contract 3.0.0-preview")

    def test_e2e_odcs_2_2_2_full_normalization(self):
        """E2E test: Full normalization flow for ODCS 2.2.2."""
        raw_contract = self._create_yaml_contract("2.2.2", include_advanced=False)

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Verify detection
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "2.2.2")

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(errors), 0)

        # Verify critical fields
        self.assertEqual(hub_contract["id"], "e2e-test-2.2.2")
        self.assertEqual(hub_contract["info"]["name"], "E2E Test Contract 2.2.2")

    def test_e2e_all_versions_consistent_behavior(self):
        """E2E test: Verify all versions produce consistent behavior."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        results = {}

        for version in versions:
            include_advanced = version in ["3.0.2", "3.0.1"]
            raw_contract = self._create_yaml_contract(version, include_advanced=include_advanced)

            hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
                raw_contract, "yaml"
            )

            results[version] = {
                "hub_contract": hub_contract,
                "spec_type": spec_type,
                "spec_version": spec_version,
                "status": status,
                "errors": errors,
                "warnings": warnings
            }

        # All versions should normalize successfully
        for version, result in results.items():
            self.assertEqual(result["spec_type"], OriginalSpecType.ODCS)
            self.assertEqual(result["spec_version"], version)
            self.assertIsNotNone(result["hub_contract"])
            self.assertIn(
                result["status"],
                [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]
            )
            self.assertEqual(len(result["errors"]), 0)

            # All should have core structure
            hub_contract = result["hub_contract"]
            self.assertIn("id", hub_contract)
            self.assertIn("info", hub_contract)
            self.assertIn("schema", hub_contract)
            self.assertIn("fields", hub_contract["schema"])

    def test_e2e_graceful_degradation_older_versions(self):
        """E2E test: Verify graceful degradation for older versions."""
        # Create contract with 3.0.2 features but use older version
        raw_contract = """
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: graceful-degradation-test
name: Graceful Degradation Test
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
info:
  owners:
    - name: Test Owner
      email: owner@example.com
marketplace:
  pricing:
    model: free
"""

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Should normalize successfully (graceful degradation)
        self.assertIsNotNone(hub_contract)
        self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])

        # Core fields should be present
        self.assertEqual(hub_contract["id"], "graceful-degradation-test")
        self.assertIn("schema", hub_contract)
        self.assertIn("info", hub_contract)

    def test_e2e_json_format_all_versions(self):
        """E2E test: Verify JSON format works for all versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            json_contract = {
                "apiVersion": f"odcs.io/v{version}",
                "kind": "DataContract",
                "id": f"json-test-{version}",
                "name": f"JSON Test Contract {version}",
                "version": "1.0.0",
                "schema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nullable": False
                        }
                    ]
                },
                "info": {
                    "owners": [
                        {
                            "name": "Test Owner",
                            "email": "owner@example.com"
                        }
                    ]
                }
            }

            import json
            raw_contract = json.dumps(json_contract)

            hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
                raw_contract, "json"
            )

            # Should normalize successfully
            self.assertEqual(spec_type, OriginalSpecType.ODCS)
            self.assertEqual(spec_version, version)
            self.assertIsNotNone(hub_contract)
            self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
            self.assertEqual(len(errors), 0)
            self.assertEqual(hub_contract["id"], f"json-test-{version}")

    def test_e2e_complete_contract_all_versions(self):
        """E2E test: Verify complete contracts normalize correctly for all versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            raw_contract = self._create_yaml_contract(version, include_advanced=(version in ["3.0.2", "3.0.1"]))

            hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
                raw_contract, "yaml"
            )

            # Verify complete normalization
            self.assertIsNotNone(hub_contract)
            self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])

            # Verify all expected sections
            self.assertIn("id", hub_contract)
            self.assertIn("info", hub_contract)
            self.assertIn("schema", hub_contract)
            self.assertIn("quality", hub_contract)
            self.assertIn("lifecycle", hub_contract)

            # Verify info section details
            self.assertIn("owners", hub_contract["info"])
            self.assertIn("tags", hub_contract["info"])

            # Verify schema details
            self.assertIn("fields", hub_contract["schema"])
            self.assertGreater(len(hub_contract["schema"]["fields"]), 0)

    def test_e2e_version_detection_and_routing(self):
        """E2E test: Verify version detection and routing works for all versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            raw_contract = self._create_yaml_contract(version, include_advanced=False)

            hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
                raw_contract, "yaml"
            )

            # Verify correct version detection and routing
            self.assertEqual(spec_type, OriginalSpecType.ODCS)
            self.assertEqual(spec_version, version)

            # Verify normalization succeeded (correct normalizer was used)
            self.assertIsNotNone(hub_contract)
            self.assertIn(status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
            self.assertEqual(len(errors), 0)

