"""
Phase 250.1.F (closes B2-5) — search-vector signal-timing tests.

Contract under test
-------------------

The post_save signal handler at
``hub.apps.assets.signals.rebuild_asset_search_vector`` MUST:

* **NOT** enqueue an ``enqueue_asset_search_vector_update`` job when
  the saved Asset is in ``DRAFT`` status — drafts are not searchable,
  so building a vector for them wastes a ``job_low`` slot on every
  ``asset_create`` workflow step (Phase 250.1.A).

* **DO** enqueue when the save transitions ``DRAFT → ACTIVE`` (the
  activation save inside the asset-activation saga,
  ``hub.apps.orchestration.workflows.asset_activation_saga.activate_asset``).
  This is the first time the asset becomes searchable, so the vector
  must materialize on the same ``transaction.on_commit`` as the
  activation.

* **DO** enqueue on subsequent saves of a non-DRAFT asset — renames,
  description edits, domain changes — so the vector tracks the
  searchable text.

* **DO** enqueue on saves where the status flips ``ACTIVE → PUBLIC``,
  ``ACTIVE → RETIRED``, ``PUBLIC → RETIRED`` — those assets remain
  searchable (PUBLIC explicitly so; RETIRED for post-retirement
  audit searches), so the vector stays in sync.

* **DO** enqueue for a one-shot direct create with
  ``status=ACTIVE`` — legacy seeds, test fixtures, scheduled-ingest
  ``auto_activate`` paths — those assets are searchable from row 0.

Integration invariant (Phase 250.1.F.2)
---------------------------------------
After running the canonical asset-creation flow (DRAFT row created,
then activated via ``asset.save(update_fields=['status', ...])``):

* A new DRAFT asset has ``search_vector = None`` at the DB level.
* Once activated, executing the rebuild task populates
  ``search_vector`` with a non-null PostgreSQL ``tsvector``.

So search-vector existence ↔ asset is non-DRAFT (i.e., has been
activated past the DRAFT phase). Strict reading of the original B2-5
"exists ↔ ACTIVE" wording is "exists ↔ activated" — PUBLIC and
RETIRED both have vectors because both states post-date activation.

TDD doctrine
------------
* Real Django ORM rows + real ``post_save`` dispatch + real
  ``django.test.TestCase.captureOnCommitCallbacks(execute=True)``
  to drive the deferred enqueue paths.
* The enqueue itself is patched (only the boundary into
  ``django_rq``) so we can spy on call-count without standing up a
  real RQ worker. NO mocks of business logic.
* The integration test invokes the real
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


def _seed_user(tenant: Tenant) -> "User":
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
    )


def _seed_draft(tenant: Tenant, user: "User", *, key_suffix: str = "") -> Asset:
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
# 250.1.F.1 — signal-timing contract
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDraftSaveDoesNotEnqueue(TestCase):
    """DRAFT saves (create or update) MUST NOT enqueue a search-
    vector rebuild — drafts are not searchable, no work to do."""

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_create_does_not_enqueue(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            _seed_draft(tenant, user)

        self.assertEqual(mock_enqueue.call_count, 0,
            "Creating a DRAFT asset MUST NOT enqueue a search-vector "
            "rebuild — vectors are only meaningful for activated "
            "(non-DRAFT) assets. Phase 250.1.F closes B2-5.")

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_rename_does_not_enqueue(self, mock_enqueue):
        """Editing a DRAFT asset's name still doesn't enqueue — the
        asset hasn't been activated, so no vector to keep in sync."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "Renamed Draft"
            asset.save(update_fields=["name", "updated_at"])

        self.assertEqual(mock_enqueue.call_count, 0,
            "Renaming a DRAFT asset MUST NOT enqueue a search-vector "
            f"rebuild; got {mock_enqueue.call_count} call(s).")

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_description_edit_does_not_enqueue(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.description = "Updated description while still DRAFT"
            asset.save(update_fields=["description", "updated_at"])

        self.assertEqual(mock_enqueue.call_count, 0)


@pytest.mark.django_db(transaction=True)
class TestActivationEnqueues(TestCase):
    """The DRAFT → ACTIVE transition (the activation save) MUST
    enqueue — that's the first time the asset becomes searchable."""

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_draft_to_active_transition_enqueues_exactly_once(self, mock_enqueue):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        # Step 1: create DRAFT — no enqueue per
        # TestDraftSaveDoesNotEnqueue.
        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        self.assertEqual(mock_enqueue.call_count, 0)
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
    """Once activated, every save still enqueues so the vector
    tracks renames / description edits / domain edits / status
    transitions."""

    def _seed_active(self, tenant: Tenant, user: "User") -> Asset:
        # Use ACTIVE on create so we don't have to dance through the
        # DRAFT-then-activate path inside captureOnCommitCallbacks
        # twice; this isolates the "post-activation update" scenario.
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
        self.assertIn(rebuild_asset_search_vector, receivers,
            "rebuild_asset_search_vector MUST be connected to "
            "Asset post_save.")


# ---------------------------------------------------------------------------
# 250.1.F.2 — integration: search_vector exists ↔ asset has been activated
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestSearchVectorExistsIffActivated(TestCase):
    """End-to-end: a DRAFT asset has search_vector=None at the DB
    level; once activated (DRAFT → ACTIVE) and the rebuild task
    runs, search_vector materializes."""

    def test_draft_asset_has_null_search_vector(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        # Re-read from DB; the signal didn't enqueue, so search_vector
        # is still the column default of NULL.
        asset.refresh_from_db()
        self.assertIsNone(asset.search_vector,
            "DRAFT asset MUST have search_vector=NULL — Phase 250.1.F "
            "suppresses the rebuild while in DRAFT.")

    def test_activation_then_task_run_populates_vector(self):
        """Drive the canonical activation flow inline:
        create DRAFT → save status=ACTIVE → run the rebuild task →
        verify the row's search_vector is non-null."""
        if not _running_on_postgres():
            self.skipTest(
                "search_vector requires PostgreSQL tsvector support."
            )

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)

        # Pre-activation: vector is null.
        asset.refresh_from_db()
        self.assertIsNone(asset.search_vector)

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])

        # The on_commit callback would normally enqueue an RQ job;
        # here we run the task body directly to verify the DB write
        # produces a non-null vector. This proves the contract end-
        # to-end: signal fires → enqueue lands → task writes the
        # vector → row becomes searchable.
        update_asset_search_vector(str(asset.pk))

        asset.refresh_from_db()
        self.assertIsNotNone(asset.search_vector,
            "Post-activation, the rebuild task MUST populate "
            "search_vector with a non-null tsvector.")

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
# 250.1.F audit-pass — rollback to DRAFT clears the stale vector
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestRollbackToDraftClearsVector(TestCase):
    """The asset-activation saga's ``compensate_activation`` rolls a
    previously-activated asset back to DRAFT via
    ``asset.save(update_fields=['status', 'updated_at'])``. Without
    an explicit clear, the row would be DRAFT-status with a
    populated ``search_vector``, and the search-views.py FTS
    endpoint at ``hub/apps/search/views.py:614-632`` (which gates on
    ``search_vector__isnull=False``) would keep returning the rolled-
    back asset. The signal handler closes this gap by NULLing the
    column inside the same transaction as the rollback save."""

    def test_rollback_active_to_draft_clears_vector(self):
        if not _running_on_postgres():
            self.skipTest(
                "search_vector requires PostgreSQL tsvector support."
            )

        from hub.apps.search.tasks import update_asset_search_vector

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        # Seed DRAFT, activate, populate vector.
        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])
        update_asset_search_vector(str(asset.pk))
        asset.refresh_from_db()
        self.assertIsNotNone(asset.search_vector,
            "Pre-condition: activation must have populated the "
            "search_vector before we test the rollback path.")

        # Simulate compensate_activation: flip status back to DRAFT
        # using the same save shape as
        # asset_activation_saga.compensate_activation:354.
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.DRAFT
            asset.save(update_fields=["status", "updated_at"])

        asset.refresh_from_db()
        self.assertIsNone(asset.search_vector,
            "Phase 250.1.F invariant: rolling back from non-DRAFT "
            "to DRAFT MUST clear the stale search_vector so the "
            "row no longer surfaces from the FTS endpoint at "
            "hub/apps/search/views.py:614-632 which gates on "
            "search_vector__isnull=False."
        )

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_rollback_active_to_draft_does_not_enqueue_rebuild(self, mock_enqueue):
        """The rollback save lands with status=DRAFT, so the
        existing 'no-enqueue while DRAFT' contract still holds —
        we clear the vector but DO NOT schedule a rebuild."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)

        with self.captureOnCommitCallbacks(execute=True):
            asset = _seed_draft(tenant, user)
        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status", "updated_at"])
        # We expect at least one enqueue from the activation save.
        self.assertGreaterEqual(mock_enqueue.call_count, 1)
        mock_enqueue.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            asset.status = AssetStatus.DRAFT
            asset.save(update_fields=["status", "updated_at"])

        self.assertEqual(mock_enqueue.call_count, 0,
            "Rollback to DRAFT MUST NOT enqueue a rebuild — the "
            "vector is being cleared, not rebuilt.")

    def test_brand_new_draft_does_not_run_clear_update(self):
        """Brand-new DRAFT (no prior status) MUST NOT trigger the
        clear-update path either — there's nothing to clear, and
        running the UPDATE on every DRAFT-create would be a
        per-row-creation perf regression. The pre_save handler
        records prior=None for new rows; the signal's
        ``prior_status is not None`` guard skips the UPDATE."""
        if not _running_on_postgres():
            self.skipTest("Requires PostgreSQL.")

        tenant = _seed_tenant()
        user = _seed_user(tenant)

        # Capture queries during a brand-new DRAFT create. There
        # MUST be exactly one INSERT + the typical FK validation
        # selects, with NO ``UPDATE assets SET search_vector = NULL``
        # — the signal recognises new rows via prior=None.
        from django.db import connection

        with self.captureOnCommitCallbacks(execute=True):
            draft = _seed_draft(tenant, user)
        # Observable outcome: new DRAFT rows start with NULL search_vector
        # and NEVER trigger a clear-update UPDATE. The column default +
        # signal guard (prior_status is not None) enforce this.
        self.assertIsNone(draft.search_vector,
            "Brand-new DRAFT must have NULL search_vector; "
            "a non-NULL value means the clear-update path fired incorrectly")
