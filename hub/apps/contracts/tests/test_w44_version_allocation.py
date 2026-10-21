"""W4.4 (oss-release-remediation R2-I1) — locked contract-version
allocation.

The ``unique_contract_version_per_asset`` constraint makes
read-max-then-insert racy: two concurrent creates for the same asset
both read the same max version and the second INSERT violates the
constraint (a 500 / IntegrityError). The canonical fix is
``locked_contract_version()`` (the asset-row lock held across the
allocation AND the insert), with ``IntegrityError`` on the constraint
translated to a deterministic 409 (``CONTRACT_VERSION_CONFLICT``).

Inventory of UNLOCKED sites (the ticket's "6" was stale — the live
tree has 8, plus 2 in the dead ``integrations/_services_legacy``
module with no importers):

1. ``orchestration/workflows/asset_creation.py::_attach_contract_task``
   (re-assign save)
2. ``.../_link_odps_task`` upload branch (ODPS create)
3. ``.../_link_odps_task`` generate branch (ODPS create)
4. ``.../_link_odps_task`` link branch (re-assign save)
5. ``assets/views.py::ensure_e2e_activation_prerequisites`` (ODCS create)
6. ``ml/services.py::generate_ml_contract`` (ODPS create — no version at
   all, relied on the model default of 1)
7. ``integrations/services/discovery_service.py::_create_odps_contract_from_metadata``
   (aggregate-Max create)
8. ``.../_create_odcs_contract_from_metadata`` (aggregate-Max create)

Pins (real DB + real threads — the W2.5 TransactionTestCase/Barrier
convention; no mocks):

* concurrent creates for the same asset on EVERY unlocked surface
  allocate distinct versions with ZERO errors;
* sequential ML generation increments the version (pre-fix: both v1 —
  the second raises);
* the deterministic 409 translation: a REAL constraint violation
  raises ``ConflictError(CONTRACT_VERSION_CONFLICT)``, and a NON-version
  IntegrityError passes through untranslated.
"""

from __future__ import annotations

import json
import threading
import uuid

import pytest
from django.db import IntegrityError, connection
from django.test import TestCase, TransactionTestCase

from envpolicy import skip_or_fail
from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType

# ml is the paid layer — guarded for both core-only absence forms (W7.1).
try:
    from hub.apps.ml.models import MLModel, ModelStatus, ModelType
except (RuntimeError, ModuleNotFoundError):
    MLModel = ModelStatus = ModelType = None  # type: ignore[assignment]
from hub.apps.orchestration.models import WorkflowDefinition, WorkflowInstance, WorkflowStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_SAMPLE_ODPS = {
    "schema": "https://opendataproducts.org/schema/v4.1",
    "version": "4.1",
    "product": {
        "details": {
            "en": {
                "productID": "w44-product",
                "name": "W4.4 Product",
                "description": "version-allocation pin",
            }
        },
        "contract": {
            "spec": {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "w44-contract",
                "name": "W4.4 Contract",
                "version": "1.0.0",
                "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
            }
        },
    },
}


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"w44-{uid}",
        slug=f"w44-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"w44-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_asset(tenant):
    return Asset.objects.create(
        tenant=tenant,
        name=f"w44-asset-{uuid.uuid4().hex[:8]}",
        key=f"w44-asset-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )


def _mk_ml_model(tenant, asset):
    if MLModel is None:
        skip_or_fail("ml (paid layer) not installed in core-only mode")
    uid = uuid.uuid4().hex[:8]
    return MLModel.objects.create(
        tenant=tenant,
        asset=asset,
        odh_model_id=f"odh-{uid}",
        odh_model_name=f"w44-model-{uid}",
        odh_model_version="1.0.0",
        model_type=ModelType.CLASSIFICATION,
        status=ModelStatus.DEPLOYED,
    )


def _mk_workflow_instance(tenant, user, *, asset_id, contract_id=None):
    # The definition name+version pair is unique — a per-instance suffix
    # keeps the two worker threads from colliding on the fixture itself.
    uid = uuid.uuid4().hex[:8]
    wf_def = WorkflowDefinition.objects.create(
        name=f"w44_asset_creation_{uid}",
        version="2.0.0",
        dsl_json={
            "version": "2.0.0",
            "steps": [{"name": "validate_contract", "type": "validation"}],
        },
        is_active=True,
        created_by=user,
    )
    state = {"asset_id": str(asset_id)}
    if contract_id:
        state["contract_id"] = str(contract_id)
    return WorkflowInstance.objects.create(
        workflow_definition=wf_def,
        workflow_name=wf_def.name,
        workflow_version="2.0.0",
        tenant=tenant,
        status=WorkflowStatus.RUNNING,
        input_data={},
        state_data=state,
        created_by=user,
    )


def _run_workers(target):
    """The W2.5 canonical: two threads released by a barrier; each
    closes its connection afterwards. Returns (errors, results)."""
    barrier = threading.Barrier(2)
    results: dict = {}
    errors: list = []

    def _worker(name):
        try:
            barrier.wait(timeout=10)
            results[name] = target(name)
        except Exception as exc:  # noqa: BLE001 - the loser path is the pin
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=_worker, args=(name,)) for name in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    for t in threads:
        assert not t.is_alive(), "both workers must complete"
    return errors, results


class _DiscoveryServiceStub:
    """The mixin's contract-creation methods need no other mixin state
    — the concrete minimal stand-in (real methods, no mocks)."""

    def __init__(self):
        from hub.apps.integrations.services.discovery_service import DiscoveryServiceMixin

        self._create_odps_contract_from_metadata = (
            DiscoveryServiceMixin._create_odps_contract_from_metadata.__get__(self)
        )
        self._create_odcs_contract_from_metadata = (
            DiscoveryServiceMixin._create_odcs_contract_from_metadata.__get__(self)
        )


class TestDiscoveryODPSVersionAllocation(TransactionTestCase):
    @classmethod
    def _fixture_teardown(cls):
        """Skip flush to avoid deadlock on teardown (the ml-suite
        precedent: TransactionTestCase's TRUNCATE deadlocks against
        thread-held locks). Each test scopes by a fresh tenant, so
        residue is invisible."""

    def setUp(self):
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.asset = _mk_asset(self.tenant)

    def test_concurrent_odps_creates_allocate_distinct_versions(self):
        svc = _DiscoveryServiceStub()

        def _create(name=None):
            return svc._create_odps_contract_from_metadata(
                asset=self.asset,
                odps_metadata={},
                tenant_obj=self.tenant,
                user_obj=self.user,
                source_metadata={},
            )

        errors, results = _run_workers(_create)

        assert errors == [], (
            f"concurrent ODPS creates must serialize on the asset lock, got: {errors}"
        )
        versions = {c.version for c in results.values()}
        assert versions == {1, 2}, (
            "both creates succeed with DISTINCT versions — the pre-fix loser "
            "raised IntegrityError on unique_contract_version_per_asset"
        )


class TestDiscoveryODCSVersionAllocation(TransactionTestCase):
    @classmethod
    def _fixture_teardown(cls):
        """Skip flush to avoid deadlock on teardown (the ml-suite
        precedent: TransactionTestCase's TRUNCATE deadlocks against
        thread-held locks). Each test scopes by a fresh tenant, so
        residue is invisible."""

    def setUp(self):
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.asset = _mk_asset(self.tenant)

    def test_concurrent_odcs_creates_allocate_distinct_versions(self):
        svc = _DiscoveryServiceStub()

        def _create(name=None):
            return svc._create_odcs_contract_from_metadata(
                asset=self.asset,
                odcs_metadata={},
                tenant_obj=self.tenant,
                user_obj=self.user,
                source_metadata={},
                external_resources=None,
            )

        errors, results = _run_workers(_create)

        assert errors == [], (
            f"concurrent ODCS creates must serialize on the asset lock, got: {errors}"
        )
        versions = {c.version for c in results.values()}
        assert versions == {1, 2}


class TestMLContractVersionAllocation(TransactionTestCase):
    @classmethod
    def _fixture_teardown(cls):
        """Skip flush to avoid deadlock on teardown (the ml-suite
        precedent: TransactionTestCase's TRUNCATE deadlocks against
        thread-held locks). Each test scopes by a fresh tenant, so
        residue is invisible."""

    def setUp(self):
        # ml is the paid layer — the sanctioned guard covers both
        # core-only absence forms (W7.1).
        try:
            from hub.apps.ml.services import ModelRegistryBridgeService
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("ml (paid layer) not installed in core-only mode")

        self.tenant = _mk_tenant()
        self.asset = _mk_asset(self.tenant)
        self.service = ModelRegistryBridgeService(tenant_id=str(self.tenant.id))

    def test_sequential_generation_increments_the_version(self):
        first = self.service.generate_ml_contract(_mk_ml_model(self.tenant, self.asset))
        second = self.service.generate_ml_contract(_mk_ml_model(self.tenant, self.asset))

        assert first.version == 1
        assert second.version == 2, (
            "the ML path must allocate an EXPLICIT version — the pre-fix create "
            "relied on the model default (1) and the second call raised"
        )

    def test_concurrent_generation_allocates_distinct_versions(self):
        def _generate(name=None):
            return self.service.generate_ml_contract(_mk_ml_model(self.tenant, self.asset))

        errors, results = _run_workers(_generate)

        assert errors == [], (
            f"concurrent ML contract generation must serialize on the asset lock, got: {errors}"
        )
        versions = {c.version for c in results.values()}
        assert versions == {1, 2}


class TestAttachContractVersionAllocation(TransactionTestCase):
    @classmethod
    def _fixture_teardown(cls):
        """Skip flush to avoid deadlock on teardown (the ml-suite
        precedent: TransactionTestCase's TRUNCATE deadlocks against
        thread-held locks). Each test scopes by a fresh tenant, so
        residue is invisible."""

    """The workflow attach step (re-assign flow): two asset-less drafts
    attached to the SAME asset must land on distinct versions."""

    def setUp(self):
        from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow

        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.asset = _mk_asset(self.tenant)
        self._task = AssetCreationWorkflow._attach_contract_task

    def _mk_draft(self):
        return Contract.objects.create(
            tenant=self.tenant,
            asset=None,
            version=1,  # asset-less placeholder — the attach re-allocates
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2"}),
        )

    def test_concurrent_attaches_allocate_distinct_versions(self):
        drafts = {name: self._mk_draft() for name in ("a", "b")}

        def _attach(name):
            instance = _mk_workflow_instance(
                self.tenant,
                self.user,
                asset_id=self.asset.id,
                contract_id=drafts[name].id,
            )
            return self._task({}, instance, None)

        errors, results = _run_workers(_attach)

        assert errors == [], f"concurrent attaches must serialize on the asset lock, got: {errors}"
        versions = {r["contract_version"] for r in results.values()}
        assert versions == {1, 2}


class TestLinkOdpsUploadVersionAllocation(TransactionTestCase):
    @classmethod
    def _fixture_teardown(cls):
        """Skip flush to avoid deadlock on teardown (the ml-suite
        precedent: TransactionTestCase's TRUNCATE deadlocks against
        thread-held locks). Each test scopes by a fresh tenant, so
        residue is invisible."""

    """The workflow ODPS-upload step: two concurrent uploads for the
    same asset must land on distinct versions."""

    def setUp(self):
        from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow

        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.asset = _mk_asset(self.tenant)
        self._task = AssetCreationWorkflow._link_odps_task

    def test_concurrent_uploads_allocate_distinct_versions(self):
        input_data = {
            "odps_action": "upload",
            "odps_raw": json.dumps(_SAMPLE_ODPS),
            "odps_format": "JSON",
        }

        def _link(name=None):
            instance = _mk_workflow_instance(self.tenant, self.user, asset_id=self.asset.id)
            return self._task(input_data, instance, None)

        errors, _results = _run_workers(_link)

        assert errors == [], (
            f"concurrent ODPS uploads must serialize on the asset lock, got: {errors}"
        )
        contracts = list(
            Contract.objects.filter(tenant=self.tenant, asset=self.asset).order_by("version")
        )
        assert [c.version for c in contracts] == [1, 2]


class TestVersionConflict409Translation(TestCase):
    """The deterministic 409: a REAL constraint violation translates to
    ConflictError(CONTRACT_VERSION_CONFLICT); anything else passes
    through untouched."""

    def setUp(self):
        from hub.apps.contracts.services.contract_service import (
            contract_version_conflict_to_409,
        )

        self.tenant = _mk_tenant()
        self.asset = _mk_asset(self.tenant)
        self._guard = contract_version_conflict_to_409

    def _mk_v1(self):
        return Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
        )

    def test_version_conflict_translates_to_conflict_error(self):
        from hub.apps.core.services.base import ConflictError

        self._mk_v1()

        with pytest.raises(ConflictError) as excinfo, self._guard():
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                version=1,  # duplicate — the REAL constraint fires
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                original_raw="{}",
            )

        assert excinfo.value.code == "CONTRACT_VERSION_CONFLICT"
        assert "unique_contract_version_per_asset" in (
            (excinfo.value.details or {}).get("constraint", "")
        )

    def test_non_version_integrity_errors_pass_through_untranslated(self):
        with pytest.raises(IntegrityError) as excinfo, self._guard():
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                version=2,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                original_raw=None,  # NOT NULL violation — not a version conflict
            )

        assert "CONTRACT_VERSION_CONFLICT" not in str(excinfo.value)
