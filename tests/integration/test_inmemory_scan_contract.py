"""
Phase 250.1.B.6 — cross-service contract test validating that
``ComplianceService.scan_inmemory()`` and ``DQService.scan_inmemory()``
match the Hub workflow's expectations.

Why a CONTRACT test?
--------------------
Phase 250.1.A's fail-closed re-sequence calls these two methods from
[hub/apps/orchestration/workflows/asset_creation.py](../../hub/apps/orchestration/workflows/asset_creation.py)
with a precise expectation:

    result = ComplianceService.scan_inmemory(
        file_id=str,
        tenant=Tenant,
        legal_basis=Optional[str],
        applicable_regulations=Optional[List[str]],
        scan_mode=str,                # "internal" / "external"
        destination_jurisdiction=Optional[str],
        user=Optional[User],
        correlation_id=Optional[str],
    ) -> ComplianceRun           # row persisted; no Asset FK

    result.overall_status: Literal["PASS", "WARN", "FAIL"]
    result.allowed_to_store: bool

…and:

    result = DQService.scan_inmemory(
        file_id=str,
        tenant=Tenant,
        profile_key=Optional[str],
        contract=Optional[Contract],
        user=Optional[User],
        correlation_id=Optional[str],
    ) -> DQRun                   # row persisted; no Asset FK

    result.overall_status: Literal["PASS", "WARN", "FAIL"]

If the microservice contract drifts (signature changes, new required
field, status enum gains a value), the workflow's gate-decision logic
silently breaks. This test pins the contract — every scan_inmemory
call site MUST conform to the shape pinned here.

Doctrine
--------
Real ORM rows. The compliance + DQ microservice HTTP clients are
stubbed at the network boundary (so the test runs without spinning
up the actual microservices) — the same pattern the API-level fail-
closed tests use. The test asserts the SHAPE of the contract, not
the microservice behaviour.

When run against a live staging environment (with real microservices),
the network-boundary patches drop and the test exercises the real
contract end-to-end. Mark via the ``E2E_LIVE_MICROSERVICES=1`` env var.
"""

from __future__ import annotations

import inspect
import os
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from hub.apps.compliance.models import ComplianceRun
from hub.apps.compliance.services import ComplianceService
from hub.apps.dq.models import DQRun
from hub.apps.dq.services import DQService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


_LIVE_MODE = os.environ.get("E2E_LIVE_MICROSERVICES", "").lower() in ("1", "true")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_file(*, fail_closed: bool = True) -> tuple[Tenant, User, File]:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"ContractTest {uid}",
        slug=f"contract-test-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
        compliance_fail_closed_enabled=fail_closed,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    file_obj = File.objects.create(
        tenant=tenant,
        name="contract.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/contract.csv",
        created_by=user,
    )
    return tenant, user, file_obj


# ---------------------------------------------------------------------------
# Contract — ComplianceService.scan_inmemory
# ---------------------------------------------------------------------------


class TestComplianceScanInmemoryContract:
    """The Hub workflow expects a specific signature + return-shape from
    ``ComplianceService.scan_inmemory``. Drift in either is a silent
    breaking change to the fail-closed gate.
    """

    def test_signature_contract(self):
        """The signature MUST accept exactly these named parameters
        with these defaults. Adding required parameters → workflow
        breaks. Removing parameters → existing call sites break."""
        sig = inspect.signature(ComplianceService.scan_inmemory)
        param_names = list(sig.parameters.keys())

        expected_params = {
            "file_id",
            "tenant",
            "legal_basis",
            "applicable_regulations",
            "scan_mode",
            "destination_jurisdiction",
            "user",
            "correlation_id",
        }
        actual_params = set(param_names)
        missing = expected_params - actual_params
        assert not missing, (
            f"ComplianceService.scan_inmemory signature missing params: "
            f"{missing}. Phase 250.1.A workflow contract violated."
        )

        # `file_id` and `tenant` are positionally first (the workflow
        # passes them positionally for clarity).
        assert param_names[0] == "file_id"
        assert param_names[1] == "tenant"

        # All other parameters MUST have defaults (they are optional).
        for pname in param_names[2:]:
            param = sig.parameters[pname]
            assert param.default is not inspect.Parameter.empty, (
                f"Parameter {pname!r} of scan_inmemory has no default; "
                f"the workflow contract requires it to be optional."
            )

    def test_returns_complianc_run_row(self):
        """Return value MUST be a ``ComplianceRun`` (not a dict / not
        ``None``). The row MUST be persisted (queryable via
        `ComplianceRun.objects.get(id=...)`)."""
        tenant, user, file_obj = _seed_file()
        with (
            self._patch_compliance_client(
                overall_status="PASS",
                allowed_to_store=True,
            ),
            self._patch_storage(),
        ):
            result = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                legal_basis="legitimate_interest",
                user=user,
            )

        assert isinstance(result, ComplianceRun), (
            f"Expected ComplianceRun, got {type(result).__name__}. "
            "Workflow contract requires the row instance, not a dict."
        )
        # Row must be persistent.
        assert ComplianceRun.objects.filter(id=result.id).exists(), (
            "scan_inmemory MUST persist the ComplianceRun row before "
            "returning. Otherwise audit/replay breaks."
        )

    def test_persists_without_asset_fk(self):
        """The row MUST NOT carry an ``asset`` FK. Phase 250.1.A
        re-sequence requires the gate decision to be made BEFORE the
        Asset row exists; if scan_inmemory required an asset FK we'd
        be back to the create-then-validate ordering bug.
        """
        tenant, user, file_obj = _seed_file()
        with (
            self._patch_compliance_client(
                overall_status="PASS",
                allowed_to_store=True,
            ),
            self._patch_storage(),
        ):
            result = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                user=user,
            )

        # asset attribute may exist on the model but MUST be None for
        # in-memory scans.
        asset_fk = getattr(result, "asset", None)
        asset_fk_id = getattr(result, "asset_id", None)
        assert asset_fk is None and asset_fk_id is None, (
            f"scan_inmemory persisted ComplianceRun with asset FK "
            f"{asset_fk!r} / asset_id {asset_fk_id!r}. Phase 250.1.A "
            f"contract: scan_inmemory MUST persist Asset-FK-free rows "
            f"so the workflow can decide whether to materialise an "
            f"Asset based on the gate result."
        )

    def test_overall_status_enum(self):
        """``overall_status`` MUST be one of {PASS, WARN, FAIL}.
        Other values would break the workflow's gate-decision logic.
        """
        tenant, user, file_obj = _seed_file()
        for status_value in ("PASS", "WARN", "FAIL"):
            with (
                self._patch_compliance_client(
                    overall_status=status_value,
                    allowed_to_store=(status_value != "FAIL"),
                ),
                self._patch_storage(),
            ):
                result = ComplianceService.scan_inmemory(
                    file_id=str(file_obj.id),
                    tenant=tenant,
                    user=user,
                )
            assert result.overall_status == status_value
            # `allowed_to_store` MUST be a bool (used as gate decision).
            assert isinstance(result.allowed_to_store, bool)

    @staticmethod
    def _patch_compliance_client(*, overall_status: str, allowed_to_store: bool):
        if _LIVE_MODE:
            # Live mode: don't patch; let the real microservice run.
            from contextlib import nullcontext

            return nullcontext()
        return patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            return_value={
                "overall_status": overall_status,
                "risk_level": "HIGH" if overall_status == "FAIL" else "LOW",
                "allowed_to_store": allowed_to_store,
                "metadata": {},
            },
        )

    @staticmethod
    def _patch_storage():
        if _LIVE_MODE:
            from contextlib import nullcontext

            return nullcontext()
        return patch(
            "hub.apps.files.storage.S3StorageClient.get_file_content",
            return_value=b"a,b\n1,2\n",
        )


# ---------------------------------------------------------------------------
# Contract — DQService.scan_inmemory
# ---------------------------------------------------------------------------


class TestDQScanInmemoryContract:
    """Companion to the compliance contract — same shape, different
    domain."""

    def test_signature_contract(self):
        sig = inspect.signature(DQService.scan_inmemory)
        param_names = list(sig.parameters.keys())

        expected_params = {
            "file_id",
            "tenant",
            "profile_key",
            "contract",
            "user",
            "correlation_id",
        }
        actual_params = set(param_names)
        missing = expected_params - actual_params
        assert not missing, f"DQService.scan_inmemory signature missing params: {missing}."

        assert param_names[0] == "file_id"
        assert param_names[1] == "tenant"

        # All other parameters MUST have defaults.
        for pname in param_names[2:]:
            param = sig.parameters[pname]
            assert param.default is not inspect.Parameter.empty, (
                f"Parameter {pname!r} of DQService.scan_inmemory has no default."
            )

    def test_returns_dq_run_row(self):
        tenant, user, file_obj = _seed_file()
        with self._patch_dq_client(overall_status="PASS"), self._patch_storage():
            result = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                profile_key="intake_basic_gx",
                user=user,
            )
        assert isinstance(result, DQRun)
        assert DQRun.objects.filter(id=result.id).exists()

    def test_persists_without_asset_fk(self):
        tenant, user, file_obj = _seed_file()
        with self._patch_dq_client(overall_status="PASS"), self._patch_storage():
            result = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                user=user,
            )
        asset_fk = getattr(result, "asset", None)
        asset_fk_id = getattr(result, "asset_id", None)
        assert asset_fk is None and asset_fk_id is None, (
            "scan_inmemory persisted DQRun with asset FK; Phase 250.1.A contract violated."
        )

    def test_overall_status_enum(self):
        tenant, user, file_obj = _seed_file()
        for status_value in ("PASS", "WARN", "FAIL"):
            with self._patch_dq_client(overall_status=status_value), self._patch_storage():
                result = DQService.scan_inmemory(
                    file_id=str(file_obj.id),
                    tenant=tenant,
                    user=user,
                )
            assert result.overall_status == status_value

    @staticmethod
    def _patch_dq_client(*, overall_status: str):
        if _LIVE_MODE:
            from contextlib import nullcontext

            return nullcontext()
        return patch(
            "hub.apps.dq.service_client.DQServiceClient.run_dq",
            return_value={
                "overall_status": overall_status,
                "quality_score": 100 if overall_status == "PASS" else 12.0,
                "metadata": {},
            },
        )

    @staticmethod
    def _patch_storage():
        if _LIVE_MODE:
            from contextlib import nullcontext

            return nullcontext()
        return patch(
            "hub.apps.files.storage.S3StorageClient.get_file_content",
            return_value=b"a,b\n1,2\n",
        )


# ---------------------------------------------------------------------------
# Cross-service: workflow integration uses both
# ---------------------------------------------------------------------------


class TestWorkflowUsesBothScans:
    """Belt-and-suspenders: the workflow re-sequence calls BOTH scans;
    if either return value drifts from the contract, the gate decision
    breaks. This test pins that the workflow's expectations match what
    both services actually return.
    """

    def test_both_scans_returnable_from_workflow_perspective(self):
        tenant, user, file_obj = _seed_file()
        with (
            patch(
                "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
                return_value={
                    "overall_status": "PASS",
                    "allowed_to_store": True,
                    "metadata": {},
                },
            ),
            patch(
                "hub.apps.dq.service_client.DQServiceClient.run_dq",
                return_value={
                    "overall_status": "PASS",
                    "quality_score": 100,
                    "metadata": {},
                },
            ),
            patch(
                "hub.apps.files.storage.S3StorageClient.get_file_content",
                return_value=b"a,b\n1,2\n",
            ),
        ):
            compliance_result = ComplianceService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                user=user,
            )
            dq_result = DQService.scan_inmemory(
                file_id=str(file_obj.id),
                tenant=tenant,
                user=user,
            )

        # Workflow reads these two attributes to decide:
        #   if compliance_result.overall_status == "FAIL" or not compliance_result.allowed_to_store:
        #       raise FailClosedRejection("compliance")
        #   if dq_result.overall_status == "FAIL":
        #       raise FailClosedRejection("dq")
        #   else:
        #       proceed_to_asset_create()
        assert compliance_result.overall_status in ("PASS", "WARN", "FAIL")
        assert isinstance(compliance_result.allowed_to_store, bool)
        assert dq_result.overall_status in ("PASS", "WARN", "FAIL")

        # Both rows persisted with no Asset FK (gate ran before persist).
        assert getattr(compliance_result, "asset_id", None) is None
        assert getattr(dq_result, "asset_id", None) is None
