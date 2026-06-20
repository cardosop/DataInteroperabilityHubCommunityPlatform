"""
Phase 83.4 — purge_orphan_prefect_deployments management command tests.
"""

import uuid
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
class PurgeOrphanDeploymentsCommandTest(TestCase):
    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.get_or_create(
            name="purge-test",
            defaults={"slug": "purge-test"},
        )[0]

    def _create_deleted_ingestion(self, tenant):
        from django.db import connection

        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestion,
        )

        si_id = uuid.uuid4()
        now = timezone.now()
        with connection.cursor() as c:
            c.execute(
                """INSERT INTO scheduled_ingestions
                   (id, tenant_id, name, source_type, source_config,
                    schedule_type, schedule_config, status,
                    consecutive_failure_count, created_at, updated_at,
                    auto_create_asset, auto_activate,
                    prefect_work_pool_name, deployment_sync_status,
                    prefect_deployment_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [
                    str(si_id),
                    str(tenant.id),
                    f"del-{si_id.hex[:8]}",
                    "HTTP",
                    "{}",
                    "DAILY",
                    '{"cron":"0 0 * * *","timezone":"UTC"}',
                    "DELETED",
                    0,
                    now,
                    now,
                    False,
                    False,
                    "default",
                    "PENDING",
                    f"prefect-dep-{si_id.hex[:8]}",
                ],
            )
        return ScheduledIngestion.objects.get(pk=si_id)

    @patch(
        "hub.apps.jobs.management.commands"
        ".purge_orphan_prefect_deployments.delete_prefect_deployment",
        return_value=True,
    )
    def test_deleted_record_purged(self, mock_del):
        tenant = self._create_tenant()
        si = self._create_deleted_ingestion(tenant)
        out = StringIO()
        call_command("purge_orphan_prefect_deployments", stdout=out)
        mock_del.assert_called_once()
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        assert not ScheduledIngestion.objects.filter(pk=si.pk).exists()

    @patch(
        "hub.apps.jobs.management.commands"
        ".purge_orphan_prefect_deployments.delete_prefect_deployment",
        return_value=False,
    )
    def test_delete_failure_keeps_record(self, mock_del):
        tenant = self._create_tenant()
        si = self._create_deleted_ingestion(tenant)
        call_command("purge_orphan_prefect_deployments")
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        assert ScheduledIngestion.objects.filter(pk=si.pk).exists()

    def test_dry_run_does_not_delete(self):
        tenant = self._create_tenant()
        si = self._create_deleted_ingestion(tenant)
        out = StringIO()
        call_command("purge_orphan_prefect_deployments", "--dry-run", stdout=out)
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        assert ScheduledIngestion.objects.filter(pk=si.pk).exists()
        assert "DRY-RUN" in out.getvalue()

    def test_no_orphans_clean_exit(self):
        out = StringIO()
        call_command("purge_orphan_prefect_deployments", stdout=out)
        self.assertIn("Purged 0 orphan deployment(s)", out.getvalue())
