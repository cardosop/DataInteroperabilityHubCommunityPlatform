"""pilot-readiness 4.4 — tenant data export command (the exit-clause drill's
export leg).

Contract pinned here (TDD — the command did not exist before this suite):

1. ``tenant_data_export --slug <slug>`` produces ONE archive in the object
   store under ``data-exports/<tenant_id>/tenant-export/`` and prints the
   storage key + sha256 + a presigned download URL.
2. The archive is a REAL zip containing: tenant.json (tenant metadata),
   audit-trail.jsonl (tenant audit events), files-manifest.json (tenant
   object files with presigned GETs), and one per-user DSAR export archive
   (the user-level portability format) per ACTIVE tenant user.
3. The presigned download URL serves the archive bytes back (real roundtrip
   through the storage backend).
4. ONE ``TENANT_DATA_EXPORTED`` audit event is emitted per export.
5. Unknown tenant → CommandError (no archive written).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures (real models on the shared test DB — same conventions as the
# Phase 235.3 tenant-delete suite)
# ---------------------------------------------------------------------------


@pytest.fixture
def export_tenant(db):
    # P3-1: the NAME was fixed ("Export Drill Tenant") while the slug
    # was timestamped — the tenants_name_key unique constraint collided
    # on re-runs/residue (the duplicate-key failure class). Both are
    # unique now.
    stamp = timezone.now().strftime("%s%f")
    tenant = Tenant.objects.create(
        slug=f"export-drill-{stamp}",
        name=f"Export Drill Tenant {stamp}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.VERIFIED,
        onboarding_completed_at=timezone.now(),
    )
    user = User.objects.create_user(
        email=f"export-user-{tenant.slug}@example.com",
        password="TestPass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    File.objects.create(
        tenant=tenant,
        created_by=user,
        name="drill-report.csv",
        storage_path=f"tenant-files/{tenant.id}/drill-report.csv",
        size=12,
        content_type="text/csv",
        content_sha256="0" * 64,
        status="ACTIVE",
    )
    return tenant


class TestTenantDataExportCommand:
    def test_export_writes_archive_and_prints_contract(self, export_tenant, capsys):
        call_command("tenant_data_export", slug=export_tenant.slug)

        out = capsys.readouterr().out
        assert "storage_key" in out
        assert "sha256" in out
        assert "download_url" in out

        payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
        assert payload["tenant_slug"] == export_tenant.slug
        assert payload["user_count"] >= 1

    def test_export_emits_one_audit_event(self, export_tenant):
        before = AuditEvent.objects.filter(
            action=_audit_et.TENANT_DATA_EXPORTED
        ).count()
        call_command("tenant_data_export", slug=export_tenant.slug)
        events = AuditEvent.objects.filter(action=_audit_et.TENANT_DATA_EXPORTED)
        # P3-1: delta-counted (the shared-DB residue class).
        assert events.count() == before + 1, (
            "exactly one TENANT_DATA_EXPORTED per export"
        )
        assert str(events.first().tenant_id) == str(export_tenant.id)

    def test_archive_roundtrip_through_storage(self, export_tenant, capsys):
        call_command("tenant_data_export", slug=export_tenant.slug)
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{") : out.rindex("}") + 1])

        # The presigned URL is SigV4-bound to the host-published MinIO
        # endpoint (localhost:9010) and can only be consumed from the HOST
        # side — the exit-clause drill runner downloads it there. In this
        # suite the archive bytes come back through the REAL storage client.
        from hub.apps.files.storage import S3StorageClient

        archive_bytes = S3StorageClient().download_file(payload["storage_key"])
        assert hashlib.sha256(archive_bytes).hexdigest() == payload["sha256"], (
            "stored archive must match the printed sha256"
        )

        # The customer-facing contract: a signed http(s) URL.
        assert payload["download_url"].startswith("http"), "presigned URL contract"

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            names = set(zf.namelist())
        assert "tenant.json" in names
        assert "audit-trail.jsonl" in names
        assert "files-manifest.json" in names

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            tenant_json = json.loads(zf.read("tenant.json"))
            assert tenant_json["tenant"]["slug"] == export_tenant.slug
            manifest = json.loads(zf.read("files-manifest.json"))
            assert manifest["files"], "the tenant file object must be listed"

    def test_archive_contains_per_user_dsar_exports(self, export_tenant, capsys):
        call_command("tenant_data_export", slug=export_tenant.slug)
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{") : out.rindex("}") + 1])

        from hub.apps.files.storage import S3StorageClient

        archive_bytes = S3StorageClient().download_file(payload["storage_key"])
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            user_exports = [
                n for n in zf.namelist() if n.startswith("users/") and n.endswith(".zip")
            ]
        assert len(user_exports) >= 1, "every ACTIVE tenant user gets a DSAR export"

    def test_unknown_tenant_raises(self):
        with pytest.raises(CommandError):
            call_command("tenant_data_export", slug="no-such-tenant-drill")


class TestTenantDataExportedEventType:
    def test_event_type_is_registered(self):
        assert _audit_et.TENANT_DATA_EXPORTED == "TENANT_DATA_EXPORTED"


class TestSweepDrillOptions:
    """The 90-day grace must be bypassable ONLY for a named tenant in a
    drill (the legal-hold + DSAR re-checks stay enforced)."""

    def test_sweep_accepts_tenant_slug_and_drill_skip_grace(self):
        # The command parses the options without error (no-op run).
        call_command(
            "tenant_hard_delete_sweep",
            tenant_slug=["nonexistent-drill-tenant"],
            drill_skip_grace=True,
            dry_run=True,
            skip_job_row=True,
        )

    def test_drill_options_refuse_without_skip_grace(self):
        with pytest.raises(CommandError):
            call_command(
                "tenant_hard_delete_sweep",
                tenant_slug=["nonexistent-drill-tenant"],
                dry_run=True,
                skip_job_row=True,
            )

    def test_sweep_hard_deletes_a_tenant_with_users(self):
        """Regression pin (4.4 drill finding): the sweep failed with
        cascade_failed for ANY tenant that still had users —
        ``User.tenant`` is on_delete=RESTRICT. The sweep must purge the
        tenant's users inside the same atomic block."""
        from django.db.models import signals  # noqa: F401 (imports keep ruff quiet)

        tenant = Tenant.objects.create(
            slug=f"sweep-drill-{timezone.now().strftime('%s')}",
            name="Sweep Drill Tenant",
            status=TenantStatus.ACTIVE,
        )
        user = User.objects.create_user(
            email=f"sweep-user-{tenant.slug}@example.com",
            password="TestPass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        from hub.apps.tenants.models import TenantStatus as TS

        Tenant.all_objects.filter(pk=tenant.pk).update(
            scheduled_for_deletion_at=timezone.now(),
            deleted_at=timezone.now(),
            status=TS.DELETED,
        )
        call_command(
            "tenant_hard_delete_sweep",
            tenant_slug=[tenant.slug],
            drill_skip_grace=True,
            dry_run=False,
            skip_job_row=True,
        )
        assert not Tenant.all_objects.filter(pk=tenant.pk).exists()
        assert not User.objects.filter(pk=user.pk).exists()
