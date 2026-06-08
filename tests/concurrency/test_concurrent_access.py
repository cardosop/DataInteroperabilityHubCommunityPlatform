"""
Concurrent access tests: multi-threaded API access to same and different
resources, tenant isolation. Real APIClient and DB; no mocks.
"""

import json
import threading
import uuid
from typing import List, Tuple

from rest_framework.test import APIClient

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.users.models import UserStatus
from tests.concurrency.base import ConcurrencyTestBase


class ConcurrentAccessTest(ConcurrencyTestBase):
    """Concurrent API access tests."""

    def test_multi_threaded_get_same_resource(self):
        """Multiple threads GET same contract: all 200."""
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
        clients = [APIClient() for _ in range(10)]
        for c in clients:
            c.force_authenticate(user=self.user)
        results: List[int] = []
        errors: List[str] = []

        def get_one(client: APIClient) -> None:
            try:
                r = client.get(f"/api/v1/contracts/{contract.id}/")
                results.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=get_one, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(results), 10)
        self.assertTrue(all(c == 200 for c in results))

    def test_multi_threaded_get_different_resources(self):
        """Multiple threads GET different contracts: all 200."""
        contracts = []
        for i in range(6):
            c = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw=json.dumps(self.create_contract_payload(product_id=f"acc-{i}")),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )
            contracts.append(c)
        clients = [APIClient() for _ in range(6)]
        for c in clients:
            c.force_authenticate(user=self.user)
        results: List[int] = []
        errors: List[str] = []

        def get_one(client: APIClient, contract_id: str) -> None:
            try:
                r = client.get(f"/api/v1/contracts/{contract_id}/")
                results.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=get_one, args=(clients[i], str(contracts[i].id)))
            for i in range(6)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(results), 6)
        self.assertTrue(all(c == 200 for c in results))

    def test_concurrent_list_requests(self):
        """Concurrent list (GET collection) requests: all succeed."""
        clients = [APIClient() for _ in range(5)]
        for c in clients:
            c.force_authenticate(user=self.user)
        results: List[Tuple[int, int]] = []
        errors: List[str] = []

        def list_one(client: APIClient) -> None:
            try:
                r = client.get("/api/v1/contracts/")
                count = len(r.data.get("results", [])) if isinstance(r.data, dict) else 0
                results.append((r.status_code, count))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=list_one, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(code == 200 for code, _ in results))

    def test_tenant_isolation_concurrent_access(self):
        """Concurrent access from different tenants: owner succeeds, other gets 403/404."""
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-iso-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_user = User.objects.create_user(
            email="other@other.test",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
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
        client_owner = APIClient()
        client_owner.force_authenticate(user=self.user)
        client_other = APIClient()
        client_other.force_authenticate(user=other_user)
        codes: List[int] = []
        errors: List[str] = []

        def req(client: APIClient) -> None:
            try:
                r = client.get(f"/api/v1/contracts/{contract.id}/")
                codes.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=req, args=(client_owner,))
        t2 = threading.Thread(target=req, args=(client_other,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0, errors)
        self.assertEqual(len(codes), 2)
        self.assertIn(200, codes)
        self.assertTrue(any(c in (403, 404) for c in codes))
