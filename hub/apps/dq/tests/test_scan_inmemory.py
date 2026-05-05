"""
Phase 250.1.A.2 — ``DQService.scan_inmemory`` tests (TDD).

The fail-closed-at-intake workflow re-sequence (250.1.A.3) needs a DQ
check that runs against the file payload BEFORE persisting the
``Asset``. Same shape as :meth:`ComplianceService.scan_inmemory`:

* Persists a ``DQRun`` keyed on ``file`` only — no ``asset`` /
  ``dataset`` FK — so the row is durable for audit / replay even if
  the workflow later refuses to persist an Asset.
* Calls the dq-service synchronously (the workflow needs the result
  in-band).
* Returns the populated ``DQRun`` so the caller can inspect
  ``overall_status`` / ``quality_score``.

External boundaries (S3, dq-service HTTP) are mocked at their
boundaries; everything else (ORM, business rules, persistence) is
real.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.services import DQService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant_and_user():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    file_uuid = uuid.uuid4()
    file_obj = File.objects.create(
        tenant=tenant,
        name="data.csv",
        content_type="text/csv",
        size=42,
        storage_path=f"{tenant.id}/{file_uuid}/data.csv",
        status=FileStatus.ACTIVE,
        created_by=user,
    )
    return tenant, user, file_obj


def _patched_storage_returns(content: bytes):
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=content,
    )


def _patched_client_returns(payload: dict):
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value=payload,
    )


class ScanInMemoryHappyPathTest(TestCase):

    def test_returns_dq_run_persisted_with_pass(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        pass_payload = {
            "overall_status": "PASS",
            "quality_score": 95.5,
            "checks": [{"name": "row_count_ge_1", "status": "PASS"}],
            "engine_type": "GREAT_EXPECTATIONS",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {"total_rows": 10, "total_columns": 2},
        }
        with _patched_storage_returns(b"a,b\n1,2\n"), _patched_client_returns(pass_payload):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        assert isinstance(run, DQRun)
        run.refresh_from_db()
        assert run.tenant_id == tenant.id
        assert run.file_id == file_obj.id
        # Critical fail-closed contract: NO asset / dataset row should
        # be touched / created by an in-memory scan.
        assert run.asset_id is None
        assert run.dataset_id is None
        assert run.status == DQRunStatus.SUCCEEDED
        assert run.overall_status == "PASS"
        assert run.quality_score == pytest.approx(95.5)
        assert run.profile_key == "intake_basic_gx"
        assert run.engine == DQEngine.GREAT_EXPECTATIONS

    def test_no_asset_or_dataset_rows_created_for_inmemory_scan(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset

        before_assets = Asset.objects.filter(tenant=tenant).count()
        before_datasets = Dataset.objects.filter(tenant=tenant).count()

        with _patched_storage_returns(b"a,b\n1,2\n"), _patched_client_returns(
            {
                "overall_status": "PASS",
                "quality_score": 100,
                "checks": [],
                "metadata": {},
            }
        ):
            DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        assert Asset.objects.filter(tenant=tenant).count() == before_assets
        assert Dataset.objects.filter(tenant=tenant).count() == before_datasets


class ScanInMemoryFailClosedTest(TestCase):

    def test_unknown_overall_status_persists_and_marks_failed_when_circuit_open(self):
        """The dq-service fallback returns ``UNKNOWN`` — that must persist as-is.

        ``UNKNOWN`` from dq-service is the canonical "service unavailable"
        signal (the client's fallback dict). The workflow gate then
        treats it as a fail-closed condition.
        """
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), _patched_client_returns(
            {
                "overall_status": "UNKNOWN",
                "quality_score": 0.0,
                "checks": [],
                "engine_type": "UNKNOWN",
                "metadata": {"error": "DQ service unavailable"},
            }
        ):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        run.refresh_from_db()
        assert run.overall_status == "UNKNOWN"
        assert run.status == DQRunStatus.SUCCEEDED  # the call itself didn't crash
        assert run.quality_score == 0.0

    def test_explicit_fail_response_is_persisted(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), _patched_client_returns(
            {
                "overall_status": "FAIL",
                "quality_score": 12.0,
                "checks": [{"name": "no_nulls", "status": "FAIL"}],
                "metadata": {},
            }
        ):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        run.refresh_from_db()
        assert run.overall_status == "FAIL"
        assert run.quality_score == pytest.approx(12.0)


class ScanInMemoryServiceFailureTest(TestCase):

    def test_service_exception_marks_run_failed(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), patch(
            "hub.apps.dq.service_client.DQServiceClient.run_dq",
            side_effect=RuntimeError("dq microservice unreachable"),
        ):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        run.refresh_from_db()
        assert run.status == DQRunStatus.FAILED
        # ``overall_status`` falls back to ``UNKNOWN`` so workflow
        # gate code can use a single fail-closed predicate (``status
        # not in PASS|WARN``).
        assert run.overall_status == "UNKNOWN"
        details = run.details_json or {}
        assert details.get("error") is not None


class ScanInMemoryArgumentValidationTest(TestCase):

    def test_unknown_file_id_raises_validation_error(self):
        tenant, _user, _file_obj = _seed_tenant_and_user()
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError):
            DQService.scan_inmemory(
                file_id=str(uuid.uuid4()),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

    def test_file_belonging_to_different_tenant_is_rejected(self):
        tenant_a, _user_a, file_a = _seed_tenant_and_user()
        tenant_b, _user_b, _file_b = _seed_tenant_and_user()
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError):
            DQService.scan_inmemory(
                file_id=str(file_a.id),
                tenant=tenant_b,
                profile_key="intake_basic_gx",
            )


class ScanInMemoryProfileKeyResolutionTest(TestCase):
    """Profile key resolution must mirror :meth:`create_dq_run`."""

    def test_explicit_profile_key_routes_to_great_expectations(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), _patched_client_returns(
            {"overall_status": "PASS", "quality_score": 100, "metadata": {}}
        ):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
            )

        run.refresh_from_db()
        assert run.engine == DQEngine.GREAT_EXPECTATIONS

    def test_soda_profile_key_routes_to_soda(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), _patched_client_returns(
            {"overall_status": "PASS", "quality_score": 100, "metadata": {}}
        ):
            run = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_soda",
            )

        run.refresh_from_db()
        assert run.engine == DQEngine.SODA
