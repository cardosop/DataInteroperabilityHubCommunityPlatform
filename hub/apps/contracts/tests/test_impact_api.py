"""
Integration tests for Impact Analysis API

Tests for impact analysis API endpoints.
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.models import Contract
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class ImpactAPITest(ContractsAPITestBase):
    """Test Impact Analysis API"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract", "info": {"name": "Test Contract"}}',
            hub_contract_json={"info": {"name": "Test Contract", "title": "Test Contract"}},
            created_by=self.user,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_impact_analysis_endpoint(self):
        """Test impact analysis endpoint"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)
        self.assertIn("summary", response.data)

    def test_impact_analysis_with_depth(self):
        """Test impact analysis with depth parameter"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"depth": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_impact_analysis_csv_format(self):
        """Test impact analysis CSV format"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "csv"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "text/csv")

    def test_impact_analysis_dot_format(self):
        """Test impact analysis DOT format"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "dot"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "text/plain")
        self.assertIn("digraph ImpactAnalysis", response.content.decode())

    def test_impact_analysis_mermaid_format(self):
        """Test impact analysis Mermaid format"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "mermaid"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "text/plain")
        self.assertIn("graph LR", response.content.decode())

    def test_impact_analysis_paths_format(self):
        """Test impact analysis paths format"""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "paths"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("paths", response.data)
        self.assertIn("total_paths", response.data)

    # Edge cases and error handling tests
    def test_impact_analysis_contract_not_found(self):
        """Test impact analysis endpoint with non-existent contract."""
        import uuid

        fake_id = str(uuid.uuid4())
        url = reverse("contract-get-impact-analysis", kwargs={"id": fake_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_impact_analysis_unauthenticated(self):
        """Test impact analysis endpoint without authentication."""
        client = APIClient()  # Not authenticated
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = client.get(url)

        # Should require authentication
        self.assertIn(
            response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_impact_analysis_cross_tenant_isolation(self):
        """Test that impact analysis respects tenant isolation."""
        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-api-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Authenticate as other user
        client = APIClient()
        client.force_authenticate(user=other_user)

        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = client.get(url)

        # Should not access contract from other tenant
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_impact_analysis_with_invalid_depth(self):
        """Test impact analysis with invalid depth parameter."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})

        # Negative depth must be rejected with 400
        response = self.client.get(url, {"depth": -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Very large depth is a valid positive integer — must be accepted
        response = self.client.get(url, {"depth": 10000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Non-numeric depth must be rejected with 400 (fixed in prior round)
        response = self.client.get(url, {"depth": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_impact_analysis_with_invalid_format(self):
        """Test impact analysis with invalid format parameter."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "invalid-format"})

        # Unknown output format must be rejected with 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_impact_analysis_with_missing_contract_hub_json(self):
        """Test impact analysis with contract missing hub_contract_json."""
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract"}',
            # hub_contract_json is None
            created_by=self.user,
        )

        url = reverse("contract-get-impact-analysis", kwargs={"id": contract_no_hub.id})
        response = self.client.get(url)

        # ImpactAnalyzer.analyze_impact handles None hub_contract_json gracefully
        # and returns a valid result without an "error" key, so the view returns 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_impact_analysis_json_format_structure(self):
        """Test that JSON format returns proper structure."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "json"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)
        self.assertIn("summary", response.data)

        # Verify structure
        self.assertIsInstance(response.data["nodes"], list)
        self.assertIsInstance(response.data["links"], list)
        self.assertIsInstance(response.data["summary"], dict)

    def test_impact_analysis_csv_format_content(self):
        """Test that CSV format returns valid CSV content."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "csv"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["content-type"], "text/csv")

        # Verify CSV content
        content = response.content.decode()
        self.assertIn("Resource Type", content)
        self.assertIn("Contract ID", content)
        # Should have at least header row
        lines = content.split("\n")
        self.assertGreater(len(lines), 0)

    def test_impact_analysis_dot_format_content(self):
        """Test that DOT format returns valid DOT content."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "dot"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn("digraph", content.lower())
        self.assertIn("{", content)
        self.assertIn("}", content)

    def test_impact_analysis_mermaid_format_content(self):
        """Test that Mermaid format returns valid Mermaid content."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "mermaid"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn("graph", content.lower())
        # Should have valid Mermaid syntax

    def test_impact_analysis_paths_format_structure(self):
        """Test that paths format returns proper structure."""
        url = reverse("contract-get-impact-analysis", kwargs={"id": self.contract.id})
        response = self.client.get(url, {"output": "paths"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("paths", response.data)
        self.assertIn("total_paths", response.data)

        # Verify structure
        self.assertIsInstance(response.data["paths"], list)
        self.assertIsInstance(response.data["total_paths"], int)

    def test_impact_analysis_with_empty_lineage(self):
        """Test impact analysis with contract that has no lineage."""
        contract_no_lineage = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "v1", "kind": "DataContract"}',
            hub_contract_json={
                "info": {"name": "No Lineage Contract"},
                # No lineage field
            },
            created_by=self.user,
        )

        url = reverse("contract-get-impact-analysis", kwargs={"id": contract_no_lineage.id})
        response = self.client.get(url)

        # Should handle gracefully
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("links", response.data)
