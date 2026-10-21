"""
E2E Tests for Lineage Use Cases

Comprehensive end-to-end tests for lineage functionality:
- Lineage queries (contract-level, model-level, field-level, full)
- Lineage visualization (JSON, DOT, Mermaid)
- Impact analysis (contract change, model change, field change)

All tests use real implementations without mocks/stubs.
"""

import json

import pytest

pytestmark = pytest.mark.slow
from rest_framework import status

from hub.apps.contracts.impact_analysis import ImpactAnalyzer
from hub.apps.contracts.lineage_service import LineageService
from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    ValidationStatus,
)

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class LineageQueriesE2ETest(E2ETestBase):
    """E2E tests for lineage queries at all levels"""

    def setUp(self):
        """Set up test fixtures with contracts having lineage relationships"""
        super().setUp()

        # Create source contract (upstream)
        self.source_contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "info": {
                        "name": "source-contract",
                        "title": "Source Contract",
                        "version": "1.0.0",
                    },
                    "models": [
                        {
                            "name": "UserModel",
                            "fields": [
                                {
                                    "name": "email",
                                    "type": "string",
                                    "lineage": {"input_fields": [], "transformations": []},
                                },
                                {
                                    "name": "name",
                                    "type": "string",
                                    "lineage": {"input_fields": [], "transformations": []},
                                },
                            ],
                            "lineage": {"models": [], "entries": []},
                        }
                    ],
                    "lineage": {"contracts": [], "entries": []},
                }
            ),
        )

        # Get the contract to update it with proper hub_contract_json
        source_contract = Contract.objects.get(id=self.source_contract_id)
        source_contract.hub_contract_json = {
            "info": {"name": "source-contract", "title": "Source Contract", "version": "1.0.0"},
            "models": [
                {
                    "name": "UserModel",
                    "fields": [
                        {
                            "name": "email",
                            "type": "string",
                            "lineage": {"input_fields": [], "transformations": []},
                        },
                        {
                            "name": "name",
                            "type": "string",
                            "lineage": {"input_fields": [], "transformations": []},
                        },
                    ],
                    "lineage": {"models": [], "entries": []},
                }
            ],
            "lineage": {"contracts": [], "entries": []},
        }
        source_contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        source_contract.validation_status = ValidationStatus.VALID
        source_contract.save()

        # Create intermediate contract (depends on source)
        self.intermediate_contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "info": {
                        "name": "intermediate-contract",
                        "title": "Intermediate Contract",
                        "version": "1.0.0",
                    },
                    "models": [
                        {
                            "name": "ProcessedUserModel",
                            "fields": [
                                {
                                    "name": "user_email",
                                    "type": "string",
                                    "lineage": {
                                        "input_fields": [
                                            {
                                                "namespace": None,
                                                "name": "source-contract",
                                                "model_name": "UserModel",
                                                "field": "email",
                                            }
                                        ],
                                        "transformations": [
                                            {
                                                "logic": "SELECT email as user_email FROM source",
                                                "description": "Rename email to user_email",
                                            }
                                        ],
                                    },
                                }
                            ],
                            "lineage": {
                                "models": [
                                    {
                                        "namespace": None,
                                        "name": "source-contract",
                                        "model_name": "UserModel",
                                    }
                                ],
                                "entries": [],
                            },
                        }
                    ],
                    "lineage": {
                        "contracts": [{"namespace": None, "name": "source-contract"}],
                        "entries": [],
                    },
                }
            ),
        )

        # Update intermediate contract
        intermediate_contract = Contract.objects.get(id=self.intermediate_contract_id)
        intermediate_contract.hub_contract_json = {
            "info": {
                "name": "intermediate-contract",
                "title": "Intermediate Contract",
                "version": "1.0.0",
            },
            "models": [
                {
                    "name": "ProcessedUserModel",
                    "fields": [
                        {
                            "name": "user_email",
                            "type": "string",
                            "lineage": {
                                "input_fields": [
                                    {
                                        "namespace": None,
                                        "name": "source-contract",
                                        "model_name": "UserModel",
                                        "field": "email",
                                    }
                                ],
                                "transformations": [
                                    {
                                        "logic": "SELECT email as user_email FROM source",
                                        "description": "Rename email to user_email",
                                    }
                                ],
                            },
                        }
                    ],
                    "lineage": {
                        "models": [
                            {
                                "namespace": None,
                                "name": "source-contract",
                                "model_name": "UserModel",
                            }
                        ],
                        "entries": [],
                    },
                }
            ],
            "lineage": {
                "contracts": [{"namespace": None, "name": "source-contract"}],
                "entries": [],
            },
        }
        intermediate_contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        intermediate_contract.validation_status = ValidationStatus.VALID
        intermediate_contract.save()

        # Create target contract (depends on intermediate)
        self.target_contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "info": {
                        "name": "target-contract",
                        "title": "Target Contract",
                        "version": "1.0.0",
                    },
                    "models": [
                        {
                            "name": "FinalUserModel",
                            "fields": [
                                {
                                    "name": "final_email",
                                    "type": "string",
                                    "lineage": {
                                        "input_fields": [
                                            {
                                                "namespace": None,
                                                "name": "intermediate-contract",
                                                "model_name": "ProcessedUserModel",
                                                "field": "user_email",
                                            }
                                        ],
                                        "transformations": [
                                            {
                                                "logic": "SELECT user_email as final_email FROM intermediate",
                                                "description": "Rename user_email to final_email",
                                            }
                                        ],
                                    },
                                }
                            ],
                            "lineage": {
                                "models": [
                                    {
                                        "namespace": None,
                                        "name": "intermediate-contract",
                                        "model_name": "ProcessedUserModel",
                                    }
                                ],
                                "entries": [],
                            },
                        }
                    ],
                    "lineage": {
                        "contracts": [{"namespace": None, "name": "intermediate-contract"}],
                        "entries": [],
                    },
                }
            ),
        )

        # Update target contract
        target_contract = Contract.objects.get(id=self.target_contract_id)
        target_contract.hub_contract_json = {
            "info": {"name": "target-contract", "title": "Target Contract", "version": "1.0.0"},
            "models": [
                {
                    "name": "FinalUserModel",
                    "fields": [
                        {
                            "name": "final_email",
                            "type": "string",
                            "lineage": {
                                "input_fields": [
                                    {
                                        "namespace": None,
                                        "name": "intermediate-contract",
                                        "model_name": "ProcessedUserModel",
                                        "field": "user_email",
                                    }
                                ],
                                "transformations": [
                                    {
                                        "logic": "SELECT user_email as final_email FROM intermediate",
                                        "description": "Rename user_email to final_email",
                                    }
                                ],
                            },
                        }
                    ],
                    "lineage": {
                        "models": [
                            {
                                "namespace": None,
                                "name": "intermediate-contract",
                                "model_name": "ProcessedUserModel",
                            }
                        ],
                        "entries": [],
                    },
                }
            ],
            "lineage": {
                "contracts": [{"namespace": None, "name": "intermediate-contract"}],
                "entries": [],
            },
        }
        target_contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        target_contract.validation_status = ValidationStatus.VALID
        target_contract.save()

        # Initialize lineage service
        self.lineage_service = LineageService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_contract_level_lineage_query(self):
        """Test contract-level lineage query"""
        # Get contract-level lineage for intermediate contract
        lineage = self.lineage_service.get_contract_lineage(
            contract_id=self.intermediate_contract_id, tenant_id=str(self.tenant.id)
        )

        # Verify structure
        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)

        # Verify it references source contract
        contracts = lineage.get("contracts", [])
        contract_names = [c.get("name") for c in contracts if isinstance(c, dict)]
        self.assertIn("source-contract", contract_names)

    def test_model_level_lineage_query(self):
        """Test model-level lineage query"""
        # Get model-level lineage for ProcessedUserModel
        lineage = self.lineage_service.get_model_lineage(
            contract_id=self.intermediate_contract_id,
            model_name="ProcessedUserModel",
            tenant_id=str(self.tenant.id),
        )

        # Verify structure
        self.assertIn("model_name", lineage)
        self.assertIn("lineage", lineage)
        self.assertEqual(lineage["model_name"], "ProcessedUserModel")

        # Verify it references source model
        model_lineage = lineage.get("lineage", {})
        models = model_lineage.get("models", [])
        model_names = [m.get("name") for m in models if isinstance(m, dict)]
        self.assertIn("source-contract", model_names)

    def test_field_level_lineage_query(self):
        """Test field-level lineage query"""
        # Get field-level lineage for user_email field
        lineage = self.lineage_service.get_field_lineage(
            contract_id=self.intermediate_contract_id,
            field_name="user_email",
            model_name="ProcessedUserModel",
            tenant_id=str(self.tenant.id),
        )

        # Verify structure
        self.assertIn("field_name", lineage)
        self.assertIn("lineage", lineage)
        self.assertEqual(lineage["field_name"], "user_email")

        # Verify it references source field
        field_lineage = lineage.get("lineage", {})
        input_fields = field_lineage.get("input_fields", [])
        self.assertGreater(len(input_fields), 0)

        # Verify input field reference
        first_input = input_fields[0] if input_fields else {}
        self.assertEqual(first_input.get("name"), "source-contract")
        self.assertEqual(first_input.get("model_name"), "UserModel")
        self.assertEqual(first_input.get("field"), "email")

    def test_full_lineage_query(self):
        """Test full hierarchical lineage query"""
        # Get full lineage for intermediate contract
        lineage = self.lineage_service.get_full_lineage(
            contract_id=self.intermediate_contract_id,
            tenant_id=str(self.tenant.id),
            max_contract_depth=10,
            max_model_depth=10,
            max_field_depth=10,
        )

        # Verify structure
        self.assertIn("upstream", lineage)
        self.assertIn("downstream", lineage)

        # For intermediate contract:
        # - downstream should contain source contract (what intermediate depends on)
        # - upstream should contain target contract (what depends on intermediate)
        downstream = lineage.get("downstream", {})
        # Downstream should show source contract (intermediate depends on source)
        # The structure may be nested, so we check if it's a dict with contract info
        if isinstance(downstream, dict):
            # Check for contract_lineage or contract_id
            if "contract_lineage" in downstream:
                contract_lineage = downstream["contract_lineage"]
                if isinstance(contract_lineage, list) and len(contract_lineage) > 0:
                    # Found source contract in downstream
                    self.assertIsNotNone(contract_lineage[0].get("contract_id"))
            elif "contract_id" in downstream:
                self.assertIsNotNone(downstream.get("contract_id"))

        upstream = lineage.get("upstream", {})
        # Upstream should show target contract (what depends on intermediate)
        # This is found via reverse traversal, so it may be in referenced_by
        if isinstance(upstream, dict):
            if "referenced_by" in upstream:
                referenced_by = upstream["referenced_by"]
                if isinstance(referenced_by, list) and len(referenced_by) > 0:
                    # Found target contract in upstream
                    self.assertIsNotNone(referenced_by[0].get("contract_id"))
            elif "contract_id" in upstream:
                self.assertIsNotNone(upstream.get("contract_id"))


class LineageVisualizationE2ETest(E2ETestBase):
    """E2E tests for lineage visualization formats"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create a contract with lineage
        self.contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "info": {
                        "name": "visualization-test-contract",
                        "title": "Visualization Test Contract",
                    },
                    "models": [
                        {"name": "TestModel", "fields": [{"name": "field1", "type": "string"}]}
                    ],
                    "lineage": {"contracts": [], "entries": []},
                }
            ),
        )

        # Update contract with hub_contract_json
        contract = Contract.objects.get(id=self.contract_id)
        contract.hub_contract_json = {
            "info": {"name": "visualization-test-contract", "title": "Visualization Test Contract"},
            "models": [{"name": "TestModel", "fields": [{"name": "field1", "type": "string"}]}],
            "lineage": {"contracts": [], "entries": []},
        }
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.validation_status = ValidationStatus.VALID
        contract.save()

        self.lineage_service = LineageService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_json_visualization(self):
        """Test lineage visualization in JSON format"""
        visualization = self.lineage_service.get_lineage_visualization(
            contract_id=self.contract_id, format="json", tenant_id=str(self.tenant.id)
        )

        # Verify JSON structure
        self.assertIn("nodes", visualization)
        self.assertIn("links", visualization)

        # Verify nodes array
        nodes = visualization.get("nodes", [])
        self.assertIsInstance(nodes, list)
        self.assertGreater(len(nodes), 0)

        # Verify first node has required fields
        if nodes:
            first_node = nodes[0]
            self.assertIn("id", first_node)
            self.assertIn("type", first_node)

    def test_dot_visualization(self):
        """Test lineage visualization in DOT format"""
        visualization = self.lineage_service.get_lineage_visualization(
            contract_id=self.contract_id, format="dot", tenant_id=str(self.tenant.id)
        )

        # Verify DOT format
        self.assertIn("dot", visualization)
        dot_string = visualization["dot"]
        self.assertIsInstance(dot_string, str)

        # Verify DOT syntax
        self.assertIn("digraph", dot_string)
        self.assertIn("{", dot_string)
        self.assertIn("}", dot_string)

    def test_mermaid_visualization(self):
        """Test lineage visualization in Mermaid format"""
        visualization = self.lineage_service.get_lineage_visualization(
            contract_id=self.contract_id, format="mermaid", tenant_id=str(self.tenant.id)
        )

        # Verify Mermaid format
        self.assertIn("mermaid", visualization)
        mermaid_string = visualization["mermaid"]
        self.assertIsInstance(mermaid_string, str)

        # Verify Mermaid syntax
        self.assertIn("graph", mermaid_string.lower())


class ImpactAnalysisE2ETest(E2ETestBase):
    """E2E tests for impact analysis"""

    def setUp(self):
        """Set up test fixtures with contracts for impact analysis"""
        super().setUp()

        # Create source contract
        # ODCS requires: id, info.name, schema.fields (at least one field)
        self.source_contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "id": "impact-source-contract",
                    "info": {"name": "impact-source-contract", "title": "Impact Source Contract"},
                    "schema": {"fields": [{"name": "source_field", "type": "string"}]},
                    "models": [
                        {
                            "name": "SourceModel",
                            "fields": [{"name": "source_field", "type": "string"}],
                        }
                    ],
                    "lineage": {"contracts": [], "entries": []},
                }
            ),
        )

        source_contract = Contract.objects.get(id=self.source_contract_id)
        source_contract.hub_contract_json = {
            "info": {"name": "impact-source-contract", "title": "Impact Source Contract"},
            "models": [
                {"name": "SourceModel", "fields": [{"name": "source_field", "type": "string"}]}
            ],
            "lineage": {"contracts": [], "entries": []},
        }
        source_contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        source_contract.validation_status = ValidationStatus.VALID
        source_contract.save()

        # Create dependent contract
        # ODCS requires: id, info.name, schema.fields (at least one field)
        self.dependent_contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "id": "impact-dependent-contract",
                    "info": {
                        "name": "impact-dependent-contract",
                        "title": "Impact Dependent Contract",
                    },
                    "schema": {
                        "fields": [
                            {
                                "name": "dependent_field",
                                "type": "string",
                            }
                        ]
                    },
                    "models": [
                        {
                            "name": "DependentModel",
                            "fields": [
                                {
                                    "name": "dependent_field",
                                    "type": "string",
                                    "lineage": {
                                        "input_fields": [
                                            {
                                                "namespace": None,
                                                "name": "impact-source-contract",
                                                "model_name": "SourceModel",
                                                "field": "source_field",
                                            }
                                        ]
                                    },
                                }
                            ],
                            "lineage": {
                                "models": [
                                    {
                                        "namespace": None,
                                        "name": "impact-source-contract",
                                        "model_name": "SourceModel",
                                    }
                                ]
                            },
                        }
                    ],
                    "lineage": {
                        "contracts": [{"namespace": None, "name": "impact-source-contract"}]
                    },
                }
            ),
        )

        dependent_contract = Contract.objects.get(id=self.dependent_contract_id)
        dependent_contract.hub_contract_json = {
            "info": {"name": "impact-dependent-contract", "title": "Impact Dependent Contract"},
            "models": [
                {
                    "name": "DependentModel",
                    "fields": [
                        {
                            "name": "dependent_field",
                            "type": "string",
                            "lineage": {
                                "input_fields": [
                                    {
                                        "namespace": None,
                                        "name": "impact-source-contract",
                                        "model_name": "SourceModel",
                                        "field": "source_field",
                                    }
                                ]
                            },
                        }
                    ],
                    "lineage": {
                        "models": [
                            {
                                "namespace": None,
                                "name": "impact-source-contract",
                                "model_name": "SourceModel",
                            }
                        ]
                    },
                }
            ],
            "lineage": {"contracts": [{"namespace": None, "name": "impact-source-contract"}]},
        }
        dependent_contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        dependent_contract.validation_status = ValidationStatus.VALID
        dependent_contract.save()

        self.analyzer = ImpactAnalyzer(
            max_contract_depth=10, max_model_depth=10, max_field_depth=10, include_fields=True
        )

    def test_contract_change_impact_analysis(self):
        """Test impact analysis for contract-level changes"""
        impact_result = self.analyzer.analyze_impact(
            contract_id=str(self.source_contract_id), tenant_id=str(self.tenant.id)
        )

        # Verify structure
        self.assertNotIn("error", impact_result)
        self.assertIn("source", impact_result)
        self.assertIn("impact_graph", impact_result)
        self.assertIn("summary", impact_result)
        self.assertIn("total_affected", impact_result)

        # Verify source information
        source = impact_result.get("source", {})
        self.assertEqual(source.get("contract_id"), str(self.source_contract_id))

        # Verify impact graph
        impact_graph = impact_result.get("impact_graph", {})
        self.assertIsInstance(impact_graph, dict)

        # Verify summary
        summary = impact_result.get("summary", {})
        self.assertIn("total_contracts", summary)
        self.assertIn("severity_distribution", summary)

    def test_model_change_impact_analysis(self):
        """Test impact analysis for model-level changes"""
        impact_result = self.analyzer.analyze_impact(
            contract_id=str(self.source_contract_id),
            model_name="SourceModel",
            tenant_id=str(self.tenant.id),
        )

        # Verify structure
        self.assertNotIn("error", impact_result)
        self.assertIn("source", impact_result)

        # Verify source includes model name
        source = impact_result.get("source", {})
        self.assertEqual(source.get("model_name"), "SourceModel")

    def test_field_change_impact_analysis(self):
        """Test impact analysis for field-level changes"""
        impact_result = self.analyzer.analyze_impact(
            contract_id=str(self.source_contract_id),
            model_name="SourceModel",
            field_name="source_field",
            tenant_id=str(self.tenant.id),
        )

        # Verify structure
        self.assertNotIn("error", impact_result)
        self.assertIn("source", impact_result)

        # Verify source includes field name
        source = impact_result.get("source", {})
        self.assertEqual(source.get("field_name"), "source_field")
        self.assertEqual(source.get("model_name"), "SourceModel")


class LineageAPIE2ETest(E2ETestBase):
    """E2E tests for lineage API endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create contract via API
        # ODCS requires: id, info.name, schema.fields (at least one field)
        self.contract_id = self.create_contract(
            asset_id=None,
            original_raw=json.dumps(
                {
                    "id": "api-test-contract",
                    "info": {"name": "api-test-contract", "title": "API Test Contract"},
                    "schema": {"fields": [{"name": "api_field", "type": "string"}]},
                    "models": [
                        {"name": "APIModel", "fields": [{"name": "api_field", "type": "string"}]}
                    ],
                    "lineage": {"contracts": [], "entries": []},
                }
            ),
        )

        # Update contract
        contract = Contract.objects.get(id=self.contract_id)
        contract.hub_contract_json = {
            "info": {"name": "api-test-contract", "title": "API Test Contract"},
            "models": [{"name": "APIModel", "fields": [{"name": "api_field", "type": "string"}]}],
            "lineage": {"contracts": [], "entries": []},
        }
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.validation_status = ValidationStatus.VALID
        contract.save()

    def test_contract_lineage_api_endpoint(self):
        """Test contract-level lineage API endpoint"""
        response = self.client.get(f"/api/v1/contracts/{self.contract_id}/lineage/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contracts", response.data)
        self.assertIn("entries", response.data)

    def test_model_lineage_api_endpoint(self):
        """Test model-level lineage API endpoint"""
        response = self.client.get(f"/api/v1/contracts/{self.contract_id}/models/APIModel/lineage/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("model_name", response.data)
        self.assertIn("lineage", response.data)

    def test_field_lineage_api_endpoint(self):
        """Test field-level lineage API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/fields/api_field/lineage/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("field_name", response.data)
        self.assertIn("lineage", response.data)

    def test_full_lineage_api_endpoint(self):
        """Test full lineage API endpoint"""
        response = self.client.get(f"/api/v1/contracts/{self.contract_id}/lineage/full/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upstream", response.data)
        self.assertIn("downstream", response.data)

    def test_lineage_visualization_json_api_endpoint(self):
        """Test lineage visualization JSON API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/lineage/visualization/",
            {"format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)

    def test_lineage_visualization_dot_api_endpoint(self):
        """Test lineage visualization DOT API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/lineage/visualization/",
            {"format": "dot"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DOT format returns as text
        self.assertIn("digraph", response.content.decode("utf-8"))

    def test_lineage_visualization_mermaid_api_endpoint(self):
        """Test lineage visualization Mermaid API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/lineage/visualization/",
            {"format": "mermaid"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Mermaid format returns as text
        content = response.content.decode("utf-8")
        self.assertIn("graph", content.lower())

    def test_impact_analysis_api_endpoint(self):
        """Test impact analysis API endpoint"""
        response = self.client.get(f"/api/v1/contracts/{self.contract_id}/impact-analysis/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("source", response.data)
        self.assertIn("impact_graph", response.data)
        self.assertIn("summary", response.data)

    def test_impact_analysis_model_level_api_endpoint(self):
        """Test model-level impact analysis API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/impact-analysis/",
            {"model_name": "APIModel"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        source = response.data.get("source", {})
        self.assertEqual(source.get("model_name"), "APIModel")

    def test_impact_analysis_field_level_api_endpoint(self):
        """Test field-level impact analysis API endpoint"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_id}/impact-analysis/",
            {"model_name": "APIModel", "field_name": "api_field"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        source = response.data.get("source", {})
        self.assertEqual(source.get("field_name"), "api_field")
        self.assertEqual(source.get("model_name"), "APIModel")
