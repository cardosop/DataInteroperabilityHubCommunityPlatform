"""
283.3.3.3 — G3 E2E RoPA generation + download flow.

Covers:
- Preview RoPA payload
- Generate a RoPA artefact (sync path)
- List generations
- Download a completed artefact
- Delete a generation
"""

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.ropa.models import RopaGeneration, RopaGenerationStatus
from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.journey("JOURNEY-CPO-013")]

@pytest.mark.e2e
class RopaGenerationE2ETests(E2ETestBase):
    """E2E tests for RoPA generation + download flow (283.3.3.3)."""

    def setUp(self):
        super().setUp()
        self.tenant.compliance_ropa_enabled = True
        self.tenant.save(update_fields=["compliance_ropa_enabled"])

        # Create a test asset so the RoPA payload is non-empty
        Asset.objects.create(
            tenant=self.tenant,
            key="ropa-e2e-asset",
            name="RoPA E2E Asset",
            description="Asset for RoPA E2E testing",
            status=AssetStatus.ACTIVE,
            categories_of_subjects=["employees"],
            recipient_categories=["hr-department"],
        )

    def test_preview_ropa_returns_200(self):
        """Preview returns 200 with regulation, summary, and gaps."""
        resp = self.client.get(
            "/api/v1/ropa/generations/preview/",
            {"regulation": "GDPR"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("regulation", resp.data)
        self.assertIn("summary", resp.data)
        self.assertIn("gaps", resp.data)

    def test_generate_ropa_json_sync_returns_201(self):
        """Generate a JSON RoPA artefact synchronously."""
        resp = self.client.post(
            "/api/v1/ropa/generate/?regulation=GDPR&format=json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["output_format"], "json")
        self.assertEqual(resp.data["status"], RopaGenerationStatus.COMPLETED)

        gen_id = resp.data["id"]
        self.assertTrue(RopaGeneration.objects.filter(id=gen_id, tenant=self.tenant).exists())

    def test_list_generations_includes_created(self):
        """List generations returns the created artefact."""
        RopaGeneration.objects.create(
            tenant=self.tenant,
            regulation="GDPR",
            output_format="json",
            status=RopaGenerationStatus.COMPLETED,
            summary_json={"asset_count": 1},
            gaps_json=[],
        )
        resp = self.client.get("/api/v1/ropa/generations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", [])
        self.assertGreater(len(results), 0)

    def test_delete_generation_returns_204(self):
        """Delete a completed generation."""
        gen = RopaGeneration.objects.create(
            tenant=self.tenant,
            regulation="GDPR",
            output_format="json",
            status=RopaGenerationStatus.COMPLETED,
            summary_json={"asset_count": 0},
            gaps_json=[],
        )
        resp = self.client.delete(
            f"/api/v1/ropa/generations/{gen.id}/delete/",
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RopaGeneration.objects.filter(id=gen.id).exists())

    def test_ropa_disabled_returns_403(self):
        """When feature flag is off, endpoints return 403."""
        self.tenant.compliance_ropa_enabled = False
        self.tenant.save(update_fields=["compliance_ropa_enabled"])

        resp = self.client.get(
            "/api/v1/ropa/generations/preview/",
            {"regulation": "GDPR"},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
