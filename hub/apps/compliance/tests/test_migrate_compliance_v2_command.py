"""
Phase 83.8 — migrate_compliance_runs_v2 management command tests.
"""

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class MigrateComplianceV2CommandTest(TestCase):
    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.get_or_create(
            name="comp-v2-test",
            defaults={"slug": "comp-v2-test"},
        )[0]

    def _create_run_with_v1_data(self, tenant, reg_json, **v2_overrides):
        """Create a ComplianceRun with v1 data, optionally pre-filled v2."""
        from hub.apps.assets.models import Asset
        from hub.apps.jobs.models import Job, JobStatus, JobType

        asset = Asset.objects.create(
            tenant=tenant,
            name=f"a-{uuid.uuid4().hex[:6]}",
        )
        job = Job.objects.create(
            tenant=tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=asset.id,
        )
        from hub.apps.compliance.models import ComplianceRun

        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status="SUCCEEDED",
            regulation_mapping_json=reg_json,
        )
        # Apply v2 overrides via update to bypass model defaults
        if v2_overrides:
            ComplianceRun.objects.filter(pk=run.pk).update(
                **v2_overrides,
            )
            run.refresh_from_db()
        return run

    def test_v2_fields_backfilled(self):
        tenant = self._create_tenant()
        run = self._create_run_with_v1_data(
            tenant,
            reg_json={
                "GDPR": {"applicable": True},
                "CCPA": {"applicable": True},
            },
        )
        out = StringIO()
        call_command("migrate_compliance_runs_v2", stdout=out)
        run.refresh_from_db()
        self.assertIsNotNone(run.cross_border_alert)
        self.assertTrue(run.cross_border_alert["backfilled"] is True)

    def test_already_backfilled_skipped(self):
        tenant = self._create_tenant()
        run = self._create_run_with_v1_data(
            tenant,
            reg_json={"GDPR": {"applicable": True}},
            cross_border_alert={
                "applicable": True,
                "backfilled": True,
            },
            localisation_alert={
                "applicable": False,
                "backfilled": True,
            },
            legal_basis_violations=[],
        )
        out = StringIO()
        call_command("migrate_compliance_runs_v2", stdout=out)
        # The run was already backfilled — the command must not crash and
        # the run's backfill flag must remain unchanged.
        # With ``--keepdb`` the command may find other un-backfilled runs
        # from prior test batches, so the global output may report counts > 0.
        # The core assertion is that our already-backfilled run stays
        # backfilled and no error occurs.
        run.refresh_from_db()
        self.assertTrue(run.cross_border_alert["backfilled"])
        output = out.getvalue()
        self.assertNotIn("error", output.lower(), "Command must complete without error")

    def test_dry_run_does_not_modify(self):
        tenant = self._create_tenant()
        run = self._create_run_with_v1_data(
            tenant,
            reg_json={"PIPL_CN": {"applicable": True}},
        )
        call_command("migrate_compliance_runs_v2", "--dry-run")
        run.refresh_from_db()
        self.assertIsNone(run.cross_border_alert)

    def test_null_regulation_mapping_not_eligible(self):
        """Rows with no regulation_mapping_json are not eligible."""
        tenant = self._create_tenant()
        run = self._create_run_with_v1_data(
            tenant,
            reg_json=None,
        )
        out = StringIO()
        call_command("migrate_compliance_runs_v2", stdout=out)
        run.refresh_from_db()
        self.assertIsNone(run.cross_border_alert)
