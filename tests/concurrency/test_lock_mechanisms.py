"""
Lock mechanism tests: transaction isolation, no deadlocks under load.
Uses real DB; no mocks.
"""

import threading
from typing import List

from django.db import connection, transaction

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from tests.concurrency.base import ConcurrencyTestBase


class LockMechanismsTest(ConcurrencyTestBase):
    """Lock and transaction isolation behavior under concurrency."""

    def test_concurrent_transactions_no_deadlock(self):
        """Multiple threads each run a short transaction; no deadlock."""
        contract = Contract.objects.create(
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
        results: List[bool] = []
        errors: List[str] = []
        lock = threading.Lock()

        def run_transaction(index: int) -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    Contract.objects.filter(id=contract.id, tenant=self.tenant).update(
                        version=contract.version + 1 + index
                    )
                with lock:
                    results.append(True)
            except Exception as e:
                with lock:
                    errors.append(str(e))
                    results.append(False)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=run_transaction, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(results), 5)
        self.assertGreaterEqual(sum(results), 4)

    def test_sequential_transaction_isolation(self):
        """Transactions in different threads see consistent state (no dirty read)."""
        Contract.objects.create(
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
        counts: List[int] = []
        lock = threading.Lock()

        def read_count() -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    n = Contract.objects.filter(tenant=self.tenant).count()
                    with lock:
                        counts.append(n)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=read_count) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(counts), 4)
        self.assertTrue(all(c == 1 for c in counts))

    def test_concurrent_reads_no_blocking(self):
        """Concurrent read-only transactions do not block each other."""
        for i in range(3):
            Contract.objects.create(
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
        results: List[int] = []
        lock = threading.Lock()

        def read_all() -> None:
            try:
                connection.ensure_connection()
                n = Contract.objects.filter(tenant=self.tenant).count()
                with lock:
                    results.append(n)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=read_all) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 8)
        self.assertTrue(all(r == 3 for r in results))
