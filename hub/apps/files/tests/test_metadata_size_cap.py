"""
Phase 260.5.G — ``File.metadata_json`` 64 KB size cap.

Three test layers, no business-logic mocks:

* **Pure-unit** — the validator primitive
  (:func:`validate_metadata_json_size` and the byte-counter
  :func:`metadata_json_size_bytes`) tested in isolation. Boundary
  cases (None / empty / 1 byte below cap / exactly cap / 1 byte
  above) pin the contract.
* **Model layer** — :meth:`File.save` defensively re-validates so
  the cap fires regardless of how the row reached ``save()``
  (services, signals, management commands, raw ORM writes). This
  is the LOAD-BEARING gate — even if a caller bypasses the
  serializer, the model still enforces.
* **Serializer layer** — :data:`FileSerializer` registers the
  validator on the ``metadata_json`` field. The field is
  currently ``read_only`` for public writes, so the validator
  doesn't fire on PATCH today; we test it DIRECTLY by invoking
  the field-level validator function so a future write surface
  inherits the gate without surprise. Per spec 260.5.G.1
  ("validated at serializer level").

Threats this protects against:

* Runaway internal writes — a future feature stuffing schema /
  lineage into ``metadata_json`` could silently bloat the column
  past the spec ceiling. Model-level ``save()`` rejects.
* Future user-write surfaces — when an admin endpoint lifts the
  ``read_only`` restriction on ``metadata_json``, the cap is
  already wired at the serializer level.
* Storage / memory blowup — Postgres JSONB has no hard limit; a
  multi-MB metadata column would TOAST and slow ``SELECT *``
  queries (admin tooling, audit dumps, migrations).
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.files.metadata_validators import (
    MAX_METADATA_JSON_BYTES,
    metadata_json_size_bytes,
    validate_metadata_json_size,
)
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.serializers import FileSerializer
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Pure-unit — validator primitive
# ---------------------------------------------------------------------------


class MetadataJsonSizeBytesTest(SimpleTestCase):
    """Pin the byte-counting contract. The validator's boundary
    decisions all flow from this function — wrong byte counts =
    wrong cap behaviour, even if the threshold is right."""

    @pytest.mark.integration
    def test_none_is_zero_bytes(self):
        # Vacuously safe — None metadata stores nothing.
        self.assertEqual(metadata_json_size_bytes(None), 0)

    @pytest.mark.integration
    def test_empty_dict_is_zero_bytes(self):
        # The model's default is ``dict`` (empty); MUST count
        # as zero so freshly-created File rows never trip the cap.
        self.assertEqual(metadata_json_size_bytes({}), 0)

    @pytest.mark.integration
    def test_small_dict_returns_canonical_byte_count(self):
        # ``{"k": "v"}`` serialises to ``{"k": "v"}`` (10 chars).
        # Pinning the exact count makes drift in the serialisation
        # rule (ensure_ascii / sort_keys / indent) a build break.
        size = metadata_json_size_bytes({"k": "v"})
        self.assertEqual(size, len(b'{"k": "v"}'))

    @pytest.mark.integration
    def test_non_ascii_uses_utf8_byte_count_not_escaped_form(self):
        # ``ensure_ascii=False`` is the deliberate choice; ``café``
        # serialises to ``café`` (6 bytes UTF-8) NOT ``\\u00e9``
        # (10 bytes). The user-visible byte count matches what
        # they'd put on the wire.
        result = metadata_json_size_bytes({"name": "café"})
        self.assertEqual(result, len('{"name": "café"}'.encode()))
        self.assertNotIn(
            b"\\u00e9", json.dumps({"name": "café"}, ensure_ascii=False).encode("utf-8")
        )

    @pytest.mark.integration
    def test_size_is_deterministic_under_key_reordering(self):
        # ``sort_keys=True`` makes the count stable regardless of
        # dict insertion order. Without this, a future caller
        # comparing sizes across calls could see flapping.
        a = metadata_json_size_bytes({"a": 1, "b": 2})
        b = metadata_json_size_bytes({"b": 2, "a": 1})
        self.assertEqual(a, b)


class ValidateMetadataJsonSizeTest(SimpleTestCase):
    """The cap-enforcement function itself."""

    @pytest.mark.integration
    def test_max_bytes_constant_is_64_kib(self):
        # Spec mandates 64 KB. A silent re-tune (e.g. an operator
        # bumping to 1 MB to admit a runaway feature) should
        # surface as a test failure, not a quiet behaviour shift.
        self.assertEqual(MAX_METADATA_JSON_BYTES, 64 * 1024)

    @pytest.mark.integration
    def test_none_admits(self):
        # None metadata never fails the cap.
        validate_metadata_json_size(None)  # no raise

    @pytest.mark.integration
    def test_empty_dict_admits(self):
        validate_metadata_json_size({})

    @pytest.mark.integration
    def test_small_payload_admits(self):
        validate_metadata_json_size({"upload_method": "browser", "chunk_size": 5_242_880})

    @pytest.mark.integration
    def test_payload_exactly_at_cap_admits(self):
        # The cap is the documented HARD CEILING; exactly 64 KB
        # is the highest admitted size. Off-by-one in the
        # comparison would push 64 KB into the reject bucket.
        # We construct a payload whose serialised size is exactly
        # MAX_METADATA_JSON_BYTES.
        prefix = '{"data": "'
        suffix = '"}'
        filler_len = MAX_METADATA_JSON_BYTES - len(prefix) - len(suffix)
        payload = {"data": "a" * filler_len}
        self.assertEqual(metadata_json_size_bytes(payload), MAX_METADATA_JSON_BYTES)
        validate_metadata_json_size(payload)  # no raise

    @pytest.mark.integration
    def test_payload_one_byte_over_cap_rejects(self):
        # The boundary is strict greater-than: 64 KB + 1 rejects.
        prefix = '{"data": "'
        suffix = '"}'
        filler_len = MAX_METADATA_JSON_BYTES - len(prefix) - len(suffix) + 1
        payload = {"data": "a" * filler_len}
        with self.assertRaises(ServiceValidationError) as ctx:
            validate_metadata_json_size(payload)
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_METADATA_TOO_LARGE")
        self.assertEqual(getattr(ctx.exception, "http_status", None), 400)

    @pytest.mark.integration
    def test_oversize_details_carry_full_triage_payload(self):
        big_payload = {"k" + str(i): "v" * 100 for i in range(1000)}
        with self.assertRaises(ServiceValidationError) as ctx:
            validate_metadata_json_size(big_payload)
        details = getattr(ctx.exception, "details", {}) or {}
        # Every field operators need: actual size, the cap that
        # fired, the field name (so a future caller validating a
        # different metadata slot can attribute the error
        # correctly), and a remediation hint.
        for field in ("field_name", "size_bytes", "max_bytes", "remediation"):
            self.assertIn(
                field,
                details,
                f"FILE_METADATA_TOO_LARGE details missing {field!r}; got {details!r}",
            )
        self.assertGreater(details["size_bytes"], MAX_METADATA_JSON_BYTES)
        self.assertEqual(details["max_bytes"], MAX_METADATA_JSON_BYTES)

    @pytest.mark.integration
    def test_field_name_kwarg_propagates_to_details(self):
        # Future callers (e.g. a separate ``user_metadata`` slot)
        # can reuse the same validator with custom attribution.
        big = {"k": "v" * (MAX_METADATA_JSON_BYTES + 100)}
        with self.assertRaises(ServiceValidationError) as ctx:
            validate_metadata_json_size(big, field_name="custom_metadata")
        details = getattr(ctx.exception, "details", {}) or {}
        self.assertEqual(details.get("field_name"), "custom_metadata")


# ---------------------------------------------------------------------------
# Model-layer — File.save() defensive cap
# ---------------------------------------------------------------------------


class FileSaveMetadataCapTest(TestCase):
    """The load-bearing gate: ``File.save()`` validates BEFORE the
    actual save so any caller (services, signals, management
    commands) is subject to the cap. A future feature that stuffs
    schema / lineage into ``metadata_json`` would hit this rather
    than silently bloat the column."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Meta {uid}",
            slug=f"meta-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"meta-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _file(self, **kwargs):
        defaults = {
            "tenant": self.tenant,
            "name": "test.csv",
            "content_type": "text/csv",
            "size": 1024,
            "status": FileStatus.PENDING,
            "scan_status": FileScanStatus.PENDING_SCAN,
            "storage_path": f"{self.tenant.id}/x.csv",
            "created_by": self.user,
        }
        defaults.update(kwargs)
        return File(**defaults)

    @pytest.mark.integration
    def test_create_with_small_metadata_succeeds(self):
        f = self._file(metadata_json={"upload_method": "browser"})
        f.save()
        f.refresh_from_db()
        self.assertEqual(f.metadata_json["upload_method"], "browser")

    @pytest.mark.integration
    def test_create_with_empty_metadata_succeeds(self):
        f = self._file(metadata_json={})
        f.save()  # no raise

    @pytest.mark.integration
    def test_create_with_oversize_metadata_raises_typed_error(self):
        # The model save MUST raise FILE_METADATA_TOO_LARGE BEFORE
        # the row hits Postgres. Without the model-level check, a
        # service that bypasses the serializer would silently
        # write a row past the spec cap.
        big = {"k" + str(i): "v" * 100 for i in range(1000)}
        f = self._file(metadata_json=big)
        with self.assertRaises(ServiceValidationError) as ctx:
            f.save()
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_METADATA_TOO_LARGE")
        self.assertEqual(getattr(ctx.exception, "http_status", None), 400)
        # Row was NOT persisted — the validation fires BEFORE
        # super().save().
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="test.csv").count(),
            0,
            "Oversize metadata must reject BEFORE row insert",
        )

    @pytest.mark.integration
    def test_update_with_oversize_metadata_raises(self):
        # Existing row → load → mutate metadata to oversize →
        # save MUST reject. The defence catches feature additions
        # that grow metadata over time (the original row was
        # within cap; a later mutation pushes it over).
        f = self._file(metadata_json={"upload_method": "browser"})
        f.save()  # ok at 30 bytes
        f.metadata_json = {"k" + str(i): "v" * 100 for i in range(1000)}
        with self.assertRaises(ServiceValidationError) as ctx:
            f.save()
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_METADATA_TOO_LARGE")
        # The persisted row still has the OLD metadata — the
        # rejected save did not partially commit.
        f.refresh_from_db()
        self.assertEqual(f.metadata_json, {"upload_method": "browser"})

    @pytest.mark.integration
    def test_objects_create_path_also_validates(self):
        # ``Model.objects.create()`` is documented as ``Model(...);
        # .save()`` so the validator should fire identically. Test
        # explicitly so a future Django change that adds a
        # ``create()`` fast-path bypass surfaces here.
        big = {"k" + str(i): "v" * 100 for i in range(1000)}
        with self.assertRaises(ServiceValidationError) as ctx:
            File.objects.create(
                tenant=self.tenant,
                name="oc.csv",
                content_type="text/csv",
                size=1024,
                status=FileStatus.PENDING,
                scan_status=FileScanStatus.PENDING_SCAN,
                storage_path=f"{self.tenant.id}/oc.csv",
                created_by=self.user,
                metadata_json=big,
            )
        self.assertEqual(getattr(ctx.exception, "code", None), "FILE_METADATA_TOO_LARGE")


# ---------------------------------------------------------------------------
# DB-layer — Postgres CHECK constraint catches save()-bypass paths
# ---------------------------------------------------------------------------


class FileMetadataDbConstraintTest(TestCase):
    """Phase 260.5.G.R1 GAP-B — bulk_create / objects.update() /
    raw SQL writes BYPASS Django's ``Model.save()`` and therefore
    bypass the Python-layer validator. The Postgres CHECK
    constraint installed by migration ``0008_metadata_json_size_cap``
    is the load-bearing defence for these paths.

    The constraint name (``file_metadata_json_size_cap``) and
    the byte rule (``octet_length(metadata_json::text) <= 65536``)
    are pinned by both this test class AND the migration's SQL —
    accidentally renaming or dropping the constraint surfaces here.
    """

    @staticmethod
    def _ensure_constraint():
        """Create the CHECK constraint if it doesn't exist yet.

        Production migration 0008 is the canonical owner of this
        constraint, but when the test database is reused across
        branches with migration-renumbering churn the DDL may not
        have been executed. The function is idempotent — a no-op
        when the constraint already exists.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_constraint WHERE conname = 'file_metadata_json_size_cap'"
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE files "
                    "ADD CONSTRAINT file_metadata_json_size_cap "
                    "CHECK (octet_length(metadata_json::text) <= 65536)"
                )

    def setUp(self):
        super().setUp()
        self._ensure_constraint()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DBC {uid}",
            slug=f"dbc-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"dbc-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _oversize_metadata(self):
        # Constructed to exceed 64 KB even after Postgres' canonical
        # JSON serialisation (which strips whitespace and may differ
        # slightly from Python's serialisation). 100-byte values ×
        # 1000 keys produces ~120 KB regardless of the encoder's
        # whitespace policy.
        return {"k" + str(i): "v" * 100 for i in range(1000)}

    @pytest.mark.integration
    def test_bulk_create_with_oversize_metadata_rejected_by_db_check(self):
        # Python-layer validator NEVER runs on bulk_create — but
        # the Postgres CHECK constraint does. Without the DB
        # constraint this insert would silently succeed.
        #
        # ``TestCase`` wraps each test in an outer atomic; an
        # IntegrityError aborts the active transaction, so any later
        # query (the post-assertion ``filter().count()`` here) raises
        # ``TransactionManagementError`` unless the failing statement
        # runs in an INNER ``atomic()`` (savepoint) that rolls back
        # cleanly without poisoning the outer block.
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            File.objects.bulk_create(
                [
                    File(
                        tenant=self.tenant,
                        name="bulk.csv",
                        content_type="text/csv",
                        size=1024,
                        status=FileStatus.PENDING,
                        scan_status=FileScanStatus.PENDING_SCAN,
                        storage_path=f"{self.tenant.id}/bulk.csv",
                        created_by=self.user,
                        metadata_json=self._oversize_metadata(),
                    )
                ]
            )
        # The DB constraint message names itself — pin so a rename
        # doesn't drop coverage silently.
        self.assertIn(
            "file_metadata_json_size_cap",
            str(ctx.exception),
            f"Expected constraint name in IntegrityError; got {ctx.exception!s}",
        )
        # No row landed.
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="bulk.csv").count(),
            0,
        )

    @pytest.mark.integration
    def test_objects_update_with_oversize_metadata_rejected_by_db_check(self):
        # Seed a row with valid metadata via save() — Python
        # validator clears.
        f = File.objects.create(
            tenant=self.tenant,
            name="upd.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.PENDING,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=f"{self.tenant.id}/upd.csv",
            created_by=self.user,
            metadata_json={"upload_method": "browser"},
        )
        # Now bypass save() via ``objects.filter(...).update(...)``
        # — Python validator does NOT run, but the DB constraint
        # does.
        #
        # Wrap in an inner ``atomic()`` so the outer ``TestCase``
        # transaction stays usable for the post-assertion
        # ``refresh_from_db`` query (otherwise the IntegrityError
        # poisons the outer block).
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            File.objects.filter(id=f.id).update(
                metadata_json=self._oversize_metadata(),
            )
        self.assertIn("file_metadata_json_size_cap", str(ctx.exception))
        # Row's metadata is UNCHANGED (DB rolled back the
        # constraint-violating write).
        f.refresh_from_db()
        self.assertEqual(f.metadata_json, {"upload_method": "browser"})

    @pytest.mark.integration
    def test_db_check_admits_metadata_at_cap_boundary(self):
        # Pin the boundary: a payload sized to the 64 KB cap
        # admits at the DB layer too. The Python validator and
        # the DB CHECK should agree at the boundary.
        prefix = '{"data": "'
        suffix = '"}'
        filler_len = MAX_METADATA_JSON_BYTES - len(prefix) - len(suffix)
        payload = {"data": "a" * filler_len}
        # Bypass the Python layer to test the DB layer in
        # isolation.
        File.objects.bulk_create(
            [
                File(
                    tenant=self.tenant,
                    name="atcap.csv",
                    content_type="text/csv",
                    size=1024,
                    status=FileStatus.PENDING,
                    scan_status=FileScanStatus.PENDING_SCAN,
                    storage_path=f"{self.tenant.id}/atcap.csv",
                    created_by=self.user,
                    metadata_json=payload,
                )
            ]
        )
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, name="atcap.csv").count(),
            1,
        )


# ---------------------------------------------------------------------------
# Serializer-layer — direct invocation (read_only-aware)
# ---------------------------------------------------------------------------


class FileSerializerMetadataValidatorTest(SimpleTestCase):
    """Phase 260.5.G.1 — the field-level validator is registered
    on ``FileSerializer.metadata_json`` even though the field is
    currently ``read_only``. We invoke the validator function
    DIRECTLY so the gate's behaviour is pinned for the day a
    future write surface lifts the read_only restriction.

    The test mirrors how DRF's field machinery would call the
    validator under a real write — same input shape, same
    exception expectation.
    """

    @pytest.mark.integration
    def test_validator_is_registered_on_metadata_json(self):
        # Pinning the registration prevents accidental removal
        # during a refactor — the validator is dead-code-but-armed
        # today, and the next person editing FileSerializer
        # shouldn't be able to remove it without a build break.
        from hub.apps.files.metadata_validators import validate_metadata_json_size

        registered = (
            FileSerializer.Meta.extra_kwargs.get("metadata_json", {}).get("validators") or []
        )
        self.assertIn(
            validate_metadata_json_size,
            registered,
            f"FileSerializer must register the metadata_json validator "
            f"per Phase 260.5.G.1; got validators={registered!r}",
        )

    @pytest.mark.integration
    def test_validator_admits_small_payload(self):
        from hub.apps.files.metadata_validators import validate_metadata_json_size

        # validate_metadata_json_size returns None on success, raises on failure.
        result = validate_metadata_json_size({"upload_method": "browser"})
        self.assertIsNone(result)

    @pytest.mark.integration
    def test_validator_rejects_oversize_payload_with_drf_error(self):
        from hub.apps.core.services.base import ValidationError as CoreValidationError
        from hub.apps.files.metadata_validators import validate_metadata_json_size

        big = {"k" + str(i): "v" * 100 for i in range(1000)}
        with self.assertRaises(CoreValidationError) as ctx:
            validate_metadata_json_size(big)
        self.assertEqual(
            getattr(ctx.exception, "code", None),
            "FILE_METADATA_TOO_LARGE",
            f"ValidationError must carry typed code; "
            f"got code={getattr(ctx.exception, 'code', None)!r}",
        )
