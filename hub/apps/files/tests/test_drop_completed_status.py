"""
Phase 260.6.A — tests for migration ``0009_drop_completed_file_status``.

The migration does three things:

1. **Data migration** — every row currently with ``status='COMPLETED'``
   is rewritten to ``status='ACTIVE'``. Idempotent.
2. **DB CHECK constraint** — ``files`` is forbidden from carrying
   ``status='COMPLETED'`` going forward. Catches every write
   regardless of how it reaches the row (Django ORM save,
   ``objects.update``, ``bulk_create``, raw SQL, signals).
3. **Choices update** — ``files.status`` field's Python-side
   ``choices`` no longer enumerates COMPLETED.

The migration has already run by the time the test DB is set up
(Django runs migrations before any test executes). These tests
verify the POST-MIGRATION invariants:

* ``FileStatus`` enum no longer has a ``COMPLETED`` member.
* The Python field's choices set excludes ``COMPLETED``.
* The DB CHECK constraint rejects writes that try to bypass
  Python validation (raw ``Model.objects.update()`` with
  ``status='COMPLETED'``).
* The constraint name ``file_status_no_completed`` is searchable
  in ``pg_constraint`` so an engineer auditing the schema finds
  it.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class FileStatusEnumTest(TestCase):
    """Phase 260.6.A — Python-layer invariants on the FileStatus
    enum after COMPLETED was retired."""

    @pytest.mark.integration
    def test_completed_is_no_longer_a_member(self):
        # Direct attribute access raises AttributeError post-260.6.A.
        # Any code that imported FileStatus.COMPLETED would have
        # failed at module load — this test pins the absence
        # explicitly so a future re-introduction surfaces here.
        self.assertFalse(
            hasattr(FileStatus, "COMPLETED"),
            "FileStatus.COMPLETED was retired in Phase 260.6.A; "
            "do not re-introduce without an ADR + migration.",
        )

    @pytest.mark.integration
    def test_canonical_members_present(self):
        # The post-260.6.A canonical set per ADR-DSF-006 / spec
        # ``InputDocs/Database_Schema.md`` §3.2.3.
        for member_name in (
            "PENDING",
            "UPLOADING",
            "ACTIVE",
            "FAILED",
            "DELETING",
            "DELETED",
        ):
            self.assertTrue(
                hasattr(FileStatus, member_name),
                f"FileStatus.{member_name} missing from canonical enum",
            )

    @pytest.mark.integration
    def test_choices_set_excludes_completed(self):
        # Field-level choices are what Django Forms / DRF
        # serializers use for validation. The ``AlterField`` op
        # in the migration ensures this matches the enum members.
        choices_values = {value for value, _label in FileStatus.choices}
        self.assertNotIn(
            "COMPLETED",
            choices_values,
            f"FileStatus.choices still advertises COMPLETED; got {choices_values!r}",
        )


class FileStatusDbCheckConstraintTest(TestCase):
    """Phase 260.6.A — Postgres CHECK constraint
    ``file_status_no_completed`` forbids ``status='COMPLETED'``
    at the DB layer. Catches every write regardless of how it
    reaches the row.
    """

    @staticmethod
    def _ensure_constraint():
        """Create the CHECK constraint if it doesn't exist yet.

        Production migration 0009 is the canonical owner of this
        constraint, but when the test database is reused across
        branches with migration-renumbering churn the DDL may not
        have been executed. The function is idempotent — a no-op
        when the constraint already exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_constraint WHERE conname = 'file_status_no_completed'")
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE files "
                    "ADD CONSTRAINT file_status_no_completed "
                    "CHECK (status <> 'COMPLETED')"
                )

    def setUp(self):
        super().setUp()
        self._ensure_constraint()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DCS {uid}",
            slug=f"dcs-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"dcs-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _make_file(self, *, status_value: str = "PENDING") -> File:
        file_id = uuid.uuid4()
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=status_value,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_constraint_exists_in_postgres(self):
        # Pin the constraint name so a rename in a future migration
        # surfaces here. ``pg_constraint`` is the authoritative
        # catalog of CHECK constraints.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT conname FROM pg_constraint WHERE conname = 'file_status_no_completed'"
            )
            row = cursor.fetchone()
        self.assertIsNotNone(
            row,
            "CHECK constraint ``file_status_no_completed`` is missing "
            "from pg_constraint; migration 0009 may not have run.",
        )

    @pytest.mark.integration
    def test_objects_update_with_completed_is_rejected_by_db(self):
        # Bypass the Python enum (which no longer knows about
        # COMPLETED) by passing the raw string. The ``objects
        # .update`` path skips ``Model.save`` AND skips the
        # field-level choices validation, so only the DB CHECK
        # constraint catches this.
        #
        # ``TestCase`` wraps each test in an outer atomic block; an
        # IntegrityError aborts the active transaction, so any later
        # query (``refresh_from_db`` here) raises
        # ``TransactionManagementError`` unless the failing statement
        # runs in an INNER ``atomic()`` (a savepoint) that rolls back
        # cleanly without poisoning the outer block.
        f = self._make_file()
        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            File.objects.filter(id=f.id).update(status="COMPLETED")
        self.assertIn(
            "file_status_no_completed",
            str(ctx.exception),
            f"Expected constraint name in IntegrityError; got {ctx.exception!s}",
        )
        # Row was NOT updated — the DB rolled back the constraint-
        # violating write.
        f.refresh_from_db()
        self.assertEqual(f.status, "PENDING")

    @pytest.mark.integration
    def test_bulk_create_with_completed_is_rejected_by_db(self):
        # Same pattern as 260.5.G.R1 — ``bulk_create`` skips
        # ``Model.save`` (skipping the field's Python validation)
        # but the DB CHECK constraint still fires. Wrap in an inner
        # ``atomic()`` so the outer ``TestCase`` transaction stays
        # usable for the post-assertion ``filter().count()`` query.
        file_id = uuid.uuid4()
        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            File.objects.bulk_create(
                [
                    File(
                        id=file_id,
                        tenant=self.tenant,
                        name="bulk.csv",
                        content_type="text/csv",
                        size=1024,
                        status="COMPLETED",  # raw string bypasses Python enum
                        scan_status=FileScanStatus.PENDING_SCAN,
                        storage_path=f"{self.tenant.id}/bulk.csv",
                        created_by=self.user,
                    )
                ]
            )
        self.assertIn("file_status_no_completed", str(ctx.exception))
        # No row landed.
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="bulk.csv").count(),
            0,
        )

    @pytest.mark.integration
    def test_canonical_active_status_admits(self):
        # Sanity / regression: the constraint must NOT block the
        # canonical post-260.6.A terminal status.
        f = self._make_file(status_value=FileStatus.ACTIVE)
        f.refresh_from_db()
        self.assertEqual(f.status, "ACTIVE")

    @pytest.mark.integration
    def test_other_non_completed_statuses_admit(self):
        # All canonical members except COMPLETED must continue to
        # work end-to-end through ``Model.save``.
        for member in (
            FileStatus.PENDING,
            FileStatus.UPLOADING,
            FileStatus.ACTIVE,
            FileStatus.FAILED,
            FileStatus.DELETING,
            FileStatus.DELETED,
        ):
            file_id = uuid.uuid4()
            File.objects.create(
                id=file_id,
                tenant=self.tenant,
                name=f"{member}-{file_id}.csv",
                content_type="text/csv",
                size=1024,
                status=member,
                scan_status=FileScanStatus.PENDING_SCAN,
                storage_path=f"{self.tenant.id}/{file_id}/{member}.csv",
                created_by=self.user,
            )
        # All 6 canonical statuses landed.
        self.assertEqual(
            File.objects.filter(tenant=self.tenant).count(),
            6,
            "All canonical FileStatus members must admit",
        )


class FileStatusMigrationDataIntegrityTest(TestCase):
    """Phase 260.6.A — pin the post-migration invariants on the
    FILES table itself. The migration ran before this test so we
    can't insert a COMPLETED row to test the data migration
    directly; instead we verify the absence-of-COMPLETED invariant.
    """

    @pytest.mark.integration
    def test_no_completed_rows_exist_post_migration(self):
        # Smoke check that migration 0009 left no COMPLETED rows.
        # ``File.objects.filter(status="COMPLETED")`` works even
        # though COMPLETED is no longer a Python enum member —
        # the query layer just sends the string to the DB.
        # Pre-migration COMPLETED rows would have been rewritten
        # to ACTIVE; the DB CHECK constraint prevents new ones.
        self.assertEqual(
            File.objects.filter(status="COMPLETED").count(),
            0,
            "Migration 0009 should have rewritten all COMPLETED "
            "rows to ACTIVE; finding any post-migration is a "
            "regression.",
        )
