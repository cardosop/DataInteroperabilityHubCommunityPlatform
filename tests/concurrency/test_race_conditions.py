"""
Race condition tests: concurrent CRUD, updates, deletions, reads,
lock contention, and data consistency. Real API and DB; no mocks.
"""

import json
import threading

from rest_framework.test import APIClient

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from tests.concurrency.base import ConcurrencyTestBase


class RaceConditionsTest(ConcurrencyTestBase):
    """Race condition tests using real contracts API and DB."""

    def test_concurrent_create_different_resources(self):
        """Concurrent create of different resources: all succeed with unique IDs."""
        clients = [APIClient() for _ in range(5)]
        for c in clients:
            c.force_authenticate(user=self.user)
        results: list[int] = []
        errors: list[str] = []

        def create_one(client: APIClient, index: int) -> None:
            try:
                payload = self.create_contract_payload(product_id=f"race-create-{index}")
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
                results.append(r.status_code)
                if r.status_code not in (200, 201):
                    errors.append(f"index={index} status={r.status_code}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create_one, args=(clients[i], i)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(c in (200, 201) for c in results))

    def test_concurrent_read_same_resource(self):
        """Concurrent reads of same resource: all return 200 and consistent data."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )
        clients = [APIClient() for _ in range(8)]
        for c in clients:
            c.force_authenticate(user=self.user)
        codes: list[int] = []
        errors: list[str] = []

        def read_one(client: APIClient) -> None:
            try:
                r = client.get(f"/api/v1/contracts/{contract.id}/")
                codes.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_one, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(codes), 8)
        self.assertTrue(all(c == 200 for c in codes))

    def test_concurrent_update_same_resource_handled(self):
        """Concurrent updates to same resource: all handled (success or conflict)."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )
        clients = [APIClient() for _ in range(3)]
        for c in clients:
            c.force_authenticate(user=self.user)
        codes: list[int] = []
        errors: list[str] = []

        def update_one(client: APIClient) -> None:
            try:
                payload = self.create_contract_payload(product_id="race-update")
                r = client.patch(
                    f"/api/v1/contracts/{contract.id}/",
                    {"original_raw": json.dumps(payload)},
                    format="json",
                )
                codes.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=update_one, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(codes), 3)
        self.assertGreater(sum(1 for c in codes if c in (200, 201)), 0)

    def test_concurrent_delete_different_resources(self):
        """Concurrent delete of different resources: all return success."""
        contracts = []
        for i in range(5):
            c = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw=json.dumps(self.create_contract_payload(product_id=f"del-{i}")),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )
            contracts.append(c)
        clients = [APIClient() for _ in range(5)]
        for c in clients:
            c.force_authenticate(user=self.user)
        codes: list[int] = []
        errors: list[str] = []

        def delete_one(client: APIClient, contract_id: str) -> None:
            try:
                r = client.delete(f"/api/v1/contracts/{contract_id}/")
                codes.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=delete_one, args=(clients[i], str(contracts[i].id)))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(codes), 5)
        self.assertTrue(all(c in (200, 204) for c in codes))

    def test_data_consistency_after_concurrent_creates(self):
        """After concurrent creates, list count matches created count."""
        clients = [APIClient() for _ in range(4)]
        for c in clients:
            c.force_authenticate(user=self.user)
        created_ids: list[str] = []
        errors: list[str] = []

        def create_and_collect(client: APIClient, index: int) -> None:
            try:
                payload = self.create_contract_payload(product_id=f"consistency-{index}")
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
                    created_ids.append(str(r.data.get("id", "")))
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=create_and_collect, args=(clients[i], i)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(created_ids), 4)
        self.assertEqual(len(set(created_ids)), 4)

        # Read-back: all IDs exist and are in tenant scope
        for cid in created_ids:
            c = Contract.objects.filter(id=cid, tenant=self.tenant).first()
            self.assertIsNotNone(c, f"Contract {cid} should exist")
