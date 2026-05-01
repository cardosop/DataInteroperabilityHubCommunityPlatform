"""
Unit tests for lineage visualization formats.

All tests use real implementations (no mocks of hub services).
Uses real Contract objects from database.
"""

from hub.apps.contracts.lineage import (
    generate_lineage_dot,
    generate_lineage_json,
    generate_lineage_mermaid,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsTransactionTestBase


class TestLineageVisualization(ContractsTransactionTestBase):
    """Tests for lineage visualization formats using real Contract objects."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create real contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "test-contract"}}',
            hub_contract_json={
                "info": {"name": "test-contract"},
                "models": [
                    {
                        "name": "model1",
                        "fields": [
                            {
                                "name": "field1",
                                "lineage": {
                                    "input_fields": [
                                        {
                                            "namespace": "ns1",
                                            "name": "source-contract",
                                            "model": "source-model",
                                            "field": "source-field",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            },
        )

    def test_generate_lineage_json(self):
        """Test JSON format generation."""
        # Act
        result = generate_lineage_json(self.contract)

        # Assert
        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        self.assertIsInstance(result["nodes"], list)
        self.assertIsInstance(result["links"], list)

    def test_generate_lineage_json_has_contract_node(self):
        """Test that JSON includes contract node."""
        result = generate_lineage_json(self.contract)

        contract_nodes = [n for n in result["nodes"] if n.get("type") == "contract"]
        self.assertGreater(len(contract_nodes), 0)

    def test_generate_lineage_dot(self):
        """Test DOT format generation."""
        result = generate_lineage_dot(self.contract)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertIn("digraph Lineage", result)
        self.assertIn("node [shape=box]", result)

    def test_generate_lineage_mermaid(self):
        """Test Mermaid format generation."""
        result = generate_lineage_mermaid(self.contract)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        self.assertIn("graph LR", result)

    def test_generate_lineage_json_includes_declared_contract_dependencies(self):
        """Declared hub_contract_json.lineage.contracts edges appear in visualization JSON."""
        # Phase 227 W1.13.1 — see test_generate_lineage_json_includes_referenced_by_edges
        # for the rationale on the minimum-viable structural-floor shape.
        # ``_min_models()`` returns a fresh structure on each call so
        # the two contracts don't share inner-dict references.
        def _min_models():
            return [
                {
                    "name": "default",
                    "fields": [
                        {"name": "id", "data_type": "string", "nullable": False},
                    ],
                }
            ]

        provider = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "lineage-provider"}}',
            hub_contract_json={
                "info": {"name": "lineage-provider", "domain": "acme.test"},
                "models": _min_models(),
            },
        )
        consumer = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "lineage-consumer"}}',
            hub_contract_json={
                "info": {"name": "lineage-consumer"},
                "lineage": {
                    "contracts": [
                        {"namespace": "acme.test", "name": "lineage-provider"},
                    ]
                },
                "models": _min_models(),
            },
        )

        result = generate_lineage_json(consumer)

        self.assertIsNotNone(result)
        link_targets = {e["target"] for e in result["links"]}
        self.assertIn(str(consumer.id), link_targets)
        self.assertTrue(
            any(e["source"] == str(provider.id) and e["target"] == str(consumer.id) for e in result["links"]),
            msg=f"Expected edge provider→consumer in links: {result['links']}",
        )

    def test_generate_lineage_json_includes_referenced_by_edges(self):
        """Other contracts that declare this contract in lineage.contracts appear as edges."""
        # Phase 227 W1.13.1 — populate the minimum-viable structural-floor
        # shape (1 model, 1 field, type=string, nullable=False) so the
        # fixture remains valid under the L3 unconditional floor
        # enforcement. The lineage assertions don't depend on field
        # contents; the fields are pure structural-floor satisfiers.
        #
        # ``_min_models()`` returns a fresh list-of-dicts so the two
        # contracts don't share the SAME inner-dict reference (which
        # would let a test-time mutation of one contract's models
        # silently propagate to the other).
        def _min_models():
            return [
                {
                    "name": "default",
                    "fields": [
                        {"name": "id", "data_type": "string", "nullable": False},
                    ],
                }
            ]

        core = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "refby-core"}}',
            hub_contract_json={
                "info": {"name": "refby-core", "domain": "tenant.refby"},
                "models": _min_models(),
            },
        )
        dependent = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "refby-dependent"}}',
            hub_contract_json={
                "info": {"name": "refby-dependent"},
                "lineage": {
                    "contracts": [{"namespace": "tenant.refby", "name": "refby-core"}],
                },
                "models": _min_models(),
            },
        )

        result = generate_lineage_json(core)

        self.assertTrue(
            any(e["source"] == str(core.id) and e["target"] == str(dependent.id) for e in result["links"]),
            msg=f"Expected edge core→dependent in links: {result['links']}",
        )

    def test_generate_lineage_json_with_empty_lineage(self):
        """Test JSON format generation with contract that has no lineage."""
        contract_no_lineage = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-lineage"}}',
            hub_contract_json={
                "info": {"name": "no-lineage"},
                # No lineage field
            },
        )

        result = generate_lineage_json(contract_no_lineage)

        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        # Should still have at least the contract node
        self.assertGreater(len(result["nodes"]), 0)

    def test_generate_lineage_json_with_missing_hub_contract_json(self):
        """Test JSON format generation with contract missing hub_contract_json."""
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "no-hub"}}',
            # hub_contract_json is None
        )

        result = generate_lineage_json(contract_no_hub)

        # Should handle gracefully - may return empty or minimal structure
        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("links", result)

    def test_generate_lineage_dot_with_empty_lineage(self):
        """Test DOT format generation with empty lineage."""
        contract_empty = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "empty"}}',
            hub_contract_json={"info": {"name": "empty"}, "lineage": {}},
        )

        result = generate_lineage_dot(contract_empty)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        # Should still generate valid DOT format
        self.assertIn("digraph", result.lower())

    def test_generate_lineage_mermaid_with_empty_lineage(self):
        """Test Mermaid format generation with empty lineage."""
        contract_empty = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "empty"}}',
            hub_contract_json={"info": {"name": "empty"}, "lineage": {}},
        )

        result = generate_lineage_mermaid(contract_empty)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        # Should still generate valid Mermaid format
        self.assertIn("graph", result.lower())

    def test_generate_lineage_json_with_large_lineage(self):
        """Test JSON format generation with large lineage graph."""
        large_lineage = {
            "contracts": [{"namespace": f"ns{i}", "name": f"contract{i}"} for i in range(100)],
            "entries": [],
        }

        contract_large = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "large"}}',
            hub_contract_json={"info": {"name": "large"}, "lineage": large_lineage},
        )

        result = generate_lineage_json(contract_large)

        self.assertIsNotNone(result)
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        # Should handle large graphs
        self.assertIsInstance(result["nodes"], list)

    def test_generate_lineage_dot_with_special_characters(self):
        """Test DOT format generation with special characters in names."""
        contract_special = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "special-chars"}}',
            hub_contract_json={
                "info": {"name": "contract-name_v2"},
                "lineage": {"contracts": [{"namespace": "ns-1", "name": "contract.name"}]},
            },
        )

        result = generate_lineage_dot(contract_special)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        # Should handle special characters in DOT format
        self.assertIn("digraph", result.lower())

    def test_generate_lineage_mermaid_with_unicode(self):
        """Test Mermaid format generation with unicode characters."""
        contract_unicode = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_format=OriginalFormat.JSON,
            original_raw='{"info": {"name": "unicode"}}',
            hub_contract_json={
                "info": {"name": "产品名称"},
                "lineage": {"contracts": [{"namespace": "命名空间", "name": "合同名称"}]},
            },
        )

        result = generate_lineage_mermaid(contract_unicode)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        # Should handle unicode characters
        self.assertIn("graph", result.lower())

    def test_generate_lineage_json_structure_consistency(self):
        """Test that JSON format has consistent structure."""
        result = generate_lineage_json(self.contract)

        # Verify structure
        self.assertIsInstance(result, dict)
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        self.assertIsInstance(result["nodes"], list)
        self.assertIsInstance(result["links"], list)

        # Verify node structure if nodes exist
        if result["nodes"]:
            node = result["nodes"][0]
            self.assertIsInstance(node, dict)
            # Nodes should have at least id and type
            self.assertIn("id", node)
            self.assertIn("type", node)

        # Verify link structure if links exist
        if result["links"]:
            link = result["links"][0]
            self.assertIsInstance(link, dict)
            # Links should have source and target
            self.assertIn("source", link)
            self.assertIn("target", link)

    def test_generate_lineage_dot_valid_syntax(self):
        """Test that DOT format generates valid syntax."""
        result = generate_lineage_dot(self.contract)

        # Basic DOT syntax checks
        self.assertIn("digraph", result)
        self.assertIn("{", result)
        self.assertIn("}", result)
        # Should not have syntax errors (basic check)
        self.assertNotIn("{{", result)  # No double braces
        self.assertNotIn("}}", result)

    def test_generate_lineage_mermaid_valid_syntax(self):
        """Test that Mermaid format generates valid syntax."""
        result = generate_lineage_mermaid(self.contract)

        # Basic Mermaid syntax checks
        self.assertIn("graph", result.lower())
        # Should have node definitions
        self.assertIsInstance(result, str)
        # Should not have obvious syntax errors
        self.assertNotIn("[[", result)  # No double brackets
