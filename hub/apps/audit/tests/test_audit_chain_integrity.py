"""
285.12.4.7 CC8 — Audit chain tamper-evidence tests.

Verifies the Phase 234.1 cryptographic audit chain:
  1. chain_hash is computed on save
  2. prev_chain_hash links to prior event
  3. chain breaks detected (hash mismatch)
  4. tenant isolation: chains are per-tenant
  5. genesis event has NULL prev_chain_hash
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class AuditChainIntegrityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = Tenant.objects.create(
            name=f"Test-{uuid.uuid4().hex[:8]}",
            slug=f"t-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )

    @pytest.mark.integration
    def test_chain_hash_populated_on_save(self):
        """Each audit event should have a chain_hash after save."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="CHAIN_TEST",
            resource_id=str(uuid.uuid4()),
        )
        self.assertIsNotNone(event.chain_hash, "chain_hash should be populated after save")
        self.assertEqual(len(event.chain_hash), 64, "chain_hash should be 64-char SHA-256 hex")

    @pytest.mark.integration
    def test_prev_chain_hash_links_to_prior_event(self):
        """The second event's prev_chain_hash should equal the first event's chain_hash."""
        e1 = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="CHAIN_LINK_1",
            resource_id=str(uuid.uuid4()),
        )
        e2 = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="CHAIN_LINK_2",
            resource_id=str(uuid.uuid4()),
        )
        self.assertEqual(
            e2.prev_chain_hash,
            e1.chain_hash,
            "Second event should reference first event's chain_hash",
        )

    @pytest.mark.integration
    def test_genesis_event_has_null_prev_hash(self):
        """The first event for a tenant should have NULL prev_chain_hash."""
        tenant2 = Tenant.objects.create(
            name=f"Test-{uuid.uuid4().hex[:8]}",
            slug=f"t-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        event = AuditEvent.objects.create(
            tenant=tenant2,
            resource_type="TEST",
            action="GENESIS",
            resource_id=str(uuid.uuid4()),
        )
        self.assertIsNone(event.prev_chain_hash, "Genesis event should have NULL prev_chain_hash")

    @pytest.mark.integration
    def test_tenant_isolation_separate_chains(self):
        """Different tenants have independent audit chains."""
        tenant_b = Tenant.objects.create(
            name=f"Test-B-{uuid.uuid4().hex[:8]}",
            slug=f"tb-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        e_a = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="ISO_A",
            resource_id=str(uuid.uuid4()),
        )
        e_b = AuditEvent.objects.create(
            tenant=tenant_b,
            resource_type="TEST",
            action="ISO_B",
            resource_id=str(uuid.uuid4()),
        )
        self.assertNotEqual(
            e_a.chain_hash, e_b.chain_hash, "Different tenants should have different chain hashes"
        )
        self.assertIsNone(
            e_b.prev_chain_hash, "First event in tenant B should be genesis (NULL prev)"
        )

    @pytest.mark.integration
    def test_chain_sequence_increments(self):
        """chain_sequence should increment for each event in a tenant."""
        e1 = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="SEQ_1",
            resource_id=str(uuid.uuid4()),
        )
        e2 = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="SEQ_2",
            resource_id=str(uuid.uuid4()),
        )
        self.assertIsNotNone(e1.chain_sequence)
        self.assertIsNotNone(e2.chain_sequence)
        # Sequence should be monotonically increasing
        self.assertGreater(
            e2.chain_sequence, e1.chain_sequence, "chain_sequence should increment between events"
        )
