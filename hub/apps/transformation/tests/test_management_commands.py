"""
Unit tests for transformation management commands.

Tests migrate_legacy_transformation_pipelines command.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.transformation.models import PipelineStatus, TransformationPipeline

pytestmark = pytest.mark.django_db(transaction=True)


class MigrateLegacyPipelinesTest(TestCase):
    """Test migrate_legacy_transformation_pipelines command"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="MigrateTest",
            slug="migrate-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.out = StringIO()
        self.err = StringIO()

    def _create_legacy_pipeline(self, name="legacy_pipe", mode="SQL"):
        """Helper to create a legacy pipeline with the legacy mode flag."""
        return TransformationPipeline.objects.create(
            name=name,
            tenant=self.tenant,
            status=PipelineStatus.ACTIVE,
            pipeline_definition={"mode": mode, "query": "SELECT 1"},
            metadata={},
        )

    def _create_dbt_pipeline(self, name="dbt_pipe"):
        """Helper to create a modern dbt pipeline."""
        return TransformationPipeline.objects.create(
            name=name,
            tenant=self.tenant,
            status=PipelineStatus.ACTIVE,
            pipeline_definition={"engine": "dbt", "project": "analytics"},
            metadata={},
        )

    # ── Dry run ──────────────────────────────────────────────────────

    def test_dry_run_finds_legacy_pipelines(self):
        """Dry run lists legacy pipelines without modifying them"""
        p1 = self._create_legacy_pipeline("old_sql")
        self._create_dbt_pipeline("modern_dbt")

        call_command(
            "migrate_legacy_transformation_pipelines", "--dry-run", stdout=self.out, stderr=self.err
        )

        output = self.out.getvalue()
        self.assertIn("Found 1 legacy pipeline", output)
        self.assertIn("old_sql", output)
        self.assertIn("DRY RUN", output)
        # Verify pipeline was NOT modified
        p1.refresh_from_db()
        self.assertEqual(p1.pipeline_definition.get("mode"), "SQL")

    def test_dry_run_no_legacy(self):
        """Dry run reports no legacy pipelines when all are modern"""
        self._create_dbt_pipeline("modern")

        call_command(
            "migrate_legacy_transformation_pipelines", "--dry-run", stdout=self.out, stderr=self.err
        )

        self.assertIn("No legacy pipelines found", self.out.getvalue())

    # ── Actual migration ─────────────────────────────────────────────

    def test_migrate_converts_legacy_to_dbt(self):
        """Migration converts SQL mode pipeline to dbt engine"""
        p1 = self._create_legacy_pipeline("convert_me", mode="SQL")

        call_command("migrate_legacy_transformation_pipelines", stdout=self.out, stderr=self.err)

        p1.refresh_from_db()
        self.assertEqual(p1.pipeline_definition.get("engine"), "dbt")
        self.assertNotIn("mode", p1.pipeline_definition)
        self.assertIn("migrated_from", p1.pipeline_definition)

    def test_migrate_converts_visual_mode(self):
        """Migration handles VISUAL mode pipelines"""
        p1 = self._create_legacy_pipeline("visual_pipe", mode="VISUAL")

        call_command("migrate_legacy_transformation_pipelines", stdout=self.out, stderr=self.err)

        p1.refresh_from_db()
        self.assertEqual(p1.pipeline_definition.get("engine"), "dbt")

    def test_migrate_single_pipeline(self):
        """--pipeline-id migrates only the specified pipeline"""
        self._create_legacy_pipeline("target")
        p2 = self._create_legacy_pipeline("other")

        call_command(
            "migrate_legacy_transformation_pipelines",
            "--pipeline-id",
            str(p2.id),
            stdout=self.out,
            stderr=self.err,
        )

        # Only p2 should be migrated
        p2.refresh_from_db()
        self.assertEqual(p2.pipeline_definition.get("engine"), "dbt")

    def test_migrate_skips_archived(self):
        """Migration skips ARCHIVED pipelines"""
        p1 = self._create_legacy_pipeline("archived_legacy")
        p1.status = PipelineStatus.ARCHIVED
        p1.save()

        call_command("migrate_legacy_transformation_pipelines", stdout=self.out, stderr=self.err)

        self.assertIn("No legacy pipelines found", self.out.getvalue())
