"""Phase 2.1 — ODPS twin idempotency race (deterministic, no mocks).

The bug: ``auto_generate_odps_for_odcs`` checks the ODCS's
``x_odps.odps_link`` and, finding none, generates + creates an ODPS twin
inside ``locked_contract_version``. Two concurrent calls both pass the
link check BEFORE either reaches the lock — the asset-row lock serializes
VERSION ALLOCATION only, not the get-or-create — so both create twins and
the second overwrites the link. Deterministic RED: the test holds the
asset-row EXCLUSIVE lock (explicit transaction, own connection) while two
threads run the real service; thread A blocks AT the version lock (after
its link check), thread B performs its link check while A is blocked (no
link committed yet) and queues too — on release both create. GREEN: the
link re-check inside the lock scope sees A's committed link and returns
the existing twin.

NO MOCKS: real Postgres, real threads, real service. The row lock is a
concurrency primitive, not a stub.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.services.contract_service import ContractService
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.tenants.tests.factories import SubscriptionFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

TOTAL_CALLS = 2


def _hub_contract_json() -> dict:
    """A HubContract the ODPS generator can consume (the ``info`` shape the
    generator requires — mirrors the real test fixture in
    ``test_odps_auto_generation.py``)."""
    return {
        "id": "twin-hub-contract",
        "info": {
            "name": "Twin Hub Contract",
            "description": "Race test source",
            "version": "1.0.0",
            "tags": ["race"],
            "owners": [{"name": "Race Owner", "email": "owner@example.com"}],
        },
        "schema": {"fields": [{"name": "id", "type": "string"}]},
        "marketplace": {
            "x_odps": {
                "pricing_plans": [{"name": "Basic Plan", "price": 10.00, "currency": "USD"}],
                "access_methods": {"api": {"endpoint": "https://api.example.com/data"}},
                "payment_gateways": {"stripe": {"enabled": True}},
            },
            "license_summary": "MIT License",
        },
        "lifecycle": {"slas": {"availability": 0.99}},
    }


def _setup():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Twin {uid}", slug=f"twin-{uid}", status="ACTIVE")
    plan = TenantPlan.objects.create(
        name=f"Twin Plan {uid}",
        slug=f"twin-plan-{uid}",
        tier="PRO",
        is_active=True,
        limits_json={"max_contracts": 1000},
    )
    tenant.plan = plan
    tenant.save(update_fields=["plan"])
    SubscriptionFactory.create_subscription(tenant=tenant, plan=plan)
    user = User.objects.create_user(
        email=f"twin-{uid}@meshant.test", password="testpass", tenant=tenant
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"twin-asset-{uid}",
        name="Twin Asset",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    # NOTE: the ODCS 3.0.2 wire format uses "schema" for BOTH the schema URL
    # and the fields block (the fields block wins in the real fixture) —
    # assign sequentially so the duplicated key doesn't trip lint (F601).
    odcs_doc = {
        "schema": "https://datacontract.com/schema/v3.0.2",
        "version": "3.0.2",
        "info": {"title": "Twin Data Contract", "version": "1.0.0"},
    }
    odcs_doc["schema"] = {"fields": [{"name": "id", "type": "string"}]}
    odcs_raw = json.dumps(odcs_doc, indent=2)
    odcs = Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_raw=odcs_raw,
        original_format=OriginalFormat.JSON,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.0.2",
        hub_contract_json=_hub_contract_json(),
        hub_contract_version="1.0.0",
        normalization_status=NormalizationStatus.NORMALIZED_OK,
        status="ACTIVE",
        created_by=user,
    )
    return tenant, user, asset, odcs


def _run_concurrent_twins(tenant_id: str, odcs_id: str) -> tuple[list[str], list[Exception]]:
    ids: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()
    entered = threading.Event()

    def worker(barrier: threading.Barrier) -> None:
        connections["default"].close()
        try:
            barrier.wait(timeout=60)
            entered.set()
            service = ContractService(tenant_id=tenant_id, user_id=None)
            twin = service.auto_generate_odps_for_odcs(
                odcs_contract_id=odcs_id,
                tenant_id=tenant_id,
            )
            with lock:
                ids.append(str(twin.id))
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            connections["default"].close()

    barrier = threading.Barrier(TOTAL_CALLS)
    with ThreadPoolExecutor(max_workers=TOTAL_CALLS) as executor:
        futures = [executor.submit(worker, barrier) for _ in range(TOTAL_CALLS)]
        assert entered.wait(timeout=30), "workers never entered the service"
        time.sleep(1.0)  # noqa: sleep-needed — test timing requirement  # INTENTIONAL: sleep-needed (auto-fixer marker completion)
        connection.commit()  # release the test-held asset-row lock
        for future in futures:
            future.result(timeout=120)
    return ids, errors


def _run_locked(asset: Asset, tenant_id: str, odcs_id: str):
    connection.set_autocommit(False)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT id FROM {Asset._meta.db_table} WHERE id = %s FOR UPDATE",
            [str(asset.pk)],
        )
        cursor.fetchone()
        return _run_concurrent_twins(tenant_id, odcs_id)
    finally:
        connection.commit()
        connection.set_autocommit(True)


def _run_locked_link(asset: Asset, link_callable):
    """Same lever for the link form — callable takes no args, returns a Contract."""
    ids: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()
    entered = threading.Event()

    def worker(barrier: threading.Barrier) -> None:
        connections["default"].close()
        try:
            barrier.wait(timeout=60)
            entered.set()
            twin = link_callable()
            with lock:
                ids.append(str(twin.id))
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            connections["default"].close()

    connection.set_autocommit(False)
    futures = []
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT id FROM {Asset._meta.db_table} WHERE id = %s FOR UPDATE",
            [str(asset.pk)],
        )
        cursor.fetchone()
        barrier = threading.Barrier(TOTAL_CALLS)
        executor = ThreadPoolExecutor(max_workers=TOTAL_CALLS)
        futures = [executor.submit(worker, barrier) for _ in range(TOTAL_CALLS)]
        assert entered.wait(timeout=30), "workers never entered the service"
        time.sleep(1.0)  # noqa: sleep-needed — test timing requirement  # INTENTIONAL: sleep-needed (auto-fixer marker completion)
        connection.commit()
        connection.set_autocommit(True)
        for future in futures:
            future.result(timeout=120)
    finally:
        if not connection.get_autocommit():
            connection.commit()
            connection.set_autocommit(True)
        executor.shutdown(wait=True)
    return ids, errors


class ODPSConcurrentTwinRaceTest:
    """The Phase 2.1 twin-race pins, class-based per the ODPS test-structure
    convention (test_odps_test_structure_conventions.py requires Test*
    classes — the module-level pytest functions here made the CORE-only
    suite fail its convention gate)."""

    def test_concurrent_auto_generate_creates_exactly_one_twin(self):
        """Two concurrent calls: exactly ONE ODPS twin; both calls return it."""
        tenant, _user, asset, odcs = _setup()
        ids, errors = _run_locked(asset, str(tenant.id), str(odcs.id))
        assert errors == [], (
            f"{len(errors)} of {TOTAL_CALLS} concurrent calls failed. First error: {errors[0]!r}"
        )
        assert len(set(ids)) == 1, (
            f"TWIN RACE: {TOTAL_CALLS} concurrent calls produced {len(set(ids))} "
            f"distinct ODPS twins ({ids}) — the get-or-create must serialize "
            "inside locked_contract_version"
        )
        odps_twins = Contract.objects.filter(
            tenant=tenant, asset=asset, original_spec_type=OriginalSpecType.ODPS
        )
        assert odps_twins.count() == 1, f"{odps_twins.count()} ODPS twins exist; want 1"

    def test_concurrent_link_odps_to_odcs_creates_exactly_one_twin(self):
        """The SAME race exists in link_odps_to_odcs's odps_raw form — two
        concurrent link calls both create twins (the review found the 2.1 fix
        had only covered auto_generate; "explicit target" is NOT the odps_raw
        path). The lock-scoped get-or-create must close it here too."""
        tenant, _user, asset, odcs = _setup()
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "link-odps-twin",
                            "name": "Link ODPS Twin",
                            "description": "Race test",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    # link validation requires product.contract.spec (the ODCS
                    # reference) — an empty spec dict skips the id/name checks.
                    "contract": {"spec": {}},
                },
            },
            indent=2,
        )

        def link_call() -> Contract:
            service = ContractService(tenant_id=str(tenant.id), user_id=None)
            return service.link_odps_to_odcs(
                odcs_contract_id=str(odcs.id),
                odps_raw=odps_raw,
                odps_format="json",
                tenant_id=str(tenant.id),
            )

        ids, errors = _run_locked_link(asset, link_call)
        assert errors == [], (
            f"{len(errors)} of {TOTAL_CALLS} concurrent link calls failed. First error: {errors[0]!r}"
        )
        assert len(set(ids)) == 1, f"TWIN RACE (link form): {len(set(ids))} distinct twins ({ids})"
        odps_twins = Contract.objects.filter(
            tenant=tenant, asset=asset, original_spec_type=OriginalSpecType.ODPS
        )
        assert odps_twins.count() == 1, f"{odps_twins.count()} ODPS twins exist; want 1"
