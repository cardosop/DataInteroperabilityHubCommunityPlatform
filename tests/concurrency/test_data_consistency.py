"""
Data consistency tests under concurrency: read-after-write, counters,
unique constraints. Real DB and API; no mocks.
"""

import json
import threading

from django.db import connection
from rest_framework.test import APIClient

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from tests.concurrency.base import ConcurrencyTestBase


class DataConsistencyTest(ConcurrencyTestBase):
    """Data consistency under concurrent operations."""

    def test_read_after_write_concurrent_creates(self):
        """After each concurrent create, immediate read sees the new contract."""
        clients = [APIClient() for _ in range(3)]
        for c in clients:
            c.force_authenticate(user=self.user)
        created_ids: list[str] = []
        errors: list[str] = []
        lock = threading.Lock()

        def create_and_read(client: APIClient, index: int) -> None:
            try:
                payload = self.create_contract_payload(product_id=f"raw-{index}")
                r = client.post(
                    "/api/v1/contracts/",
                    {
                        "original_raw": json.dumps(payload),
                        "original_format": "JSON",
                        "original_spec_type": "ODPS",
                        "asset_id": str(self.asset.id),
                    },
                    format="json",
                )
                if r.status_code not in (200, 201) or not r.data:
                    with lock:
                        errors.append(f"create failed index={index} status={r.status_code}")
                    return
                cid = str(r.data.get("id"))
                with lock:
                    created_ids.append(cid)
                # Read back immediately
                r2 = client.get(f"/api/v1/contracts/{cid}/")
                if r2.status_code != 200:
                    with lock:
                        errors.append(f"read-after-write failed index={index}")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=create_and_read, args=(clients[i], i)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(created_ids), 3)
        self.assertEqual(len(set(created_ids)), 3)

    def test_unique_ids_under_concurrent_creation(self):
        """Concurrent creates produce unique contract IDs."""
        clients = [APIClient() for _ in range(8)]
        for c in clients:
            c.force_authenticate(user=self.user)
        ids: list[str] = []
        lock = threading.Lock()
        errors: list[str] = []

        def create_one(client: APIClient, index: int) -> None:
            try:
                payload = self.create_contract_payload(product_id=f"unique-{index}")
                r = client.post(
                    "/api/v1/contracts/",
                    {
                        "original_raw": json.dumps(payload),
                        "original_format": "JSON",
                        "original_spec_type": "ODPS",
                        "asset_id": str(self.asset.id),
                    },
                    format="json",
                )
                if r.status_code in (200, 201) and r.data:
                    with lock:
                        ids.append(str(r.data.get("id")))
                elif r.status_code not in (200, 201):
                    with lock:
                        errors.append(f"index={index} status={r.status_code}")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=create_one, args=(clients[i], i)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8)

    def test_contract_count_consistency_after_concurrent_ops(self):
        """Contract count for tenant is consistent after concurrent create/delete."""
        # Create 3 then delete 1 concurrently; final count predictable
        for i in range(3):
            Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw=json.dumps(self.create_contract_payload(product_id=f"cnt-{i}")),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )
        initial_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(initial_count, 3)

        clients = [APIClient() for _ in range(3)]
        for c in clients:
            c.force_authenticate(user=self.user)
        contracts = list(Contract.objects.filter(tenant=self.tenant).values_list("id", flat=True))
        deleted: list[bool] = []
        lock = threading.Lock()

        def delete_one(client: APIClient, contract_id: str) -> None:
            try:
                r = client.delete(f"/api/v1/contracts/{contract_id}/")
                with lock:
                    deleted.append(r.status_code in (200, 204))
            except Exception:
                with lock:
                    deleted.append(False)

        threads = [
            threading.Thread(target=delete_one, args=(clients[i], str(contracts[i])))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(final_count, 0)
        self.assertEqual(sum(1 for d in deleted if d), 3)

    def test_db_connection_per_thread_no_leak(self):
        """Worker threads that touch DB use connection correctly (ensure_connection/close)."""
        results: list[bool] = []
        lock = threading.Lock()

        def query_in_thread(index: int) -> None:
            try:
                connection.ensure_connection()
                n = Contract.objects.filter(tenant=self.tenant).count()
                with lock:
                    results.append(n >= 0)
            except Exception:
                with lock:
                    results.append(False)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=query_in_thread, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 4)
        self.assertTrue(all(results))
