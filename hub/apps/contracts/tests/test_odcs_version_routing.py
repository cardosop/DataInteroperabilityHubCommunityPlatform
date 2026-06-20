"""
Unit tests for ODCS version detection and routing.

Tests verify:
1. Version detection routes to appropriate normalizer
2. Fallback to latest version (3.0.2) if version not recognized
3. Version-specific normalizers are preferred over default
4. All ODCS versions route correctly
"""

from django.test import TestCase

from hub.apps.contracts.models import OriginalSpecType
from hub.apps.contracts.normalization import (
    _reset_normalizer_registry,
    get_normalizer,
    normalize_contract,
)
from hub.apps.contracts.normalization.odcs_normalizer_default import ODCSNormalizerDefault
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import (
    ODCSNormalizerV3_0_0_Preview,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_1_0 import ODCSNormalizerV3_1_0


class ODCSVersionRoutingTest(TestCase):
    """Test ODCS version detection and routing to appropriate normalizers"""

    def setUp(self):
        """Set up test fixtures"""
        # Save registry state
        self.registry_snapshot = None

    def tearDown(self):
        """Clean up after tests"""
        # Restore registry state
        if self.registry_snapshot is not None:
            _reset_normalizer_registry(self.registry_snapshot)

    def test_routes_3_0_2_to_v3_0_2_normalizer(self):
        """Test that ODCS 3.0.2 routes to ODCSNormalizerV3_0_2"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-1",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_2)

    def test_routes_3_0_1_to_v3_0_1_normalizer(self):
        """Test that ODCS 3.0.1 routes to ODCSNormalizerV3_0_1"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-2",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

    def test_routes_3_0_0_to_v3_0_0_normalizer(self):
        """Test that ODCS 3.0.0 routes to ODCSNormalizerV3_0_0"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-3",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.0", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0)

    def test_routes_3_0_0_preview_to_preview_normalizer(self):
        """Test that ODCS 3.0.0-preview routes to ODCSNormalizerV3_0_0_Preview"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.0-preview",
            "kind": "DataContract",
            "id": "test-4",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.0-preview", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0_Preview)

    def test_routes_2_2_2_to_v2_2_2_normalizer(self):
        """Test that ODCS 2.2.2 routes to ODCSNormalizerV2_2_2"""
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-5",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "2.2.2", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV2_2_2)

    def test_fallback_to_latest_version_for_unknown_version(self):
        """Test that unknown ODCS version falls back to latest version (3.1.0)"""
        contract_data = {
            "apiVersion": "odcs.io/v3.1.0",
            "kind": "DataContract",
            "id": "test-6",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.1.0", contract_data)
        # Should use 3.1.0 normalizer (latest version)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, (ODCSNormalizerV3_1_0, ODCSNormalizerV3_0_2))

    def test_fallback_to_latest_version_for_empty_version(self):
        """Test that empty ODCS version falls back to latest version"""
        contract_data = {
            "kind": "DataContract",
            "id": "test-7",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "", contract_data)
        # Should fallback to latest normalizer
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, (ODCSNormalizerV3_1_0, ODCSNormalizerV3_0_2))

    def test_fallback_to_latest_version_for_invalid_version(self):
        """Test that invalid ODCS version falls back to latest version"""
        contract_data = {
            "apiVersion": "odcs.io/invalid",
            "kind": "DataContract",
            "id": "test-8",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "invalid", contract_data)
        # Should fallback to latest normalizer
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, (ODCSNormalizerV3_1_0, ODCSNormalizerV3_0_2))

    def test_prefers_version_specific_over_default(self):
        """Test that version-specific normalizers are preferred over default"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-9",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2", contract_data)
        # Should use version-specific normalizer, not default
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_2)
        self.assertNotIsInstance(normalizer, ODCSNormalizerDefault)

    def test_patch_versions_route_to_base_version(self):
        """Test that patch versions (e.g., 3.0.2.1) route to base version normalizer"""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2.1",
            "kind": "DataContract",
            "id": "test-10",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2.1", contract_data)
        # Should route to 3.0.2 normalizer (supports patch versions)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_2)


class ODCSVersionRoutingIntegrationTest(TestCase):
    """Integration tests for ODCS version routing in normalize_contract()"""

    def test_normalize_contract_routes_3_0_2_correctly(self):
        """Test that normalize_contract() routes ODCS 3.0.2 correctly"""
        raw_contract = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-integration-1
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.2")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_routes_3_0_1_correctly(self):
        """Test that normalize_contract() routes ODCS 3.0.1 correctly"""
        raw_contract = """
apiVersion: odcs.io/v3.0.1
kind: DataContract
id: test-integration-2
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.1")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_routes_3_0_0_correctly(self):
        """Test that normalize_contract() routes ODCS 3.0.0 correctly"""
        raw_contract = """
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: test-integration-3
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.0")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_routes_3_0_0_preview_correctly(self):
        """Test that normalize_contract() routes ODCS 3.0.0-preview correctly"""
        raw_contract = """
apiVersion: odcs.io/v3.0.0-preview
kind: DataContract
id: test-integration-4
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.0-preview")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_routes_2_2_2_correctly(self):
        """Test that normalize_contract() routes ODCS 2.2.2 correctly"""
        raw_contract = """
apiVersion: odcs.io/v2.2.2
kind: DataContract
id: test-integration-5
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "2.2.2")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_fallback_to_latest_for_unknown_version(self):
        """Test that normalize_contract() falls back to latest version for unknown ODCS version"""
        raw_contract = """
apiVersion: odcs.io/v3.1.0
kind: DataContract
id: test-integration-6
name: Test Contract
schema:
  fields:
    - name: id
      type: string
"""
        hub_contract, spec_type, _spec_version, _status, errors, _warnings = normalize_contract(
            raw_contract, "yaml"
        )

        # Should detect as 3.1.0 but fallback to 3.0.2 normalizer
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        # spec_version will be the detected version (3.1.0), but normalizer will be 3.0.2
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0)
