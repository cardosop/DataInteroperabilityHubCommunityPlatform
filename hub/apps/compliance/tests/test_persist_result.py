"""
Tests for ComplianceService._persist_result() static method.

Validates that result_data from the compliance microservice is correctly
mapped onto ComplianceRun fields, including fail-closed defaults,
American-to-British spelling normalisation, metering population, and
asset compliance_status propagation.
"""
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus as AssetComplianceStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.jobs.models import Job, JobType
from hub.apps.jobs.utils import create_job, get_job_timeout
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class PersistResultTest(TestCase):
    """Tests for ComplianceService._persist_result()"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def _create_job(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        defaults.update(overrides)
        return create_job(**defaults)

    def _create_run(self, **overrides):
        job = self._create_job()
        defaults = dict(
            tenant=self.tenant,
            asset=self.asset,
            job=job,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    def _full_result_data(self, **overrides):
        data = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": [{"category": "PII_DIRECT_EMAIL", "count": 5}],
            "column_findings": [
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                }
            ],
            "applicable_regulations": ["GDPR"],
            "regulation_mapping": {"GDPR": {"articles": ["Art. 6"]}},
            "schema_version": "2.0",
            "risk_score": 15.0,
            "metadata": {"total_rows": 100, "total_columns": 5},
        }
        data.update(overrides)
        return data

    # ----------------------------------------------------------------
    # 1. Full field mapping
    # ----------------------------------------------------------------

    def test_persist_maps_all_fields(self):
        """Full result_data populates all key fields on the ComplianceRun."""
        run = self._create_run()
        ComplianceService._persist_result(run, self._full_result_data())
        run.refresh_from_db()

        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(run.overall_status, "PASS")
        self.assertEqual(run.risk_level, "LOW")
        self.assertTrue(run.allowed_to_store)
        self.assertEqual(run.regulations, ["GDPR"])
        self.assertIsInstance(run.detected_categories_json, list)
        self.assertEqual(len(run.detected_categories_json), 1)
        self.assertIsInstance(run.column_findings_json, list)
        self.assertEqual(len(run.column_findings_json), 1)

    # ----------------------------------------------------------------
    # 2. Fail-closed: UNKNOWN overall_status
    # ----------------------------------------------------------------

    def test_fail_closed_unknown_status(self):
        """UNKNOWN overall_status forces allowed_to_store=False (fail-closed)."""
        run = self._create_run()
        result = self._full_result_data(
            overall_status="UNKNOWN", allowed_to_store=True
        )
        ComplianceService._persist_result(run, result)
        run.refresh_from_db()

        self.assertFalse(run.allowed_to_store)

    # ----------------------------------------------------------------
    # 3. Fail-closed: missing allowed_to_store key
    # ----------------------------------------------------------------

    def test_fail_closed_missing_allowed(self):
        """Missing allowed_to_store key defaults to False (fail-closed)."""
        run = self._create_run()
        result = self._full_result_data()
        del result["allowed_to_store"]
        ComplianceService._persist_result(run, result)
        run.refresh_from_db()

        self.assertFalse(run.allowed_to_store)

    # ----------------------------------------------------------------
    # 4. American → British spelling normalisation
    # ----------------------------------------------------------------

    def test_localisation_spelling(self):
        """localization_alert (American) maps to localisation_alert (British)."""
        run = self._create_run()
        result = self._full_result_data(
            localization_alert={"applicable": True}
        )
        ComplianceService._persist_result(run, result)
        run.refresh_from_db()

        self.assertEqual(run.localisation_alert, {"applicable": True})

    # ----------------------------------------------------------------
    # 5. schema_version stored in regulation_mapping_json
    # ----------------------------------------------------------------

    def test_schema_version_in_reg_mapping(self):
        """schema_version from result_data lands in regulation_mapping_json."""
        run = self._create_run()
        result = self._full_result_data(schema_version="2.0")
        ComplianceService._persist_result(run, result)
        run.refresh_from_db()

        self.assertEqual(
            run.regulation_mapping_json["schema_version"], "2.0"
        )

    # ----------------------------------------------------------------
    # 6. Metering block populated correctly
    # ----------------------------------------------------------------

    def test_metering_populated(self):
        """Metering dict has all expected keys after persist."""
        run = self._create_run()
        ComplianceService._persist_result(run, self._full_result_data())
        run.refresh_from_db()

        metering = run.regulation_mapping_json.get("metering")
        self.assertIsNotNone(metering)
        expected_keys = {
            "operation_type",
            "rows_scanned",
            "columns_scanned",
            "execution_time_seconds",
            "scan_mode",
            "risk_score",
            "risk_level",
            "allowed_to_store",
            "regulations_checked",
        }
        self.assertTrue(
            expected_keys.issubset(set(metering.keys())),
            f"Missing metering keys: {expected_keys - set(metering.keys())}",
        )
        self.assertEqual(metering["operation_type"], "COMPLIANCE_RUN")
        self.assertEqual(metering["rows_scanned"], 100)
        self.assertEqual(metering["columns_scanned"], 5)
        self.assertEqual(metering["scan_mode"], "internal")

    # ----------------------------------------------------------------
    # Phase 213.G.7 — defensive guard: a FAILED payload must not be
    # marked SUCCEEDED. The error must be persisted with
    # error_type=EXECUTION_ERROR and the run must end FAILED.
    # ----------------------------------------------------------------

    def test_failed_payload_does_not_mark_succeeded(self):
        run = self._create_run()
        ComplianceService._persist_result(
            run,
            {
                "status": "FAILED",
                "error": "scan worker raised RuntimeError('boom')",
            },
        )
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertIsNotNone(run.regulation_mapping_json)
        self.assertEqual(
            run.regulation_mapping_json["error"],
            "scan worker raised RuntimeError('boom')",
        )
        self.assertEqual(
            run.regulation_mapping_json["error_type"], "EXECUTION_ERROR"
        )

    def test_error_payload_status_aliased_to_failed(self):
        run = self._create_run()
        ComplianceService._persist_result(
            run, {"status": "ERROR", "detail": "kaboom"}
        )
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertEqual(
            run.regulation_mapping_json["error_type"], "EXECUTION_ERROR"
        )
        self.assertEqual(run.regulation_mapping_json["error"], "kaboom")

    # ----------------------------------------------------------------
    # 7. Asset compliance_status updated on PASS
    # ----------------------------------------------------------------

    def test_asset_compliance_status_pass(self):
        """overall_status=PASS updates asset.compliance_status to PASS."""
        run = self._create_run()
        ComplianceService._persist_result(
            run, self._full_result_data(overall_status="PASS")
        )
        self.asset.refresh_from_db()

        self.assertEqual(self.asset.compliance_status, AssetComplianceStatus.PASS)

    # ----------------------------------------------------------------
    # 8. Asset compliance_status updated on FAIL
    # ----------------------------------------------------------------

    def test_asset_compliance_status_fail(self):
        """overall_status=FAIL updates asset.compliance_status to FAIL."""
        run = self._create_run()
        ComplianceService._persist_result(
            run, self._full_result_data(overall_status="FAIL")
        )
        self.asset.refresh_from_db()

        self.assertEqual(self.asset.compliance_status, AssetComplianceStatus.FAIL)
