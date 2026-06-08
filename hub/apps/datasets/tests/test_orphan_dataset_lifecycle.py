"""
Phase 260.7.B — Orphan-dataset lifecycle E2E (closes Gap 16).

Pre-260.7.B, the chain ``forced File hard-delete → Dataset RETIRED →
GET /datasets/{id}/sample/ 410`` was covered by TWO separate test
files:

* :mod:`hub.apps.datasets.tests.test_file_hard_delete_retires_datasets`
  — pins the SIGNAL slice (``pre_delete`` on File flips Dataset to
  RETIRED + stamps ``retired_at``).
* :mod:`hub.apps.datasets.tests.test_sample_endpoint` — pins the
  ENDPOINT slice (``/sample/`` returns 410 with typed code
  ``DATASET_FILE_PURGED`` when the dataset is RETIRED OR has
  ``file_id IS NULL``).

The slice tests catch regressions WITHIN their slice but cannot catch
regressions AT THE SEAM between them. Examples a slice-test would
miss but this test catches:

* The signal sets ``status=RETIRED`` but a future migration drops
  ``retired_at`` from the model → endpoint test still passes (it
  doesn't assert ``retired_at``); signal test still passes (it asserts
  ``retired_at`` but on a fresh row — the migration would only
  surface on existing-row queries).
* The endpoint check loosens to "only ``status==RETIRED``" without
  also checking ``file_id is None`` → ``RETIRED`` rows DO 410, but
  the orphan ``file_id IS NULL`` + ``ACTIVE`` row (a real
  pre-260.6.C state) starts returning 200 with stale sample data.
* The purge management command starts using ``QuerySet.delete()``
  instead of ``model.delete()`` → ``pre_delete`` signals don't fire
  on bulk deletes, so the dataset stays ACTIVE forever AND the
  endpoint returns 200 with stale data pointing at a non-existent
  file.

This file pins the FULL chain end-to-end in ONE test method and ALSO
pins the production user-flow (soft-delete via API → grace period
elapses → ``purge_deleted_files`` cron runs → hard-delete →
signal fires → dataset RETIRED → ``/sample/`` returns 410). The
second test exists because the management command's hard-delete path
is the ACTUAL production code path; if it drifts from the
ORM-direct ``file.delete()`` (e.g., switches to bulk delete), the
ORM-direct test still passes but production breaks.
"""

from __future__ import annotations
import pytest
import pytest

import os
import unittest
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from rest_framework import status

from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.files.services import FileService
from hub.apps.tenants.request_tenant import tenant_context

pytestmark = pytest.mark.django_db(transaction=True)


def _redis_or_skip() -> None:
    """Skip the test if Redis is unreachable.

    Mirrors the pattern in
    :mod:`hub.apps.files.tests.test_purge_deleted_files` (line 31-37).
    The ``purge_deleted_files`` management command requires Redis for
    its distributed lock — if Redis is down the command calls
    ``sys.exit(2)`` BEFORE running any purge logic, which surfaces in
    pytest as a hard failure rather than a skip. This guard converts
    that failure into a skip so dev environments without Redis (e.g.
    ``pytest`` outside docker-compose.test.yml) don't see noise.
    """
    from hub.apps.api.middleware.idempotency_utils import get_redis_client

    try:
        get_redis_client().ping()
    except Exception as exc:  # pragma: no cover — environment-dependent
        raise unittest.SkipTest(f"Redis required: {exc}") from exc


class OrphanDatasetLifecycleTest(DatasetsAPITestBase):
    """260.7.B — single end-to-end test pinning the full chain.

    Inherits ``self.tenant``, ``self.user``, ``self.file``, and
    ``self.client`` (force-authenticated) from
    :class:`DatasetsAPITestBase`. setUp also seeds an S3 object body
    via :class:`S3StorageClient` — tolerated failure path if MinIO
    isn't reachable, which is fine for these tests because no path
    here reads file BYTES (only the ``sample_data_json`` cached on
    the Dataset row).
    """

    def setUp(self):
        super().setUp()
        # Pre-canned sample rows on the Dataset. Endpoint reads from
        # ``sample_data_json`` directly — the file's S3 bytes are NOT
        # touched by ``GET /sample/``. This is what makes the 410
        # contract well-defined: the dataset has data to "would have
        # served" but the platform refuses to serve it once the
        # backing File is gone (per OQ260.1.C policy: don't surface
        # sample data once provenance is broken).
        self.sample_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={
                "fields": [
                    {"name": "id", "type": "integer", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                ]
            },
            sample_data_json=self.sample_rows,
            row_count=len(self.sample_rows),
            created_by=self.user,
        )

    def _sample_url(self) -> str:
        return f"/api/v1/datasets/{self.dataset.id}/sample/"

    # ------------------------------------------------------------------
    # Primary test — direct ORM hard-delete (the path that the
    # ``purge_deleted_files`` management command ultimately calls
    # at line 242: ``file_obj.delete()``).
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_force_file_delete_retires_dataset_and_sample_returns_410(self):
        """Forced File.delete() → Dataset RETIRED → /sample/ 410.

        Single linear journey. Each ``self.assert*`` block pins one
        observable in the chain; a seam regression that breaks any
        link fails the test loud.
        """
        sample_url = self._sample_url()

        # --- 1. BASELINE: ACTIVE state, /sample/ returns 200 with
        # the stored rows. If this fails, the test is meaningless
        # (we'd be asserting a stable 410 rather than a transition).
        baseline = self.client.get(sample_url)
        self.assertEqual(
            baseline.status_code,
            status.HTTP_200_OK,
            "baseline: ACTIVE dataset must serve /sample/ with 200",
        )
        baseline_json = baseline.json()
        self.assertEqual(baseline_json["row_count"], 3)
        self.assertEqual(baseline_json["sample_size"], 3)

        # Pin the pre-transition Dataset state explicitly. A future
        # migration that backfills RETIRED into existing rows would
        # break this baseline before the deletion even happens —
        # surfacing the migration's data error here rather than
        # downstream.
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, DatasetStatus.ACTIVE)
        self.assertIsNone(self.dataset.retired_at)
        self.assertIsNotNone(self.dataset.file_id)

        # --- 2. TRANSITION: forced ORM hard-delete inside the
        # tenant context. ``pre_delete`` on File runs IN the same
        # DB transaction as ``File.delete()`` and reads
        # ``file_id=instance.pk`` BEFORE the FK is set to NULL.
        # ``tenant_context`` is required because the signal handler
        # calls ``invalidate_dataset_caches(..., tenant_id_str)``
        # which expects tenant scope.
        file_pk = self.file.pk
        with tenant_context(str(self.tenant.id)):
            self.file.delete()

        # --- 3. INTERMEDIATE STATE: signal-driven side-effects on
        # the Dataset row.
        self.dataset.refresh_from_db()
        self.assertEqual(
            self.dataset.status,
            DatasetStatus.RETIRED,
            "signal must mark linked ACTIVE datasets RETIRED on File.delete()",
        )
        self.assertIsNotNone(
            self.dataset.retired_at,
            "RETIRED transition must stamp retired_at (audit-trail invariant)",
        )
        # The file FK is NULL after the transaction commits because
        # the File model declares ``on_delete=SET_NULL`` on the
        # Dataset.file relation. The signal saw file_id=instance.pk
        # BEFORE the SET_NULL ran — that's the ordering invariant.
        self.assertIsNone(
            self.dataset.file,
            "File FK must be NULL after delete (on_delete=SET_NULL)",
        )
        # File row physically gone from the DB — confirms we exercised
        # hard-delete (the soft-delete path leaves the row with
        # status=DELETING).
        self.assertFalse(
            File.objects.filter(pk=file_pk).exists(),
            "force-delete must HARD-delete the File row, not soft-delete",
        )

        # --- 4. FINAL API CONTRACT: /sample/ returns 410 GONE with
        # the typed error code ``DATASET_FILE_PURGED``. SDK consumers
        # branch on this typed code (per the error-codes.md contract)
        # rather than parsing the message string.
        post_delete = self.client.get(sample_url)
        self.assertEqual(
            post_delete.status_code,
            status.HTTP_410_GONE,
            "post-purge: /sample/ MUST return 410 (provenance broken)",
        )
        self.assertEqual(
            post_delete.json().get("error_code"),
            "DATASET_FILE_PURGED",
            "410 must carry typed error code so SDK consumers branch precisely",
        )

    # ------------------------------------------------------------------
    # Secondary test — production user-flow through the management
    # command. Pins that the full chain works when driven by the
    # cron path (DELETE API → grace → purge command), not just by
    # a direct ORM call.
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_production_purge_flow_retires_dataset_and_sample_returns_410(self):
        """Production user-flow: API soft-delete → grace → purge cron → 410.

        Pins that the management command's hard-delete path doesn't
        drift from the ORM-direct path tested above. Concretely:

        * If ``purge_deleted_files`` switched from ``model.delete()``
          to ``QuerySet.delete()``, ``pre_delete`` signals would NOT
          fire on bulk deletes and the dataset would stay ACTIVE
          forever.
        * If the command bypassed ``tenant_context``, the signal
          handler's cache invalidation would silently fail (caught
          by an exception logger) but the dataset retire still works
          — that's a degradation we'd want a future test to pin
          separately, but the cache hit/miss does not affect the
          410 contract.
        """
        sample_url = self._sample_url()

        # --- 1. SOFT-DELETE via the FileService entry point that
        # ``DELETE /api/v1/files/{id}/`` ultimately calls. Grace
        # window starts now.
        service = FileService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        service.delete_file(
            file_id=str(self.file.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.file.refresh_from_db()
        self.assertEqual(
            self.file.status,
            FileStatus.DELETING,
            "soft-delete: File.status must transition to DELETING",
        )
        self.assertIsNotNone(
            self.file.deleted_at,
            "soft-delete: File.deleted_at must be stamped",
        )

        # WITHIN GRACE: dataset remains ACTIVE; /sample/ still 200.
        # This pins that we DON'T retire prematurely on soft-delete.
        # If a regression starts retiring on soft-delete, the user
        # loses access to their data during the grace window — a
        # silent UX regression that nothing else would catch.
        within_grace = self.client.get(sample_url)
        self.assertEqual(
            within_grace.status_code,
            status.HTTP_200_OK,
            "during grace window: /sample/ MUST still serve 200 (soft-delete is reversible)",
        )
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, DatasetStatus.ACTIVE)

        # --- 2. TIME-TRAVEL: backdate ``deleted_at`` past the
        # tenant's grace period so the file becomes purge-eligible.
        # We cannot ``time.sleep(grace_days)``; backdating the
        # ``deleted_at`` column directly mirrors how production
        # would look on day ``grace_days+1``.
        grace_days = int(
            getattr(self.tenant, "file_soft_delete_grace_days", 30) or 30
        )
        backdated = timezone.now() - timedelta(days=grace_days + 1)
        File.objects.filter(pk=self.file.pk).update(deleted_at=backdated)

        # --- 3. RUN THE PURGE COMMAND (single-tenant filter so we
        # don't accidentally touch other tenants' files).
        #
        # R1 audit GAP-A: the command requires Redis for its
        # distributed lock (``purge_deleted_files.py:97-101`` calls
        # ``sys.exit(2)`` if ``get_redis_client()`` raises). Skip
        # the test rather than hard-fail when Redis is unreachable
        # (e.g. running ``pytest`` outside docker-compose.test.yml).
        _redis_or_skip()
        # R1 audit GAP-B: ``FILE_PURGE_DRY_RUN_REQUIRED`` is a
        # production safety env var — if it's set, the command
        # silently flips ``dry_run=True`` and the file is NOT
        # purged, breaking the assertion below. Pop the env var
        # for the duration of the call and pass ``--no-dry-run``
        # explicitly so the test is deterministic regardless of
        # the runner's environment. Restore the env var after the
        # call so we don't leak state to other tests in the same
        # worker. Mirrors the pattern in
        # ``test_purge_deleted_files.py::test_hard_purge_...``
        # (line 115).
        prev_env = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev_env is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev_env
        # The command instantiates an ``S3StorageClient`` and
        # calls ``storage.delete_file(storage_path)`` — failure
        # there is tolerated by the command (logged via
        # ``purge_deleted_files_s3_delete_failed``, not raised),
        # so the test passes even when MinIO isn't reachable.
        # Command logs ``purged N file(s)``; we expect exactly 1
        # in this test's tenant scope.
        out_text = out.getvalue()
        self.assertIn(
            "purged 1 file",
            out_text,
            f"expected 1 file purged, command output: {out_text!r}",
        )

        # --- 4. POST-PURGE STATE: file gone, dataset RETIRED.
        self.assertFalse(
            File.objects.filter(pk=self.file.pk).exists(),
            "post-purge: File row must be physically gone",
        )
        self.dataset.refresh_from_db()
        self.assertEqual(
            self.dataset.status,
            DatasetStatus.RETIRED,
            "post-purge: Dataset must be RETIRED via pre_delete signal",
        )
        self.assertIsNotNone(self.dataset.retired_at)
        self.assertIsNone(self.dataset.file)

        # --- 5. /sample/ 410 with typed code (same end-state as the
        # primary test, reached via a different production path).
        after_purge = self.client.get(sample_url)
        self.assertEqual(after_purge.status_code, status.HTTP_410_GONE)
        self.assertEqual(
            after_purge.json().get("error_code"),
            "DATASET_FILE_PURGED",
        )

    # ------------------------------------------------------------------
    # Coverage-gap pin — the OR branch of the endpoint's 410 check
    # ``file_id is None OR status == RETIRED``. The two tests above
    # both reach a state where BOTH conditions hold (signal sets
    # RETIRED + SET_NULL nulls the FK). A test where ONLY ONE
    # condition holds catches a regression that loosens the OR to
    # AND. The orphan-row case (FK NULL, status ACTIVE) is the
    # legacy-data shape this branch was added for.
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_orphan_row_file_id_null_active_status_returns_410(self):
        """Orphan row (file_id NULL, status ACTIVE) → /sample/ 410.

        This shape exists in pre-260.1.C data: rows where the File
        was purged via a path that didn't fire the pre_delete signal
        (e.g., a manual ``DELETE FROM files_file WHERE id=...`` SQL
        run, or a pre-260.1.C migration that ran SET_NULL without
        the retire-on-purge handler). Any such row MUST 410 — we
        cannot serve sample data when provenance is broken.
        """
        sample_url = self._sample_url()

        # Detach the file FK without going through the signal.
        # ``QuerySet.update`` bypasses signals — this exactly mirrors
        # the pre-260.1.C orphan-row shape.
        Dataset.objects.filter(pk=self.dataset.pk).update(
            file=None,
            updated_at=timezone.now(),
        )

        self.dataset.refresh_from_db()
        self.assertIsNone(self.dataset.file_id)
        self.assertEqual(
            self.dataset.status,
            DatasetStatus.ACTIVE,
            "orphan-row test must keep status=ACTIVE so we exercise the OR branch",
        )

        response = self.client.get(sample_url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.json().get("error_code"), "DATASET_FILE_PURGED")
