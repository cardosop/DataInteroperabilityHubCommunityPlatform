"""
Phase 260.5.C — File partial unique constraint on (tenant, name)
WHERE status='ACTIVE'.

Three layers:

* **Constraint-layer tests** (pure DB, no API plumbing) — proves the
  partial unique index admits the legitimate cases (different
  tenants with same name, same name with one ACTIVE + one DELETED,
  same name with one ACTIVE + one PENDING, same name across
  ACTIVE → DELETE → re-create) AND rejects two ACTIVE rows with
  the same (tenant, name).

* **Init-upload friendly check** — `FilesBusinessRules._validate_active_filename_unique`
  rejects EARLY at init-upload time so the user gets feedback
  before bandwidth is spent on bytes. Returns 409 with code
  ``FILENAME_COLLISION`` from the API.

* **Race safety net** — concurrent complete-upload race where both
  threads passed init with PENDING rows AND simultaneously try to
  flip to ACTIVE. The partial unique index catches the second
  writer; service translates the IntegrityError to 409
  ``FILENAME_COLLISION`` (same code as the init-time rule).
"""

from __future__ import annotations

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.services import FileService
from hub.apps.files.tests.test_base import (
    FilesAPITestBase,
    _ensure_tenant_has_active_subscription,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


def _extract_error_code(body) -> str | None:
    """Phase 260.5.C.R1 GAP-D — defensive code extraction.

    ``api_error_response`` (used by init_upload's ``return
    handle_service_exception(e)`` path AND by the rename action's
    direct ``return api_error_response(...)`` calls) produces the
    FLAT envelope ``{"detail", "code", "details"}``.

    ``custom_exception_handler`` (the DRF
    ``EXCEPTION_HANDLER`` for RAISED exceptions) produces the
    NESTED envelope ``{"error": {"code", "message", ...}}``.

    Tests assert the LOGICAL error code, not which envelope it
    arrived in — refactors that switch a view from "return Response"
    to "raise APIException" should not break collision tests.
    """
    if not isinstance(body, dict):
        return None
    nested = body.get("error")
    if isinstance(nested, dict) and nested.get("code"):
        return nested.get("code")
    return body.get("code")


def _make_file(
    *,
    tenant: Tenant,
    user: User,
    name: str,
    status_value: str = FileStatus.ACTIVE,
) -> File:
    file_id = uuid.uuid4()
    return File.objects.create(
        id=file_id,
        tenant=tenant,
        name=name,
        content_type="text/csv",
        size=1024,
        status=status_value,
        scan_status=FileScanStatus.CLEAN,
        storage_path=f"{tenant.id}/{file_id}/{name}",
        created_by=user,
    )


# ---------------------------------------------------------------------------
# Layer 1 — Constraint-layer tests
# ---------------------------------------------------------------------------


class UniqueActiveFilenameConstraintTest(TestCase):
    """Direct ORM-level constraint behaviour. No API plumbing."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Filename T {uid}",
            slug=f"filename-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"filename-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_two_active_files_same_name_raise_integrity_error(self):
        # Phase 260.5.C — the partial unique index on
        # (tenant, name) WHERE status='ACTIVE' is load-bearing.
        # Direct ORM inserts that bypass FilesBusinessRules must
        # still fail at the DB level with IntegrityError.
        from django.db import IntegrityError

        _make_file(tenant=self.tenant, user=self.user, name="report.csv")
        with self.assertRaises(IntegrityError):
            _make_file(tenant=self.tenant, user=self.user, name="report.csv")

    @pytest.mark.integration
    def test_active_and_deleted_same_name_coexist(self):
        # Re-upload after delete is the load-bearing user flow that
        # the partial index admits. A user deletes "report.csv"
        # then uploads a new "report.csv" — fine.
        _make_file(
            tenant=self.tenant,
            user=self.user,
            name="report.csv",
            status_value=FileStatus.DELETED,
        )
        _make_file(tenant=self.tenant, user=self.user, name="report.csv")
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="report.csv").count(),
            2,
        )

    @pytest.mark.integration
    def test_active_and_pending_same_name_coexist(self):
        # Two parallel uploads: one is ACTIVE (existing), one is in
        # the middle of uploading (PENDING). The constraint admits
        # this; the friendly init-upload rule is what rejects PENDING
        # creation when an ACTIVE already exists.
        _make_file(tenant=self.tenant, user=self.user, name="report.csv")
        _make_file(
            tenant=self.tenant,
            user=self.user,
            name="report.csv",
            status_value=FileStatus.PENDING,
        )
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="report.csv").count(),
            2,
        )

    @pytest.mark.integration
    def test_same_name_admitted_across_tenants(self):
        # Tenant scope: two tenants can each have an ACTIVE
        # "report.csv". The partial index includes ``tenant`` in
        # the column tuple.
        _make_file(tenant=self.tenant, user=self.user, name="report.csv")
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        _make_file(tenant=other_tenant, user=other_user, name="report.csv")
        # Each tenant has its own ACTIVE row.
        self.assertEqual(
            File.objects.filter(name="report.csv", status=FileStatus.ACTIVE).count(),
            2,
        )

    @pytest.mark.integration
    def test_active_to_deleted_then_create_active_admitted(self):
        # User uploads "X", deletes it, uploads it again. The
        # constraint admits the new ACTIVE row because the prior
        # one is now DELETED (not part of the partial index).
        f1 = _make_file(tenant=self.tenant, user=self.user, name="data.csv")
        f1.status = FileStatus.DELETED
        f1.save(update_fields=["status"])
        # Now create a new ACTIVE row with the same name.
        _make_file(tenant=self.tenant, user=self.user, name="data.csv")
        self.assertEqual(
            File.objects.filter(
                tenant=self.tenant, name="data.csv", status=FileStatus.ACTIVE
            ).count(),
            1,
        )

    @pytest.mark.integration
    def test_failed_status_does_not_collide_with_active(self):
        # Phase 260.6.A — the original test asserted ACTIVE +
        # COMPLETED coexistence, but COMPLETED was retired via
        # migration ``0009_drop_completed_file_status`` (Postgres
        # CHECK constraint now forbids it). FAILED is the
        # equivalent regression guard: the partial unique index
        # is scoped to ``status='ACTIVE'`` so any non-ACTIVE
        # status (PENDING / FAILED / DELETING / DELETED) MUST
        # coexist with an ACTIVE row carrying the same name.
        _make_file(tenant=self.tenant, user=self.user, name="data.csv")
        _make_file(
            tenant=self.tenant,
            user=self.user,
            name="data.csv",
            status_value=FileStatus.FAILED,
        )
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="data.csv").count(),
            2,
        )


# ---------------------------------------------------------------------------
# Layer 2 — Friendly early check at init-upload (FilesBusinessRules)
# ---------------------------------------------------------------------------


class FileServiceFilenameCollisionEarlyCheckTest(TestCase):
    """``FileService.create_file`` rejects EARLY when an ACTIVE file
    with the same (tenant, name) already exists."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"EarlyCheck {uid}",
            slug=f"early-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"early-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = FileService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    @pytest.mark.integration
    def test_create_file_rejects_when_active_with_same_name_exists(self):
        # Seed an ACTIVE file; then try to create a new file with
        # the same name. Service raises ValidationError with
        # FILENAME_COLLISION code.
        _make_file(tenant=self.tenant, user=self.user, name="report.csv")
        with self.assertRaises(ServiceValidationError) as ctx:
            self.service.create_file(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="report.csv",
                content_type="text/csv",
                size=1024,
            )
        self.assertEqual(getattr(ctx.exception, "code", None), "FILENAME_COLLISION")
        # http_status=409 set on the exception so the view surfaces 409.
        self.assertEqual(getattr(ctx.exception, "http_status", None), 409)
        # Details payload carries the existing-file ID for debugging.
        details = getattr(ctx.exception, "details", {}) or {}
        self.assertTrue(details.get("filename_collision"))

    @pytest.mark.integration
    def test_create_file_admits_when_existing_is_deleted(self):
        # Re-upload after delete is admitted. The friendly rule
        # filters by status='ACTIVE' so DELETED rows don't block.
        _make_file(
            tenant=self.tenant,
            user=self.user,
            name="report.csv",
            status_value=FileStatus.DELETED,
        )
        # No raise — service creates the new PENDING row.
        f = self.service.create_file(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="report.csv",
            content_type="text/csv",
            size=1024,
        )
        self.assertEqual(f.name, "report.csv")
        self.assertEqual(f.status, FileStatus.PENDING)


# ---------------------------------------------------------------------------
# Layer 3 — API-layer 409 acceptance (260.5.C.2)
# ---------------------------------------------------------------------------


class FileInitUploadFilenameCollisionAPITest(FilesAPITestBase):
    """Phase 260.5.C.2 acceptance: re-upload same name as ACTIVE → 409."""

    @pytest.mark.integration
    def test_init_upload_409_when_active_with_same_name_exists(self):
        # The fixture's ``self.file`` is ACTIVE with name "test.csv".
        # POST init-upload with the SAME name → 409.
        response = self.client.post(
            "/api/v1/files/init/",
            data={
                "name": "test.csv",
                "content_type": "text/csv",
                "size": 1024,
                "upload_method": "browser",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        # Phase 260.5.C.R1 GAP-D: extract code from BOTH envelope shapes.
        # The codebase has two error envelope conventions:
        # * ``api_error_response`` returns FLAT
        #   ``{"detail", "code", "details"}`` — used by views that
        #   ``return handle_service_exception(e)`` (init_upload's path).
        # * ``custom_exception_handler`` (DEFAULT_EXCEPTION_HANDLER)
        #   returns NESTED ``{"error": {"code", "message", ...}}`` for
        #   RAISED exceptions.
        # Tests must accept either, since the same logical error
        # might surface via either path during refactors.
        code = _extract_error_code(response.data)
        self.assertEqual(
            code,
            "FILENAME_COLLISION",
            f"Expected error code=FILENAME_COLLISION; got body={response.data!r}",
        )

    @pytest.mark.integration
    def test_init_upload_201_with_unique_name(self):
        # Different name → admit (PENDING row created).
        response = self.client.post(
            "/api/v1/files/init/",
            data={
                "name": "different-name.csv",
                "content_type": "text/csv",
                "size": 1024,
                "upload_method": "browser",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Layer 4 — Concurrent-complete-upload race (the partial index safety net)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class FileCompleteUploadRaceSafetyNetTest(TransactionTestCase):
    """The init-time rule can't catch the race where two PENDING
    uploads are created with the same name AND both flip to ACTIVE
    simultaneously. The partial unique index catches the second
    writer at SAVE time; the service translates the IntegrityError
    to ``FILENAME_COLLISION`` so SDK / FE consumers handle one
    error code regardless of which gate caught the collision.

    Uses ``TransactionTestCase`` (not ``TestCase``) because Django's
    regular ``TestCase`` wraps the whole test in a single outer
    transaction invisible to other threads — threading-based
    concurrency tests need real per-connection transactions to
    exercise row-level locks against Postgres.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Race T {uid}",
            slug=f"race-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"race-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = FileService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    @pytest.mark.integration
    def test_concurrent_complete_upload_one_succeeds_one_409s(self):
        # Seed two PENDING rows with the same (tenant, name). At
        # init time these coexist (PENDING is not part of the
        # partial index). Each thread tries to flip its row to
        # ACTIVE simultaneously; ONE succeeds, the OTHER's UPDATE
        # violates the constraint → ServiceValidationError(
        # code='FILENAME_COLLISION').
        f1 = _make_file(
            tenant=self.tenant,
            user=self.user,
            name="race.csv",
            status_value=FileStatus.PENDING,
        )
        f2 = _make_file(
            tenant=self.tenant,
            user=self.user,
            name="race.csv",
            status_value=FileStatus.PENDING,
        )

        barrier = threading.Barrier(2)
        results: list[str] = []
        results_lock = threading.Lock()

        def attempt(file_id: str) -> None:
            barrier.wait()
            try:
                self.service.update_file(
                    file_id=file_id,
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                    new_status=FileStatus.ACTIVE,
                )
                with results_lock:
                    results.append("OK")
            except ServiceValidationError as exc:
                with results_lock:
                    results.append(getattr(exc, "code", "UNKNOWN"))

        t1 = threading.Thread(daemon=True, target=attempt, args=(str(f1.id),))
        t2 = threading.Thread(daemon=True, target=attempt, args=(str(f2.id),))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        self.assertEqual(len(results), 2)
        # Exactly one OK + one FILENAME_COLLISION. Without the
        # constraint, BOTH would succeed → two ACTIVE rows with the
        # same name (data integrity violation).
        self.assertEqual(
            sorted(results),
            ["FILENAME_COLLISION", "OK"],
            (
                "Concurrent complete-uploads did not produce exactly one "
                f"OK + one FILENAME_COLLISION; got {sorted(results)}. "
                "Without the partial unique index BOTH writers would "
                "succeed, leaving two ACTIVE rows with the same name."
            ),
        )

        # Exactly ONE row landed in ACTIVE (the other stayed PENDING
        # because its save was rejected before commit).
        active_rows = File.objects.filter(
            tenant=self.tenant, name="race.csv", status=FileStatus.ACTIVE
        ).count()
        self.assertEqual(
            active_rows,
            1,
            (
                "Expected exactly one ACTIVE row after concurrent "
                f"complete-upload race; found {active_rows}. The "
                "constraint MUST keep the data-integrity invariant."
            ),
        )


# ---------------------------------------------------------------------------
# Layer 5 — Rename-path collision (Phase 260.5.C.R1 GAP-A)
# ---------------------------------------------------------------------------
#
# The initial 260.5.C wiring closed the ``init_upload`` path but left
# ``POST /files/{id}/rename/`` exposed: a user renaming file B to the
# name of an existing ACTIVE file A would have hit the partial unique
# index and surfaced a generic 500 instead of the stable
# ``FILENAME_COLLISION`` / 409 contract. R1 fix adds the same two-tier
# defence (friendly rule + IntegrityError safety net) to the rename
# path; these tests assert both layers fire correctly.


class FileRenameFilenameCollisionAPITest(FilesAPITestBase):
    """Phase 260.5.C.R1 GAP-A — rename target collision."""

    @pytest.mark.integration
    def test_rename_to_existing_active_name_returns_409(self):
        # WHEN — there's a pre-existing ACTIVE file "occupied.csv" in
        # the same tenant, AND the user tries to rename ``self.file``
        # ("test.csv") to "occupied.csv".
        _make_file(tenant=self.tenant, user=self.user, name="occupied.csv")

        response = self.client.post(
            f"/api/v1/files/{self.file.id}/rename/",
            data={"name": "occupied.csv"},
            format="json",
        )

        # THEN — 409 with stable code, NOT 500 from the constraint.
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        code = _extract_error_code(response.data)
        self.assertEqual(
            code,
            "FILENAME_COLLISION",
            f"Expected error code=FILENAME_COLLISION; got body={response.data!r}",
        )

        # Row was NOT mutated (rule rejected before save).
        self.file.refresh_from_db()
        self.assertEqual(
            self.file.name,
            "test.csv",
            "Source row must be unchanged when collision rejects",
        )

    @pytest.mark.integration
    def test_rename_to_deleted_filename_admitted(self):
        # WHEN — the only file with the target name is DELETED. The
        # partial index excludes DELETED rows, so the rename SHOULD
        # admit (mirrors the create path's "re-upload after delete"
        # admission).
        _make_file(
            tenant=self.tenant,
            user=self.user,
            name="freed-name.csv",
            status_value=FileStatus.DELETED,
        )

        response = self.client.post(
            f"/api/v1/files/{self.file.id}/rename/",
            data={"name": "freed-name.csv"},
            format="json",
        )

        # THEN — 200, row updated.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"DELETED row must not block rename; got body={response.data!r}",
        )
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, "freed-name.csv")

    @pytest.mark.integration
    def test_rename_to_other_tenant_filename_admitted(self):
        # WHEN — another tenant has an ACTIVE "shared-name.csv". Our
        # tenant should be free to rename to that name (RLS scope:
        # the partial index is per-tenant).
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-r-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(other_tenant)
        other_user = User.objects.create_user(
            email=f"other-r-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        _make_file(tenant=other_tenant, user=other_user, name="shared-name.csv")

        response = self.client.post(
            f"/api/v1/files/{self.file.id}/rename/",
            data={"name": "shared-name.csv"},
            format="json",
        )

        # THEN — 200, our tenant has its own ACTIVE "shared-name.csv".
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            File.objects.filter(name="shared-name.csv", status=FileStatus.ACTIVE).count(),
            2,
            "Each tenant must independently hold an ACTIVE row with the same name",
        )


# ---------------------------------------------------------------------------
# Layer 6 — Rename concurrency safety net (Phase 260.5.C.R1 GAP-A)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class FileRenameConcurrentCollisionRaceTest(TransactionTestCase):
    """Two renamers concurrently pick the same target name. The
    ``select_for_update`` in the rename action locks the SOURCE
    rows being renamed — DIFFERENT rows for each renamer, so the
    locks do NOT serialise the rule reads. The partial unique
    index is the load-bearing gate that catches the second writer
    at SAVE time. Service translates the IntegrityError to
    ``FILENAME_COLLISION`` with ``details.race_detected = true``.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Rename Race {uid}",
            slug=f"rename-race-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"rename-race-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_concurrent_renames_to_same_target_one_succeeds_one_409s(self):
        # Seed two ACTIVE files with DIFFERENT names; both threads
        # attempt to rename to the SAME target name simultaneously.
        f1 = _make_file(tenant=self.tenant, user=self.user, name="alpha.csv")
        f2 = _make_file(tenant=self.tenant, user=self.user, name="beta.csv")

        target = "merged.csv"
        barrier = threading.Barrier(2)
        results: list[int] = []
        result_codes: list[str | None] = []
        results_lock = threading.Lock()

        def attempt(file_id: str) -> None:
            client = APIClient()
            client.force_authenticate(user=self.user)
            barrier.wait()
            response = client.post(
                f"/api/v1/files/{file_id}/rename/",
                data={"name": target},
                format="json",
            )
            with results_lock:
                results.append(response.status_code)
                result_codes.append(_extract_error_code(response.data))

        t1 = threading.Thread(daemon=True, target=attempt, args=(str(f1.id),))
        t2 = threading.Thread(daemon=True, target=attempt, args=(str(f2.id),))
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)

        # Outcomes: one OK (200) + one FILENAME_COLLISION (409).
        # Without the partial unique index BOTH renames would land
        # → two ACTIVE rows with the same name (data-integrity
        # violation).
        self.assertEqual(
            sorted(results),
            [status.HTTP_200_OK, status.HTTP_409_CONFLICT],
            (
                "Concurrent renames did not produce exactly one 200 + "
                f"one 409; got status codes {sorted(results)} with "
                f"codes {result_codes}. The partial unique index "
                "MUST be load-bearing for this race."
            ),
        )

        # Exactly ONE FILENAME_COLLISION code in the failures.
        self.assertIn(
            "FILENAME_COLLISION",
            [c for c in result_codes if c is not None],
            f"Expected FILENAME_COLLISION among result codes; got {result_codes!r}",
        )

        # Exactly ONE ACTIVE row landed with the target name.
        active = File.objects.filter(
            tenant=self.tenant, name=target, status=FileStatus.ACTIVE
        ).count()
        self.assertEqual(
            active,
            1,
            (
                f"Expected exactly one ACTIVE row with name={target!r} "
                f"after concurrent rename race; found {active}. The "
                "constraint MUST keep the data-integrity invariant."
            ),
        )
