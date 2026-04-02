"""Constraint-based contract update tests (replaces threading-based concurrency)."""
import uuid

from django.test import TestCase

from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.tenants.models import Tenant


class ContractUpdateConsistencyTest(TestCase):
    """Sequential updates produce consistent DB state."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"CU {uid}", slug=f"cu-{uid}")
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw="test: true",
            original_format="YAML",
            status=ContractStatus.DRAFT,
        )

    def test_update_changes_field(self):
        self.contract.original_raw = "updated: yes"
        self.contract.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.original_raw, "updated: yes")

    def test_two_sequential_updates_last_write_wins(self):
        self.contract.original_raw = "first update"
        self.contract.save()
        self.contract.original_raw = "second update"
        self.contract.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.original_raw, "second update")
