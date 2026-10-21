"""pilot-readiness 4.4 — tenant data export (the pilot exit-clause drill's
export leg).

Produces ONE archive per tenant in the object store under
``data-exports/<tenant_id>/tenant-export/`` containing every data class the
pilot tenant owns:

* ``tenant.json``           — tenant metadata (profile, plan, KYC, gates).
* ``audit-trail.jsonl``     — the tenant's audit events (same record shape
  as ``export_audit_trail``).
* ``files-manifest.json``   — the tenant's object files with 7-day
  presigned GET URLs (file bytes stay retrievable by the customer without
  moving them).
* ``users/<email>/export.zip`` — the per-user DSAR portability archive
  (GDPR Article 20 format) for EVERY ACTIVE tenant user, produced through
  the real ``DataPortabilityService`` and downloaded from the object store.

The archive is uploaded to the object store, a presigned download URL +
SHA-256 is printed as a JSON summary, and ONE ``TENANT_DATA_EXPORTED``
audit event is emitted. Re-runs are safe (a new archive per run — exports
are point-in-time snapshots, not idempotent state).

Management commands are cross-tenant by default (B-RLS-0.5): the command
resolves the tenant on the admin DB, then runs the per-tenant collection
inside ``tenant_context(tenant_id)``.

Usage:
    python hub/manage.py tenant_data_export --slug <slug>
    python hub/manage.py tenant_data_export --slug <slug> --download-url-ttl 604800
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.files.models import File
from hub.apps.files.storage import S3StorageClient
from hub.apps.gdpr.services import DataPortabilityService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class Command(BaseCommand):
    help = (
        "pilot-readiness 4.4 — export ALL data classes of one tenant into "
        "a single archive (tenant metadata + audit trail + file manifest "
        "with presigned GETs + per-user DSAR exports), uploaded to the "
        "object store with a presigned download URL."
    )

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="Tenant slug (or UUID).")
        parser.add_argument(
            "--download-url-ttl",
            type=int,
            default=604800,
            help="Presigned download URL lifetime in seconds (default 7 days).",
        )

    def _resolve_tenant(self, slug: str) -> Tenant:
        import uuid as _uuid

        try:
            _uuid.UUID(slug)
            tenant = Tenant.all_objects.filter(id=slug).first()
        except ValueError:
            tenant = Tenant.all_objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant {slug!r} not found")
        return tenant

    def _tenant_metadata(self, tenant: Tenant) -> dict[str, Any]:
        # Billing is the paid layer — guarded for both core-only
        # absence forms (W7.1); without it the metadata has no plan row.
        try:
            from hub.apps.billing.models import Subscription
        except (RuntimeError, ModuleNotFoundError):
            Subscription = None

        plan_row = None
        try:
            if Subscription is None:
                # Billing absent (core-only/public) — no plan row.
                subscription = None
            else:
                subscription = (
                    Subscription.objects.filter(tenant=tenant)
                    .select_related("plan")
                    .order_by("-created_at")
                    .first()
                )
            if subscription is not None and subscription.plan is not None:
                plan_row = {
                    "slug": subscription.plan.slug,
                    "name": subscription.plan.name,
                    "tier": subscription.plan.tier,
                    "status": subscription.status,
                }
        except (LookupError, ValueError):  # pragma: no cover — best-effort
            plan_row = None

        return {
            "format_version": 1,
            "exported_at": timezone.now().isoformat(),
            "tenant": {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "name": tenant.name,
                "status": tenant.status,
                "kyc_status": tenant.kyc_status,
                "created_at": tenant.created_at.isoformat(),
                "onboarding_completed_at": (
                    tenant.onboarding_completed_at.isoformat()
                    if tenant.onboarding_completed_at
                    else None
                ),
                "legal_hold": tenant.legal_hold,
                "plan": plan_row,
            },
        }

    def _audit_trail(self, tenant: Tenant) -> str:
        records = []
        for event in (
            AuditEvent.objects.filter(tenant=tenant)
            .order_by("timestamp")
            .iterator(chunk_size=10000)
        ):
            records.append(
                json.dumps(
                    {
                        "id": str(event.id),
                        "tenant_id": str(event.tenant_id),
                        "action": event.action,
                        "resource_type": event.resource_type,
                        "resource_id": str(event.resource_id),
                        "result": event.result,
                        "timestamp": event.timestamp.isoformat(),
                    }
                )
            )
        return "\n".join(records)

    def _files_manifest(self, tenant: Tenant, storage: S3StorageClient) -> dict[str, Any]:
        files = []
        for file_obj in File.objects.filter(tenant=tenant).order_by("created_at"):
            entry = {
                "id": str(file_obj.id),
                "name": file_obj.name,
                "content_type": file_obj.content_type,
                "size": file_obj.size,
                "content_sha256": file_obj.content_sha256,
                "status": file_obj.status,
                "created_at": file_obj.created_at.isoformat() if file_obj.created_at else None,
            }
            try:
                entry["download_url"] = storage.generate_presigned_download_url(
                    key=file_obj.storage_path,
                    expires_in=604800,
                    for_browser=True,
                )
            except Exception as exc:  # noqa: BLE001
                # One dead object must not kill the export; the manifest
                # records the failure for the customer to see.
                entry["download_url"] = None
                entry["presign_error"] = type(exc).__name__
            files.append(entry)
        return {"files": files}

    def _user_exports(self, tenant: Tenant, storage: S3StorageClient) -> dict[str, Any]:
        """Per-user DSAR archives through the REAL DataPortabilityService."""
        summary = {"users": []}
        users = User.objects.filter(tenant=tenant, status=UserStatus.ACTIVE).order_by("email")
        for user in users:
            service = DataPortabilityService(tenant_id=str(tenant.id), user_id=str(user.id))
            job = service.create_export_job(user_id=str(user.id))
            entry = {
                "email": user.email,
                "export_job_id": str(job.id),
                "status": job.status,
                "storage_path": job.storage_path,
                "download_url": job.download_url,
            }
            # Embed the actual archive bytes so the tenant export is
            # self-contained (not just pointers).
            if job.storage_path and job.status == "COMPLETED":
                try:
                    entry["archive_bytes"] = storage.download_file(job.storage_path)
                except Exception as exc:  # noqa: BLE001
                    # Best-effort embed: the job's presigned URL remains the
                    # retrieval path when the bytes cannot be embedded.
                    entry["archive_error"] = type(exc).__name__
            summary["users"].append(entry)
        return summary

    def _build_archive(
        self,
        tenant: Tenant,
        tenant_json: dict[str, Any],
        audit_trail: str,
        files_manifest: dict[str, Any],
        user_exports: dict[str, Any],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("tenant.json", json.dumps(tenant_json, indent=2, default=str))
            zf.writestr("audit-trail.jsonl", audit_trail or "")
            zf.writestr(
                "files-manifest.json",
                json.dumps(files_manifest, indent=2, default=str),
            )
            zf.writestr(
                "README.txt",
                f"Tenant data export for {tenant.slug}\n"
                f"Generated: {timezone.now().isoformat()}\n\n"
                "Contents:\n"
                "- tenant.json: tenant metadata\n"
                "- audit-trail.jsonl: tenant audit events\n"
                "- files-manifest.json: object files with presigned GET "
                "URLs (7 days)\n"
                "- users/<email>/export.zip: per-user DSAR portability "
                "archives\n",
            )
            for entry in user_exports["users"]:
                if entry.get("archive_bytes"):
                    zf.writestr(f"users/{entry['email']}/export.zip", entry["archive_bytes"])
                zf.writestr(
                    f"users/{entry['email']}/export-job.json",
                    json.dumps(
                        {k: v for k, v in entry.items() if k != "archive_bytes"},
                        indent=2,
                        default=str,
                    ),
                )
        buffer.seek(0)
        return buffer.read()

    def handle(self, *_args, **options):
        slug = options["slug"]
        ttl = options["download_url_ttl"]

        tenant = self._resolve_tenant(slug)

        from hub.apps.tenants.request_tenant import tenant_context

        with tenant_context(str(tenant.id)):
            storage = S3StorageClient()
            storage._ensure_bucket_exists()

            tenant_json = self._tenant_metadata(tenant)
            audit_trail = self._audit_trail(tenant)
            files_manifest = self._files_manifest(tenant, storage)
            user_exports = self._user_exports(tenant, storage)

            archive_bytes = self._build_archive(
                tenant, tenant_json, audit_trail, files_manifest, user_exports
            )
            sha256 = hashlib.sha256(archive_bytes).hexdigest()
            storage_key = (
                f"data-exports/{tenant.id}/tenant-export/"
                f"{timezone.now().strftime('%Y-%m-%dT%H%M%SZ')}.zip"
            )

            storage.upload_file(
                file_path=storage_key,
                file_content=archive_bytes,
                content_type="application/zip",
            )

            download_url = storage.generate_presigned_download_url(
                key=storage_key, expires_in=ttl, for_browser=True
            )

            create_audit_event(
                resource_type="TENANT_DATA_EXPORT",
                action=_audit_et.TENANT_DATA_EXPORTED,
                tenant=tenant,
                actor_user=None,
                resource_id=storage_key,
                details={
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "storage_key": storage_key,
                    "sha256": sha256,
                    "user_count": len(user_exports["users"]),
                    "file_count": len(files_manifest["files"]),
                    "audit_event_count": len(audit_trail.splitlines()) if audit_trail else 0,
                },
            )

        summary = {
            "tenant_slug": tenant.slug,
            "tenant_id": str(tenant.id),
            "storage_key": storage_key,
            "sha256": sha256,
            "download_url": download_url,
            "user_count": len(user_exports["users"]),
            "file_count": len(files_manifest["files"]),
        }
        self.stdout.write(json.dumps(summary, indent=2))
