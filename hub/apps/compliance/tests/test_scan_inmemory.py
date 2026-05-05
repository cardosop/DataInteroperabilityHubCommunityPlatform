"""
Phase 250.1.A.1 — ``ComplianceService.scan_inmemory`` tests (TDD).

The fail-closed-at-intake workflow re-sequence (250.1.A.3) requires a
compliance check that runs against the **file payload + tenant policy**
WITHOUT having an Asset row to attach the result to. The classic
:meth:`ComplianceService.create_compliance_run` path always wires the
new ``ComplianceRun`` to a pre-existing Asset; that's exactly the
ordering the re-sequence is undoing.

``scan_inmemory`` therefore:

1. Persists a ``ComplianceRun`` row keyed on the FILE (not an asset) so
   the result is durable for audit / replay even if the workflow
   later refuses to persist an Asset.
2. Downloads the file payload via :class:`S3StorageClient` and calls
   the compliance microservice synchronously (it cannot return the
   FAIL signal to the workflow if it returns 202).
3. Returns the populated ``ComplianceRun`` so the caller can inspect
   ``allowed_to_store`` / ``overall_status`` and decide whether to
   persist the Asset.
4. Honours the platform-wide fail-closed contract: if the service is
   unavailable / returns UNKNOWN, ``allowed_to_store=False``.

Tests in this file mock ONLY the external boundaries (S3 download,
compliance HTTP client). All ORM, business-rules, and audit logic
runs against the real implementations, in line with the project's
"no business-logic stubs" rule. The compliance HTTP client itself is
covered end-to-end by ``test_call_compliance_service.py`` /
``test_service_client.py``.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant_and_user():
    """Common fixture builder — keeps each test method self-contained."""
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
    """Patch :meth:`S3StorageClient.get_file_content` to return ``content``."""
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=content,
    )


def _patched_client_returns(payload: dict):
    """Patch :class:`ComplianceServiceClient.scan_file` to return ``payload``."""
    return patch(
        "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
        return_value=payload,
    )


class ScanInMemoryHappyPathTest(TestCase):
    """Phase 250.1.A.1 happy path: PASS result persists ComplianceRun and no Asset."""

    def test_returns_compliance_run_persisted_with_pass(self):
        tenant, _user, file_obj = _seed_tenant_and_user()

        pass_payload = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": [],
            "column_findings": [],
            "regulation_mapping": {},
            "applicable_regulations": ["GDPR"],
            "metadata": {"total_rows": 1, "total_columns": 2},
        }
        with _patched_storage_returns(b"a,b\n1,2\n"), _patched_client_returns(pass_payload):
            run = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="CONSENT",
            )

        assert isinstance(run, ComplianceRun)
        assert run.id is not None
        run.refresh_from_db()
        assert run.tenant_id == tenant.id
        assert run.file_id == file_obj.id
        # Critical fail-closed contract: NO asset row should be
        # touched / created by an in-memory scan.
        assert run.asset_id is None
        assert run.dataset_id is None
        assert run.status == ComplianceRunStatus.SUCCEEDED
        assert run.overall_status == "PASS"
        assert run.allowed_to_store is True

    def test_no_asset_rows_created_for_inmemory_scan(self):
        """The whole point of 250.1.A.1: the scan must not touch ``Asset``."""
        tenant, _user, file_obj = _seed_tenant_and_user()
        from hub.apps.assets.models import Asset

        before = Asset.objects.filter(tenant=tenant).count()
        with _patched_storage_returns(b"a,b\n1,2\n"), _patched_client_returns(
            {"overall_status": "PASS", "allowed_to_store": True, "metadata": {}}
        ):
            ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="CONSENT",
            )

        assert Asset.objects.filter(tenant=tenant).count() == before


class ScanInMemoryFailClosedTest(TestCase):
    """A FAIL or UNKNOWN response must surface ``allowed_to_store=False``."""

    def test_unknown_overall_status_marks_disallowed(self):
        tenant, _user, file_obj = _seed_tenant_and_user()

        with _patched_storage_returns(b"x"), _patched_client_returns(
            {
                "overall_status": "UNKNOWN",
                "risk_level": "UNKNOWN",
                "allowed_to_store": True,  # service lies — Hub must override
                "metadata": {},
            }
        ):
            run = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="CONSENT",
            )

        run.refresh_from_db()
        assert run.allowed_to_store is False, (
            "fail-closed: UNKNOWN must override the service's "
            "allowed_to_store hint per the platform contract"
        )

    def test_explicit_fail_response_is_persisted(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), _patched_client_returns(
            {
                "overall_status": "FAIL",
                "risk_level": "HIGH",
                "allowed_to_store": False,
                "detected_categories": ["PII_SSN"],
                "metadata": {},
            }
        ):
            run = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="CONSENT",
            )

        run.refresh_from_db()
        assert run.overall_status == "FAIL"
        assert run.allowed_to_store is False


class ScanInMemoryServiceFailureTest(TestCase):
    """A service exception must end up in a FAILED run with ``allowed_to_store=False``."""

    def test_service_exception_marks_run_failed_and_disallows_storage(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            side_effect=RuntimeError("compliance microservice unreachable"),
        ):
            run = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="CONSENT",
            )

        run.refresh_from_db()
        assert run.status == ComplianceRunStatus.FAILED
        assert run.allowed_to_store is False
        assert (run.regulation_mapping_json or {}).get("error") is not None


class ScanInMemoryArgumentValidationTest(TestCase):
    """Catch obvious bad inputs early so the workflow gets a clean error."""

    def test_unknown_file_id_raises_validation_error(self):
        tenant, _user, _file_obj = _seed_tenant_and_user()
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError):
            ComplianceService.scan_inmemory(
                file_id=str(uuid.uuid4()),  # never persisted
                tenant=tenant,
                legal_basis="CONSENT",
            )

    def test_file_belonging_to_different_tenant_is_rejected(self):
        tenant_a, _user_a, file_a = _seed_tenant_and_user()
        tenant_b, _user_b, _file_b = _seed_tenant_and_user()
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError):
            ComplianceService.scan_inmemory(
                file_id=str(file_a.id),  # file_a belongs to tenant_a
                tenant=tenant_b,         # cross-tenant access — must reject
                legal_basis="CONSENT",
            )


class ScanInMemoryRegulationsForwardingTest(TestCase):
    """``applicable_regulations`` must reach the compliance HTTP boundary."""

    def test_regulations_forwarded_to_microservice(self):
        tenant, _user, file_obj = _seed_tenant_and_user()
        with _patched_storage_returns(b"x"), patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            return_value={"overall_status": "PASS", "allowed_to_store": True, "metadata": {}},
        ) as scan_mock:
            ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="LEGITIMATE_INTEREST",
                applicable_regulations=["GDPR", "LGPD"],
            )

        assert scan_mock.called, "compliance microservice was never called"
        call_kwargs = scan_mock.call_args.kwargs
        assert call_kwargs.get("applicable_regulations") == ["GDPR", "LGPD"]
        assert call_kwargs.get("legal_basis") == "LEGITIMATE_INTEREST"
        assert call_kwargs.get("tenant_id") == str(tenant.id)
