"""
Phase 226 G12 (revised from 250.1.F) — search-vector signal-timing tests.

Contract under test
-------------------

The post_save signal handler at
``hub.apps.assets.signals.rebuild_asset_search_vector`` MUST enqueue an
``enqueue_asset_search_vector_update`` job on EVERY save — including:

* **DRAFT creates** — Phase 226 G12 promises "after a successful create,
  the resource is queryable via the unified search index". Drafts are
  tenant-scoped in search (RLS), so indexing them adds no cross-tenant
  discoverability; it restores owner findability. The old 250.1.F
  "no-enqueue while DRAFT" optimization was retired because it silently
  broke that promise (and made search a lossy index of the tenant's
  resources).

* **DRAFT edits** (renames, description changes) — the vector must track
  the searchable text regardless of status.

* **The activation save** (``DRAFT → ACTIVE`` inside the
  asset-activation saga) — a rebuild lands on the same
  ``transaction.on_commit`` as the activation.

* **Subsequent non-DRAFT saves** — renames, description edits, domain
  changes, and the ``ACTIVE → PUBLIC`` / ``ACTIVE → RETIRED`` /
  ``PUBLIC → RETIRED`` transitions (RETIRED stays searchable for
  post-retirement audit).

* **Rollbacks to DRAFT** (``compensate_activation``) — previously the
  handler NULLed ``search_vector`` so the rolled-back asset vanished
  from search; it now re-indexes as DRAFT. A rollback means "this is
  WIP again", and WIP must stay findable by its owner.

Integration invariant
---------------------
After a DRAFT create and a run of the real rebuild task body
(``hub.apps.search.tasks.update_asset_search_vector``), the row's
``search_vector`` is a non-null PostgreSQL ``tsvector`` — search-vector
existence tracks "the task ran", not "the asset is non-DRAFT".

TDD doctrine
------------
* Real Django ORM rows + real ``post_save`` dispatch + real
  ``django.test.TestCase.captureOnCommitCallbacks(execute=True)``
  to drive the deferred enqueue paths.
* The enqueue itself is patched (only the boundary into
  ``django_rq``) so we can spy on call-count without standing up a
  real RQ worker. NO mocks of business logic.
* The integration tests invoke the real
  ``hub.apps.search.tasks.update_asset_search_vector`` task body
  against a real PostgreSQL row to verify the ``tsvector`` actually
  materializes.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.signals import post_save
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_tenant(*, suffix: str | None = None) -> Tenant:
    uid = suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"SearchVectorTimingTest-{uid}",
        slug=f"sv-timing-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _seed_user(tenant: Tenant) -> User:
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
    )


def _seed_draft(tenant: Tenant, user: User, *, key_suffix: str = "") -> Asset:
    """Create a DRAFT asset. Status defaults to DRAFT on the model;
    we set it explicitly for clarity."""
    return Asset.objects.create(
        tenant=tenant,
        key=f"sv-{uuid.uuid4().hex[:8]}{key_suffix}",
        name="Search Vector Timing Asset",
        description="A description",
        domain="testdomain",
        status=AssetStatus.DRAFT,
        created_by=user,
    )


def _running_on_postgres() -> bool:
    return connection.vendor == "postgresql"


# ---------------------------------------------------------------------------
# 226 G12 — signal-timing contract: every save enqueues
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDraftSaveEnqueues(TestCase):
    """DRAFT saves (create or update) MUST enqueue a search-vector
    rebuild — drafts are tenant-scoped searchable per Phase 226 G12."""

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_create_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        mock_enqueue.assert_called_once_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_rename_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "Renamed Draft"
            asset.save(update_fields=["name", "updated_at"])

        mock_enqueue.assert_called_once_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_description_edit_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.description = "Updated description while still DRAFT"
            asset.save(update_fields=["description", "updated_at"])

        mock_enqueue.assert_called_once_with(str(asset.pk))


@pytest.mark.django_db(transaction=True)
class TestActivationEnqueues(TestCase):
    """The DRAFT → ACTIVE transition enqueues a rebuild like every
    other save (activation shares the same on_commit enqueue)."""

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_to_active_transition_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        self.assertEqual(mock_enqueue.call_count, 1)
        mock_enqueue.reset_mock()

        # Step 2: activate — flip to ACTIVE on the canonical save path
        # used by hub.apps.orchestration.workflows.asset_activation_saga
        # .activate_asset.
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])

        mock_enqueue.assert_called_once_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_direct_create_active_enqueues(self, mock_enqueue):
        """Creating an asset that is born ACTIVE (legacy seed,
        scheduled-ingest auto-activate, fixtures) enqueues on
        the very first save — no DRAFT detour."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = Asset.objects.create(
                tenant=tenant,
                key=f"direct-active-{uuid.uuid4().hex[:8]}",
                name="Born Active",
                description="No draft phase",
                domain="legacy",
                status=AssetStatus.ACTIVE,
                created_by=user,
            )

        mock_enqueue.assert_called_once_with(str(asset.pk))


@pytest.mark.django_db(transaction=True)
class TestPostActivationUpdatesEnqueue(TestCase):
    """Every save still enqueues so the vector tracks renames /
    description edits / domain edits / status transitions."""

    def _seed_active(self, tenant: Tenant, user: User) -> Asset:
        return Asset.objects.create(
            tenant=tenant,
            key=f"active-{uuid.uuid4().hex[:8]}",
            name="Active asset",
            description="initial",
            domain="initial",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_active_rename_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = self._seed_active(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "Renamed"
            asset.save(update_fields=["name", "updated_at"])

        mock_enqueue.assert_called_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_active_to_public_enqueues(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = self._seed_active(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.PUBLIC
            asset.save(update_fields=["status", "updated_at"])

        mock_enqueue.assert_called_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_active_to_retired_enqueues(self, mock_enqueue):
        """RETIRED still has a vector — post-retirement audit search
        relies on it. The semantic-tombstone signal is a separate
        concern (handled by ``_fire_asset_tombstone_if_retired``)."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = self._seed_active(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.RETIRED
            asset.save(update_fields=["status", "updated_at"])

        mock_enqueue.assert_called_with(str(asset.pk))


@pytest.mark.django_db(transaction=True)
class TestSignalConnectivity(TestCase):
    """The signal must remain wired — regression guard against an
    accidental ``post_save.disconnect`` during refactor."""

    def test_signal_handler_is_connected(self):
        from hub.apps.assets.signals import rebuild_asset_search_vector

        receivers = [r[1]() for r in post_save.receivers if r[1]() is not None]
        self.assertIn(
            rebuild_asset_search_vector,
            receivers,
            "rebuild_asset_search_vector MUST be connected to Asset post_save.",
        )


# ---------------------------------------------------------------------------
# 226 G12 — integration: the rebuild task materializes the vector
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestSearchVectorExistsAfterTaskRun(TestCase):
    """End-to-end: the vector is NULL until the (async) rebuild task
    runs; after it runs, the vector materializes — regardless of
    DRAFT/ACTIVE status."""

    def test_draft_asset_vector_populated_on_create(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        # run_after_commit dispatches synchronously under pytest, so the
        # rebuild task runs inline with the create — the vector is
        # populated immediately. This is the Phase 226 G12 invariant in
        # its strongest form: a successful create is searchable at once.
        asset.refresh_from_db()
        self.assertIsNotNone(
            asset.search_vector,
            "DRAFT asset MUST have a populated search_vector right "
            "after create — Phase 226 G12 makes drafts searchable and "
            "the test-mode dispatcher runs the rebuild inline.",
        )

    def test_draft_asset_vector_populates_after_task_run(self):
        """Create DRAFT → run the rebuild task → the row's
        search_vector is non-null. This is the Phase 226 G12
        invariant: a successful create becomes searchable once the
        indexer processes the enqueued job."""
        if not _running_on_postgres():
            self.skipTest("search_vector requires PostgreSQL tsvector support.")

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        update_asset_search_vector(str(asset.pk))

        asset.refresh_from_db()
        self.assertIsNotNone(
            asset.search_vector,
            "After the rebuild task runs, a DRAFT asset MUST have a "
            "non-null search_vector — Phase 226 G12 makes drafts "
            "searchable.",
        )

    def test_activation_then_task_run_populates_vector(self):
        """Drive the canonical activation flow inline:
        create DRAFT → save status=ACTIVE → run the rebuild task →
        verify the row's search_vector is non-null."""
        if not _running_on_postgres():
            self.skipTest("search_vector requires PostgreSQL tsvector support.")

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])

        update_asset_search_vector(str(asset.pk))

        asset.refresh_from_db()
        self.assertIsNotNone(
            asset.search_vector,
            "Post-activation, the rebuild task MUST populate "
            "search_vector with a non-null tsvector.",
        )

    def test_draft_then_active_then_back_to_active_save_keeps_vector(self):
        """Sanity: re-saving an ACTIVE asset with no field changes
        still triggers the signal and refreshes the vector
        (idempotent rebuild — vector stays in sync regardless)."""
        if not _running_on_postgres():
            self.skipTest("Requires PostgreSQL.")

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])
        update_asset_search_vector(str(asset.pk))
        asset.refresh_from_db()
        first_vector = asset.search_vector
        self.assertIsNotNone(first_vector)

        # Re-save (no field changes) and re-run the task — vector
        # remains non-null.
        with self.captureOnCommitCallbacks(execute=True):
            asset.save(update_fields=["updated_at"])
        update_asset_search_vector(str(asset.pk))
        asset.refresh_from_db()
        self.assertIsNotNone(asset.search_vector)


# ---------------------------------------------------------------------------
# 226 G12 — rollback to DRAFT re-indexes instead of clearing
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestRollbackToDraftReindexes(TestCase):
    """The asset-activation saga's ``compensate_activation`` rolls a
    previously-activated asset back to DRAFT via
    ``asset.save(update_fields=['status', 'updated_at'])``. The save
    enqueues a rebuild (like every other save), so the vector is
    refreshed to the DRAFT state — the rolled-back asset remains
    findable by its owner instead of vanishing from search."""

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_rollback_active_to_draft_enqueues_rebuild(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])
        self.assertGreaterEqual(mock_enqueue.call_count, 1)
        mock_enqueue.reset_mock()

        # Simulate compensate_activation: flip status back to DRAFT
        # using the same save shape as
        # asset_activation_saga.compensate_activation.
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.DRAFT
            asset.save(update_fields=["status", "updated_at"])

        mock_enqueue.assert_called_once_with(str(asset.pk))

    def test_rollback_active_to_draft_keeps_vector_after_task_run(self):
        """After a rollback to DRAFT and a rebuild-task run, the
        vector is still non-null — the rolled-back asset stays in the
        owner-tenant's search results (Phase 226 G12)."""
        if not _running_on_postgres():
            self.skipTest("search_vector requires PostgreSQL tsvector support.")

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])
        update_asset_search_vector(str(asset.pk))
        asset.refresh_from_db()
        self.assertIsNotNone(
            asset.search_vector,
            "Pre-condition: activation must have populated the "
            "search_vector before we test the rollback path.",
        )

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.DRAFT
            asset.save(update_fields=["status", "updated_at"])
        update_asset_search_vector(str(asset.pk))

        asset.refresh_from_db()
        self.assertIsNotNone(
            asset.search_vector,
            "Phase 226 G12: rolling back to DRAFT re-indexes the asset "
            "— the vector stays populated so the owner can still find "
            "their WIP.",
        )
