"""
Shared edge-case test mixin for normalizer test suites.

Provides standard edge-case tests (unicode, special characters, large documents,
None values, nested structures) that apply across all normalizer implementations.

Usage:
    class MyNormalizerEdgeCaseTest(NormalizerEdgeCaseMixin, TestCase):
        normalizer_class = MyNormalizerClass
        spec_version = "1.0.0"

        def setUp(self):
            self.normalizer = self.normalizer_class()
"""


class NormalizerEdgeCaseMixin:
    """Mixin providing standard edge-case normalization tests.

    Subclasses must define:
        normalizer_class: The normalizer class to instantiate.
        spec_version: The spec version string to use in test data.

    The mixin provides test methods that use self.normalizer (set in setUp).
    """

    normalizer_class = None
    spec_version = None

    def test_edge_case_handles_unicode_characters(self):
        """Normalization handles unicode characters in all text fields."""
        contract_data = self._build_unicode_contract()
        result = self.normalizer.normalize(contract_data, spec_version=self.spec_version)
        self.assertIsNotNone(
            result.hub_contract, "Normalizer should produce a hub_contract with unicode input"
        )
        self.assertIsNotNone(
            result.hub_contract.get("info"), "info section must be present with unicode input"
        )

    def test_edge_case_handles_special_characters(self):
        """Normalization handles special characters (&, <, >, parentheses) correctly."""
        contract_data = self._build_special_chars_contract()
        result = self.normalizer.normalize(contract_data, spec_version=self.spec_version)
        self.assertIsNotNone(
            result.hub_contract,
            "Normalizer should produce a hub_contract with special character input",
        )
        self.assertIsNotNone(
            result.hub_contract.get("info"),
            "info section must be present with special character input",
        )

    def test_edge_case_handles_very_large_documents(self):
        """Normalization handles very large documents (100KB+ strings) correctly."""
        contract_data = self._build_large_contract()
        result = self.normalizer.normalize(contract_data, spec_version=self.spec_version)
        self.assertIsNotNone(
            result.hub_contract, "Normalizer should handle very large documents without crashing"
        )

    def test_edge_case_handles_none_values(self):
        """Normalization handles None values in optional fields gracefully."""
        contract_data = self._build_none_value_contract()
        result = self.normalizer.normalize(contract_data, spec_version=self.spec_version)
        self.assertIsNotNone(
            result.hub_contract, "Normalizer should handle None values without crashing"
        )

    def test_edge_case_handles_nested_structures(self):
        """Normalization handles deeply nested structures correctly."""
        contract_data = self._build_nested_contract()
        result = self.normalizer.normalize(contract_data, spec_version=self.spec_version)
        self.assertIsNotNone(
            result.hub_contract, "Normalizer should handle deeply nested structures"
        )
        self.assertIn(
            "schema", result.hub_contract, "schema key must be present with nested structure input"
        )

    # ── contract builders (override per normalizer type) ──────────────────

    def _build_unicode_contract(self) -> dict:
        """Return a minimal valid contract with unicode characters.
        Override in subclass if the normalizer uses a different contract shape."""
        raise NotImplementedError(
            "Subclass must implement _build_unicode_contract() "
            "to match the normalizer's contract format."
        )

    def _build_special_chars_contract(self) -> dict:
        """Return a minimal valid contract with special characters.
        Override in subclass if the normalizer uses a different contract shape."""
        raise NotImplementedError(
            "Subclass must implement _build_special_chars_contract() "
            "to match the normalizer's contract format."
        )

    def _build_large_contract(self) -> dict:
        """Return a minimal valid contract with a very large field.
        Override in subclass if the normalizer uses a different contract shape."""
        raise NotImplementedError(
            "Subclass must implement _build_large_contract() "
            "to match the normalizer's contract format."
        )

    def _build_none_value_contract(self) -> dict:
        """Return a minimal valid contract with a None value in an optional field.
        Override in subclass if the normalizer uses a different contract shape."""
        raise NotImplementedError(
            "Subclass must implement _build_none_value_contract() "
            "to match the normalizer's contract format."
        )

    def _build_nested_contract(self) -> dict:
        """Return a minimal valid contract with deeply nested structure.
        Override in subclass if the normalizer uses a different contract shape."""
        raise NotImplementedError(
            "Subclass must implement _build_nested_contract() "
            "to match the normalizer's contract format."
        )


class ODCSEdgeCaseMixin(NormalizerEdgeCaseMixin):
    """Edge-case mixin for ODCS normalizers.

    Provides default contract builders for ODCS-format contracts.
    Subclasses only need to set normalizer_class and spec_version.
    """

    def _build_unicode_contract(self) -> dict:
        return {
            "apiVersion": f"odcs.io/v{self.spec_version}",
            "kind": "DataContract",
            "id": "test-unicode",
            "name": "测试合同",
            "version": "1.0.0",
            "description": "测试描述",
            "schema": {"fields": [{"name": "字段名称", "type": "string"}]},
        }

    def _build_special_chars_contract(self) -> dict:
        return {
            "apiVersion": f"odcs.io/v{self.spec_version}",
            "kind": "DataContract",
            "id": "test-special",
            "name": "Test & Co. (Special)",
            "version": "1.0.0",
            "description": "Test <description> & more",
            "schema": {"fields": [{"name": "field-name", "type": "string"}]},
        }

    def _build_large_contract(self) -> dict:
        large_description = "A" * 100000  # 100KB string
        return {
            "apiVersion": f"odcs.io/v{self.spec_version}",
            "kind": "DataContract",
            "id": "test-large",
            "name": "Test Product",
            "version": "1.0.0",
            "description": large_description,
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

    def _build_none_value_contract(self) -> dict:
        return {
            "apiVersion": f"odcs.io/v{self.spec_version}",
            "kind": "DataContract",
            "id": "test-none",
            "name": "Test Product",
            "version": "1.0.0",
            "description": None,
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

    def _build_nested_contract(self) -> dict:
        return {
            "apiVersion": f"odcs.io/v{self.spec_version}",
            "kind": "DataContract",
            "id": "test-nested",
            "name": "Test Product",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                ]
            },
        }


class ODPSEdgeCaseMixin(NormalizerEdgeCaseMixin):
    """Edge-case mixin for ODPS normalizers.

    Provides default contract builders for ODPS-format contracts.
    Subclasses only need to set normalizer_class and spec_version.
    """

    def _build_unicode_contract(self) -> dict:
        return {
            "schema": f"https://opendataproducts.org/schema/v{self.spec_version}",
            "version": self.spec_version,
            "product": {
                "details": {
                    "en": {
                        "productID": "test-unicode",
                        "name": "测试产品",
                        "description": "测试描述",
                    }
                },
                "dataSchema": {"fields": [{"name": "字段名称", "type": "string"}]},
            },
        }

    def _build_special_chars_contract(self) -> dict:
        return {
            "schema": f"https://opendataproducts.org/schema/v{self.spec_version}",
            "version": self.spec_version,
            "product": {
                "details": {
                    "en": {
                        "productID": "test-special",
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                },
                "dataSchema": {"fields": [{"name": "field-name", "type": "string"}]},
            },
        }

    def _build_large_contract(self) -> dict:
        large_description = "A" * 100000  # 100KB string
        return {
            "schema": f"https://opendataproducts.org/schema/v{self.spec_version}",
            "version": self.spec_version,
            "product": {
                "details": {
                    "en": {
                        "productID": "test-large",
                        "name": "Test Product",
                        "description": large_description,
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

    def _build_none_value_contract(self) -> dict:
        return {
            "schema": f"https://opendataproducts.org/schema/v{self.spec_version}",
            "version": self.spec_version,
            "product": {
                "details": {
                    "en": {
                        "productID": "test-none",
                        "name": "Test Product",
                        "description": None,
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

    def _build_nested_contract(self) -> dict:
        return {
            "schema": f"https://opendataproducts.org/schema/v{self.spec_version}",
            "version": self.spec_version,
            "product": {
                "details": {"en": {"productID": "test-nested", "name": "Test Product"}},
                "dataSchema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                        }
                    ]
                },
            },
        }
