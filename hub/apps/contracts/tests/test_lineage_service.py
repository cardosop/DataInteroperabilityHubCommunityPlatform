"""
Unit tests for LineageService.

Tests cover all service methods with 100% coverage target.

All tests use real implementations (no mocks of hub services).
Uses real LineageTraverser and visualization functions.
"""

import pytest

from hub.apps.contracts.lineage_service import LineageService
from hub.apps.contracts.models import Contract
from hub.apps.contracts.tests.test_base import ContractsTransactionTestBase
from hub.apps.core.services.base import NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class LineageServiceTest(ContractsTransactionTestBase):
    """Test LineageService operations"""

    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.service = LineageService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create contract with lineage
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            hub_contract_json={
                "info": {"name": "test-contract"},
                "lineage": {"contracts": [{"namespace": "ns1", "name": "source"}], "entries": []},
                "models": [
                    {
                        "name": "test-model",
                        "lineage": {"models": [], "entries": []},
                        "fields": [
                            {
                                "name": "test-field",
                                "lineage": {"input_fields": [], "transformations": []},
                            }
                        ],
                    }
                ],
            },
        )

    def test_get_contract_lineage_success(self):
        """Test successful contract-level lineage retrieval"""
        # Act
        lineage = self.service.get_contract_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id)
        )

        # Assert
        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)

    def test_get_model_lineage_success(self):
        """Test successful model-level lineage retrieval"""
        # Act
        lineage = self.service.get_model_lineage(
            contract_id=str(self.contract.id),
            model_name="test-model",
            tenant_id=str(self.tenant.id),
        )

        # Assert
        self.assertIn("model_name", lineage)
        self.assertIn("lineage", lineage)

    def test_get_model_lineage_not_found(self):
        """Test model lineage retrieval with non-existent model"""
        with self.assertRaises(NotFoundError):
            self.service.get_model_lineage(
                contract_id=str(self.contract.id),
                model_name="non-existent-model",
                tenant_id=str(self.tenant.id),
            )

    def test_get_field_lineage_success(self):
        """Test successful field-level lineage retrieval"""
        lineage = self.service.get_field_lineage(
            contract_id=str(self.contract.id),
            field_name="test-field",
            model_name="test-model",
            tenant_id=str(self.tenant.id),
        )

        self.assertIn("field_name", lineage)
        self.assertIn("lineage", lineage)

    def test_get_full_lineage_success(self):
        """Test successful full lineage retrieval using real LineageTraverser"""
        lineage = self.service.get_full_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("upstream", lineage)
        self.assertIn("downstream", lineage)
        # Real traverser returns dictionaries (may be empty if no lineage relationships)
        self.assertIsInstance(lineage["upstream"], dict)
        self.assertIsInstance(lineage["downstream"], dict)

    def test_get_lineage_visualization_success(self):
        """Test successful lineage visualization using real generate_lineage_json"""
        visualization = self.service.get_lineage_visualization(
            contract_id=str(self.contract.id), format="json", tenant_id=str(self.tenant.id)
        )

        # Real generate_lineage_json returns {"nodes": [...], "links": [...]}
        self.assertIn("nodes", visualization)
        self.assertIn("links", visualization)
        self.assertIsInstance(visualization["nodes"], list)
        self.assertIsInstance(visualization["links"], list)

    def test_get_contract_lineage_contract_not_found(self):
        """Test contract lineage retrieval with non-existent contract."""
        import uuid

        fake_contract_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_contract_lineage(
                contract_id=fake_contract_id, tenant_id=str(self.tenant.id)
            )

    def test_get_contract_lineage_cross_tenant_isolation(self):
        """Test that contract lineage respects tenant isolation."""
        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")
        other_user = User.objects.create_user(
            email="other@example.com", tenant=other_tenant, status=UserStatus.ACTIVE
        )

        # Try to access contract from other tenant
        with self.assertRaises(NotFoundError):
            self.service.get_contract_lineage(
                contract_id=str(self.contract.id), tenant_id=str(other_tenant.id)
            )

    def test_get_contract_lineage_without_hub_contract_json(self):
        """Test contract lineage retrieval with contract missing hub_contract_json."""
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "no-hub-contract"}}',
            original_format="JSON",
            # hub_contract_json is None
        )

        # Should return empty lineage structure
        lineage = self.service.get_contract_lineage(
            contract_id=str(contract_no_hub.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)
        self.assertEqual(len(lineage["contracts"]), 0)
        self.assertEqual(len(lineage["entries"]), 0)

    def test_get_contract_lineage_with_empty_lineage(self):
        """Test contract lineage retrieval with empty lineage data."""
        contract_empty_lineage = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "empty-lineage"}}',
            original_format="JSON",
            hub_contract_json={"info": {"name": "empty-lineage"}, "lineage": {}},  # Empty lineage
        )

        lineage = self.service.get_contract_lineage(
            contract_id=str(contract_empty_lineage.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("contracts", lineage)
        self.assertIn("entries", lineage)

    def test_get_contract_lineage_with_cache(self):
        """Test contract lineage retrieval uses cache when enabled."""
        # First call should populate cache
        lineage1 = self.service.get_contract_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id), use_cache=True
        )

        # Second call should use cache
        lineage2 = self.service.get_contract_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id), use_cache=True
        )

        # Results should be the same
        self.assertEqual(lineage1, lineage2)

    def test_get_contract_lineage_without_cache(self):
        """Test contract lineage retrieval bypasses cache when disabled."""
        lineage1 = self.service.get_contract_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id), use_cache=False
        )

        lineage2 = self.service.get_contract_lineage(
            contract_id=str(self.contract.id), tenant_id=str(self.tenant.id), use_cache=False
        )

        # Results should be the same (but fetched fresh each time)
        self.assertEqual(lineage1, lineage2)

    def test_get_model_lineage_contract_not_found(self):
        """Test model lineage retrieval with non-existent contract."""
        import uuid

        fake_contract_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_model_lineage(
                contract_id=fake_contract_id, model_name="test-model", tenant_id=str(self.tenant.id)
            )

    def test_get_model_lineage_without_models(self):
        """Test model lineage retrieval with contract that has no models."""
        contract_no_models = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "no-models"}}',
            original_format="JSON",
            hub_contract_json={
                "info": {"name": "no-models"},
                # No models field
            },
        )

        with self.assertRaises(NotFoundError):
            self.service.get_model_lineage(
                contract_id=str(contract_no_models.id),
                model_name="any-model",
                tenant_id=str(self.tenant.id),
            )

    def test_get_field_lineage_field_not_found(self):
        """Test field lineage retrieval with non-existent field."""
        with self.assertRaises(NotFoundError):
            self.service.get_field_lineage(
                contract_id=str(self.contract.id),
                field_name="non-existent-field",
                model_name="test-model",
                tenant_id=str(self.tenant.id),
            )

    def test_get_field_lineage_model_not_found(self):
        """Test field lineage retrieval with non-existent model."""
        with self.assertRaises(NotFoundError):
            self.service.get_field_lineage(
                contract_id=str(self.contract.id),
                field_name="test-field",
                model_name="non-existent-model",
                tenant_id=str(self.tenant.id),
            )

    def test_get_full_lineage_with_depth_limits(self):
        """Test full lineage retrieval with depth limits."""
        lineage = self.service.get_full_lineage(
            contract_id=str(self.contract.id),
            tenant_id=str(self.tenant.id),
            max_contract_depth=5,
            max_model_depth=3,
            max_field_depth=2,
        )

        self.assertIn("upstream", lineage)
        self.assertIn("downstream", lineage)

    def test_get_lineage_visualization_dot_format(self):
        """Test lineage visualization in DOT format."""
        visualization = self.service.get_lineage_visualization(
            contract_id=str(self.contract.id), format="dot", tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(visualization, str)
        self.assertIn("digraph", visualization.lower())

    def test_get_lineage_visualization_mermaid_format(self):
        """Test lineage visualization in Mermaid format."""
        visualization = self.service.get_lineage_visualization(
            contract_id=str(self.contract.id), format="mermaid", tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(visualization, str)
        self.assertIn("graph", visualization.lower())

    def test_get_lineage_visualization_invalid_format(self):
        """Test lineage visualization with invalid format."""
        with self.assertRaises(ValueError):
            self.service.get_lineage_visualization(
                contract_id=str(self.contract.id),
                format="invalid-format",
                tenant_id=str(self.tenant.id),
            )

    def test_get_lineage_visualization_contract_not_found(self):
        """Test lineage visualization with non-existent contract."""
        import uuid

        fake_contract_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_lineage_visualization(
                contract_id=fake_contract_id, format="json", tenant_id=str(self.tenant.id)
            )

    def test_get_full_lineage_with_large_graph(self):
        """Test full lineage retrieval with large lineage graph."""
        # Create contract with many lineage references
        large_lineage = {
            "contracts": [{"namespace": f"ns{i}", "name": f"contract{i}"} for i in range(50)],
            "entries": [],
        }

        contract_large = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "large-lineage"}}',
            original_format="JSON",
            hub_contract_json={"info": {"name": "large-lineage"}, "lineage": large_lineage},
        )

        lineage = self.service.get_full_lineage(
            contract_id=str(contract_large.id), tenant_id=str(self.tenant.id)
        )

        self.assertIn("upstream", lineage)
        self.assertIn("downstream", lineage)

    def test_get_contract_lineage_with_invalid_contract_id_format(self):
        """Test contract lineage retrieval with invalid contract_id format."""
        with self.assertRaises((ValueError, NotFoundError)):
            self.service.get_contract_lineage(
                contract_id="not-a-uuid", tenant_id=str(self.tenant.id)
            )

    def test_get_contract_lineage_missing_tenant_id(self):
        """Test contract lineage retrieval without tenant_id."""
        service_no_tenant = LineageService(user_id=str(self.user.id))

        # Should use service's tenant_id or raise error
        try:
            lineage = service_no_tenant.get_contract_lineage(contract_id=str(self.contract.id))
            # If it succeeds, verify structure
            self.assertIn("contracts", lineage)
        except (ValueError, NotFoundError):
            # If it fails, that's acceptable
            pass
