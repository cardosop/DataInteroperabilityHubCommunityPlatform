"""
Phase 260.4.C — File rename endpoint tests.

Verifies the contract for ``POST /files/{id}/rename/``:

* Happy path: 200 with serialised file payload reflecting the new name;
  audit row ``FILE_RENAMED`` lands with previous + new name + storage_path.
* Storage path immutability: rename does NOT change ``File.storage_path``
  (the load-bearing physical-key invariant — the audit row asserts this).
* Validation: invalid filenames (control chars, traversal, empty) → 400.
* No-op (same name): 200 returned, BUT no audit emission (avoid noise).
* Cross-tenant: 404 with no audit emission (existence non-disclosure).
* Unknown id: 404.
* Malformed UUID: 400.
* Permissions: unauthenticated → 401.

Real DB rows; only the file's storage object is irrelevant (not touched
on rename).  No mocks.
"""

import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.audit import event_types as audit_event_types
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import (
    FilesAPITestBase,
    _ensure_tenant_has_active_subscription,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


def _rename_url(file_id) -> str:
    return f"/api/v1/files/{file_id}/rename/"


class FileRenameEndpointTest(FilesAPITestBase):
    """Happy-path + state contracts for the rename action."""

    @pytest.mark.integration
    def test_rename_succeeds_returns_serialised_file(self):
        # WHEN — rename with a valid new display name.
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "renamed.csv"},
            format="json",
        )

        # THEN — 200 with the canonical serialised file payload.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "renamed.csv")
        # ID + storage_path on the response payload reflect the same
        # row (the response includes ``id`` so the FE can refresh its
        # detail cache without a re-fetch).
        self.assertEqual(str(response.data["id"]), str(self.file.id))

        # Row was actually updated.
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, "renamed.csv")

    @pytest.mark.integration
    def test_rename_storage_path_is_immutable(self):
        # WHEN — rename the display name.
        original_storage_path = self.file.storage_path
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "renamed-display.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # THEN — the physical storage key is UNCHANGED. The S3/MinIO
        # object lives at the path the upload created; rename is a
        # display-only operation.
        self.file.refresh_from_db()
        self.assertEqual(self.file.storage_path, original_storage_path)

    @pytest.mark.integration
    def test_rename_emits_FILE_RENAMED_audit_with_previous_and_new_name(self):
        # WHEN — rename a file.
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "audited-rename.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # THEN — exactly one FILE_RENAMED row scoped to (tenant, file).
        events = AuditEvent.objects.filter(
            tenant_id=self.tenant.id,
            resource_type="FILE",
            resource_id=self.file.id,
            action=audit_event_types.FILE_RENAMED,
        )
        self.assertEqual(events.count(), 1)
        ev = events.first()
        self.assertEqual(ev.actor_user_id, self.user.id)
        details = ev.details_json or {}
        # Audit row carries the rename forensics: previous + new name
        # AND the storage path so future audit consumers can prove the
        # storage key did NOT change on rename (the load-bearing
        # immutability invariant).
        self.assertEqual(details.get("previous_name"), "test.csv")
        self.assertEqual(details.get("new_name"), "audited-rename.csv")
        self.assertEqual(details.get("file_id"), str(self.file.id))
        self.assertIn("storage_path", details)
        self.assertEqual(details["storage_path"], self.file.storage_path)

    @pytest.mark.integration
    def test_rename_to_same_name_is_noop_no_audit(self):
        # WHEN — rename to the EXACT current name.
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": self.file.name},
            format="json",
        )

        # THEN — 200 (idempotent) but NO audit row (avoid noise from
        # accidental re-saves of unchanged display names).
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            AuditEvent.objects.filter(
                resource_id=self.file.id,
                action=audit_event_types.FILE_RENAMED,
            ).exists()
        )


class FileRenameValidationTest(FilesAPITestBase):
    """Filename validation gates."""

    @pytest.mark.integration
    def test_rename_empty_name_returns_400(self):
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_rename_whitespace_only_name_returns_400(self):
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_rename_path_traversal_returns_400(self):
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "../../etc/passwd"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_rename_control_characters_returns_400(self):
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "bad\x00name.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_rename_missing_name_returns_400(self):
        response = self.client.post(
            _rename_url(self.file.id),
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_rename_validation_failure_does_not_emit_audit(self):
        # Ensure the audit log isn't seeded with rename rows from
        # rejected payloads — only successful display-name changes
        # produce audit rows.
        self.client.post(
            _rename_url(self.file.id),
            data={"name": ""},
            format="json",
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                resource_id=self.file.id,
                action=audit_event_types.FILE_RENAMED,
            ).exists()
        )


class FileRenameTenantScopeTest(FilesAPITestBase):
    """Tenant scoping + missing-row handling."""

    @pytest.mark.integration
    def test_rename_cross_tenant_returns_404(self):
        # GIVEN — a file owned by a DIFFERENT tenant.
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
        other_file_id = uuid.uuid4()
        other_file = File.objects.create(
            id=other_file_id,
            tenant=other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=512,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{other_tenant.id}/{other_file_id}/other.csv",
            created_by=other_user,
        )

        # WHEN — self.user (tenant-A) tries to rename the tenant-B file.
        response = self.client.post(
            _rename_url(other_file.id),
            data={"name": "stolen.csv"},
            format="json",
        )

        # THEN — 404 with NO audit emission (existence non-disclosure;
        # rename is a write-class action so the cross-tenant
        # entitlement fallback does NOT apply).
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            AuditEvent.objects.filter(
                resource_id=other_file.id,
                action=audit_event_types.FILE_RENAMED,
            ).exists()
        )
        # Other-tenant row was NOT modified.
        other_file.refresh_from_db()
        self.assertEqual(other_file.name, "other.csv")

    @pytest.mark.integration
    def test_rename_unknown_id_returns_404(self):
        response = self.client.post(
            _rename_url(uuid.uuid4()),
            data={"name": "ghost.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @pytest.mark.integration
    def test_rename_malformed_uuid_returns_400(self):
        response = self.client.post(
            _rename_url("not-a-uuid"),
            data={"name": "bad.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FileRenamePermissionsTest(FilesAPITestBase):
    """Authentication gate."""

    @pytest.mark.integration
    def test_rename_unauthenticated_returns_401(self):
        anon_client = APIClient()
        response = anon_client.post(
            _rename_url(self.file.id),
            data={"name": "anon.csv"},
            format="json",
        )
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class FileRenamedAuditConstantTest(FilesAPITestBase):
    """Drift guard — the FILE_RENAMED constant must self-describe."""

    @pytest.mark.integration
    def test_FILE_RENAMED_self_describes(self):
        self.assertEqual(audit_event_types.FILE_RENAMED, "FILE_RENAMED")
        self.assertIn("FILE_RENAMED", audit_event_types.__all__)


class FileRenameBoundaryTest(FilesAPITestBase):
    """R1 audit GAP-C — character-count boundary cases."""

    @pytest.mark.integration
    def test_rename_to_255_chars_succeeds(self):
        # ``CharField(max_length=255)`` accepts exactly 255 chars; the
        # boundary case is the most common off-by-one trap (validators
        # often check ``> 255`` vs ``>= 255``).
        new_name = "a" * 255
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": new_name},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, new_name)

    @pytest.mark.integration
    def test_rename_to_256_chars_returns_400(self):
        # 256 chars exceeds the serializer cap; expect a 400 with
        # NO audit emission and NO row mutation.
        original_name = self.file.name
        response = self.client.post(
            _rename_url(self.file.id),
            data={"name": "a" * 256},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, original_name)
        self.assertFalse(
            AuditEvent.objects.filter(
                resource_id=self.file.id,
                action=audit_event_types.FILE_RENAMED,
            ).exists()
        )


class FileRenameDefenseInDepthTest(FilesAPITestBase):
    """R1 audit GAP-E — extra payload fields must NOT smuggle writes
    through the serializer surface (``storage_path`` is the
    load-bearing field that the FE / SDK could try to mutate to
    masquerade as a "move" operation)."""

    @pytest.mark.integration
    def test_rename_ignores_storage_path_in_payload(self):
        # GIVEN — original storage path captured.
        original_storage_path = self.file.storage_path
        injected_path = f"attacker/{uuid.uuid4().hex}/payload.csv"
        self.assertNotEqual(original_storage_path, injected_path)

        # WHEN — POST a rename payload that ALSO contains a
        # ``storage_path`` key (which the serializer doesn't declare;
        # DRF silently drops it but the contract test pins down the
        # behaviour so a future serializer field addition can't
        # quietly start accepting it without the test failing).
        response = self.client.post(
            _rename_url(self.file.id),
            data={
                "name": "renamed-defense-in-depth.csv",
                "storage_path": injected_path,
            },
            format="json",
        )

        # THEN — the rename happens (200) but the storage path is
        # UNCHANGED. The audit row records the original storage_path
        # so the immutability invariant survives the defense-in-depth
        # path.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.file.refresh_from_db()
        self.assertEqual(self.file.name, "renamed-defense-in-depth.csv")
        self.assertEqual(self.file.storage_path, original_storage_path)

        ev = AuditEvent.objects.filter(
            resource_id=self.file.id,
            action=audit_event_types.FILE_RENAMED,
        ).first()
        assert ev is not None  # narrows type for downstream attribute access
        self.assertEqual(ev.details_json.get("storage_path"), original_storage_path)


@pytest.mark.django_db(transaction=True)
class FileRenameConcurrentLockTest(TransactionTestCase):
    """R1 audit GAP-D — match the test-honesty pattern from
    ``test_retire_select_for_update_blocks_concurrent_writers`` (260.4.A.R1
    GAP-D).

    Without the ``select_for_update`` lock from the R1 fix, two
    concurrent renamers would both read the same ``previous_name``,
    write the row sequentially, and emit TWO audit rows with the SAME
    ``previous_name`` — even though the second writer's actual
    pre-state was the first writer's new name. This test releases two
    real ``APIClient`` POSTs simultaneously via a Python
    ``threading.Barrier`` and asserts the two audit rows form a clean
    chain (``A → B`` and ``B → C`` rather than ``A → B`` and ``A → C``).

    Uses :class:`TransactionTestCase` (NOT the file-suite default
    ``TestCase``) because Django ``TestCase`` wraps the whole test in
    a single outer transaction that other threads can never see —
    threading-based concurrency tests need real per-connection
    transactions to exercise row-level locks against Postgres.
    """

    def setUp(self):
        super().setUp()
        self.tenant = Tenant.objects.create(
            name=f"Concurrent T {uuid.uuid4().hex[:8]}",
            slug=f"concurrent-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        _ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"concurrent-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_concurrent_rename_writers_serialize_via_select_for_update(self):
        import threading

        # Two independent APIClients authenticated as the same user
        # so the request stack is the only thing being tested (auth
        # is identical across threads).
        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        barrier = threading.Barrier(2)
        results: list[int] = []
        results_lock = threading.Lock()

        def _do_rename(client, new_name: str) -> None:
            barrier.wait()
            response = client.post(
                _rename_url(self.file.id),
                data={"name": new_name},
                format="json",
            )
            with results_lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=_do_rename, args=(client_a, "concurrent-B.csv"))
        t2 = threading.Thread(target=_do_rename, args=(client_b, "concurrent-C.csv"))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        # Both renames succeed (200) — neither thread sees an error
        # because rename is idempotent under serialisation.
        self.assertEqual(len(results), 2)
        for code in results:
            self.assertEqual(code, 200, f"Unexpected non-200 from concurrent rename: {code}")

        # The audit log MUST show a clean chain: each rename's
        # ``previous_name`` must equal the prior write's ``new_name``
        # (or the original name for the first write). Without the
        # ``select_for_update`` lock both writers would emit
        # ``previous_name="test.csv"`` and the chain would break.
        self.file.refresh_from_db()
        events = list(
            AuditEvent.objects.filter(
                resource_id=self.file.id,
                action=audit_event_types.FILE_RENAMED,
            ).order_by("timestamp")
        )
        self.assertEqual(len(events), 2)

        prev_names = {e.details_json.get("previous_name") for e in events}
        new_names = {e.details_json.get("new_name") for e in events}
        # The set of new_names must equal the two attempted names.
        self.assertEqual(new_names, {"concurrent-B.csv", "concurrent-C.csv"})
        # The two previous_names form a chain: one is "test.csv"
        # (the original) and the other is whichever new name landed
        # first. They must NOT both be the original.
        self.assertIn("test.csv", prev_names)
        self.assertEqual(
            len(prev_names),
            2,
            (
                "Concurrent renamers emitted audit rows with the SAME previous_name "
                "— select_for_update lock is missing or ineffective. "
                f"prev_names={prev_names}"
            ),
        )
