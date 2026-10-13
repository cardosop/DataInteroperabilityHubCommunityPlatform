"""
W4.2 (R2-B5) — search reindex on contract PATCH.

Root cause pre-fix: the post-save cascade's Step 5
(``contracts/cache_invalidation.py::_trigger_search_reindex``) imported
``enqueue_contract_reindex`` from ``hub.apps.search.indexing`` — a symbol
that did NOT exist — and SWALLOWED the ImportError ("search app is
optional at import-time").  The signal-driven path only refreshes the
tsvector COLUMN on the Contract row
(``enqueue_contract_search_vector_update``); the SearchIndex ROW — the
title/description/schema/search_vector surface the unified search UI
actually reads (Phase 226 G12) — was never refreshed on PATCH, so a
renamed contract stayed searchable under its old title until a manual
bulk reindex.

These pins run REAL services and REAL RQ (tests run enqueued jobs
inline: ``RQ_QUEUES ASYNC=False`` under pytest) — no mocks.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.contracts.services import ContractService
from hub.apps.search.models import SearchIndex
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()

_RAW_ODCS = (
    '{"id": "test-contract", "info": {"name": "w42-contract"}, '
    '"schema": {"fields": [{"name": "id", "type": "string"}]}}'
)


class TestContractPatchSearchReindex(TestCase):
    """contract PATCH → the SearchIndex row reflects the new content."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W42 {uid}",
            slug=f"w42-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"w42-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def _search_row(self, contract):
        return SearchIndex.objects.get(
            tenant=self.tenant, resource_type="CONTRACT", resource_id=contract.id
        )

    def test_patch_updates_search_index_row(self):
        """The primary PATCH path must refresh the SearchIndex ROW (title +
        search_vector), not just the tsvector column.

        W4.5 — the post-save cascade (Step 5 included) now runs
        ``on_commit`` (R2-I2), so the reindex fires when the update's
        transaction commits. The pin drains the queued commit hooks via
        Django's ``captureOnCommitCallbacks`` — the canonical mechanism,
        the real callbacks, no mocks."""
        contract = self.service.create_contract(
            original_raw=_RAW_ODCS, original_format="JSON"
        )

        row = self._search_row(contract)
        self.assertEqual(row.title, "w42-contract")

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.service.update_contract(
                contract_id=str(contract.id),
                original_raw=(
                    '{"id": "test-contract", "info": {"name": "w42-contract-renamed"}, '
                    '"schema": {"fields": [{"name": "id", "type": "string"}]}}'
                ),
                original_format="JSON",
            )
        self.assertTrue(
            callbacks, "the PATCH must defer the post-save cascade to commit"
        )

        row.refresh_from_db()
        self.assertEqual(row.title, "w42-contract-renamed")
        self.assertIsNotNone(row.search_vector)

    def test_enqueue_contract_reindex_refreshes_stale_row(self):
        """``enqueue_contract_reindex`` must EXIST (the pre-fix import raised
        ImportError — this pin imports it directly) and, with the test
        stack's inline RQ, refresh a stale row when called."""
        from hub.apps.search.indexing import enqueue_contract_reindex

        contract = self.service.create_contract(
            original_raw=_RAW_ODCS, original_format="JSON"
        )
        row = self._search_row(contract)

        # Simulate the staleness a missed cascade would leave behind:
        # change the source content WITHOUT going through the cascade.
        from hub.apps.contracts.models import Contract

        Contract.objects.filter(pk=contract.pk).update(
            hub_contract_json={
                "info": {"name": "w42-contract-stale-fix"},
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )
        row.refresh_from_db()
        self.assertEqual(row.title, "w42-contract")  # still stale

        enqueue_contract_reindex(contract_id=str(contract.id))

        row.refresh_from_db()
        self.assertEqual(row.title, "w42-contract-stale-fix")
        self.assertIsNotNone(row.search_vector)


class TestNoSwallowedImportError(TestCase):
    """The structural half of R2-B5: the cascade's Step 5 must NOT swallow
    ImportError — the search app is always installed in this deployment, so
    a missing symbol is a real bug that must surface (the cascade's
    ``run_side_effect`` wrapper keeps the user-facing path fail-open)."""

    def test_trigger_search_reindex_has_no_swallowed_importerror(self):
        import inspect

        from hub.apps.contracts.cache_invalidation import _trigger_search_reindex

        source = inspect.getsource(_trigger_search_reindex)
        # The contract: no ``except ImportError`` SWALLOW clause (the
        # docstring may still mention the historical root cause).
        self.assertNotIn("except ImportError", source)
        self.assertIn("enqueue_contract_reindex", source)
