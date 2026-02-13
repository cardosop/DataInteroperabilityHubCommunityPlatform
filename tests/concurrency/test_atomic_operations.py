"""
Atomic operations tests: F() expressions, get_or_create, update_or_create
under concurrency. Real DB; no mocks.
"""

import threading
from typing import List

from django.db import IntegrityError, connection, transaction
from django.db.models import F

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from tests.concurrency.base import ConcurrencyTestBase


class AtomicOperationsTest(ConcurrencyTestBase):
    """Atomic DB operations under concurrency."""

    def test_f_expression_concurrent_increment(self):
        """Concurrent F() increment on version: no lost updates (all complete)."""
        c = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw='{"schema":"x","version":"4.1","product":{}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=0,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )
        results: List[bool] = []
        lock = threading.Lock()

        def increment() -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    Contract.objects.filter(id=c.id, tenant=self.tenant).update(
                        version=F("version") + 1
                    )
                with lock:
                    results.append(True)
            except Exception:
                with lock:
                    results.append(False)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(results), 5)
        self.assertTrue(all(results))
        c.refresh_from_db()
        self.assertEqual(c.version, 5)

    def test_get_or_create_concurrent_same_natural_key(self):
        """Concurrent get_or_create with same lookup: one create, others get (or one create)."""
        slug = f"atomic-tenant-{id(self)}"
        Tenant.objects.filter(slug=slug).delete()
        created_ids: List[int] = []
        lock = threading.Lock()

        def get_or_create_tenant() -> None:
            try:
                connection.ensure_connection()
                try:
                    tenant, created = Tenant.objects.get_or_create(
                        slug=slug,
                        defaults={
                            "name": "Atomic Tenant",
                            "status": TenantStatus.ACTIVE,
                            "kyc_status": KYCStatus.UNVERIFIED,
                        },
                    )
                except IntegrityError:
                    tenant = Tenant.objects.get(slug=slug)
                with lock:
                    created_ids.append(tenant.id)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=get_or_create_tenant) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(created_ids), 4)
        self.assertEqual(len(set(created_ids)), 1)
        Tenant.objects.filter(slug=slug).delete()

    def test_atomic_save_under_concurrency(self):
        """Multiple threads each create one contract in atomic block; all exist."""
        created: List[str] = []
        lock = threading.Lock()

        def create_atomic(idx: int) -> None:
            try:
                connection.ensure_connection()
                with transaction.atomic():
                    c = Contract(
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
                    c.save()
                    with lock:
                        created.append(str(c.id))
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=create_atomic, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(created), 3)
        self.assertEqual(len(set(created)), 3)

    def test_update_or_create_concurrent(self):
        """Concurrent update_or_create with same lookup: one record, consistent state."""
        slug = "atomic-update-or-create-%s" % (id(self),)
        Tenant.objects.filter(slug=slug).delete()

        def update_or_create_tenant(idx: int) -> None:
            try:
                connection.ensure_connection()
                defaults = {
                    "name": "Atomic Update Tenant %d" % idx,
                    "status": TenantStatus.ACTIVE,
                    "kyc_status": KYCStatus.UNVERIFIED,
                }
                Tenant.objects.update_or_create(slug=slug, defaults=defaults)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass  # Ignore connection close errors in teardown

        threads = [threading.Thread(target=update_or_create_tenant, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        count = Tenant.objects.filter(slug=slug).count()
        self.assertEqual(count, 1)
        tenant = Tenant.objects.get(slug=slug)
        names = ["Atomic Update Tenant %d" % i for i in range(4)]
        self.assertIn(tenant.name, names)
        Tenant.objects.filter(slug=slug).delete()
