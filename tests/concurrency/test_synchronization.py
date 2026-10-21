"""
Synchronization tests: critical sections, serialization of updates.
Real DB; no mocks.
"""

import contextlib
import threading

from django.db import connection, transaction

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from tests.concurrency.base import ConcurrencyTestBase


class SynchronizationTest(ConcurrencyTestBase):
    """Synchronization and critical section behavior."""

    def test_serialized_updates_via_transaction(self):
        """Each update in its own transaction; final state consistent."""
        c = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw='{"schema":"x","version":"4.1","product":{}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )
        versions: list[int] = []
        lock = threading.Lock()

        def update_version(inc: int) -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    obj = Contract.objects.select_for_update().get(id=c.id, tenant=self.tenant)
                    new_ver = obj.version + inc
                    Contract.objects.filter(id=c.id).update(version=new_ver)
                    with lock:
                        versions.append(new_ver)
            except Exception:
                with lock:
                    versions.append(-1)
            finally:
                with contextlib.suppress(
                    Exception
                ):  # teardown cleanup: close errors must not mask the worker result
                    connection.close()

        threads = [
            threading.Thread(target=update_version, args=(1,)),
            threading.Thread(target=update_version, args=(2,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Both updates should complete; final version in DB is one of them
        final = Contract.objects.get(id=c.id)
        self.assertIn(final.version, versions)

    def test_concurrent_simple_atomic_updates(self):
        """Concurrent atomic updates on different rows: all succeed."""
        contracts = []
        for _i in range(4):
            c = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw='{"schema":"x","version":"4.1","product":{}}',
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=_i + 1,  # unique_contract_version_per_asset: distinct per row
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )
            contracts.append(c)
        results: list[bool] = []
        lock = threading.Lock()

        def update_one(contract_id, idx) -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    # Distinct target versions keep the per-asset unique
                    # constraint satisfied across the 4 concurrent updates.
                    Contract.objects.filter(id=contract_id, tenant=self.tenant).update(
                        version=100 + idx
                    )
                with lock:
                    results.append(True)
            except Exception:
                with lock:
                    results.append(False)
            finally:
                with contextlib.suppress(
                    Exception
                ):  # teardown cleanup: close errors must not mask the worker result
                    connection.close()

        threads = [
            threading.Thread(target=update_one, args=(c.id, i)) for i, c in enumerate(contracts)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 4)
        self.assertTrue(all(results))
