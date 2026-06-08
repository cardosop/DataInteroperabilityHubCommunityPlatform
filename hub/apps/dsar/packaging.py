"""Build KMS-on-S3-backed DSAR responses (ZIP + manifest); erasure invokes gdpr ErasureService."""

from __future__ import annotations
import hashlib
import io
import json
import zipfile

from django.utils import timezone

from hub.apps.dsar.models import DSARRequest, DSARRequestType, BackupAffectedBySubject
from hub.apps.files.storage import S3StorageClient
from hub.apps.dsar.workflow import transition_status


def _manifest_entry(filename: str, data: bytes) -> tuple[str, str]:
    return filename, hashlib.sha256(data).hexdigest()


def build_dsar_zip_bytes(dsar: DSARRequest) -> tuple[bytes, str]:
    """
    Produce encrypted-at-rest artifact bytes plus aggregate SHA-256 over the ZIP.
    Structured export scaffolding (Phase 232.2.7 — legal-basis segregation) uses
    per-folder entries in MANIFEST.json.
    """
    buf = io.BytesIO()
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if dsar.request_type == DSARRequestType.ERASURE:
            body = (
                b"Erasure request recorded. Warm-path personal data purge executed "
                b"via ErasureService when a linked Hub user exists; immutable backups "
                b"remain governed by BackupAffectedBySubject registrations (D232.9).\n"
            )
            fname = "ERASURE/NOTICE.txt"
            zf.writestr(fname, body)
            mkey, mh = _manifest_entry(fname, body)
            manifest[mkey] = mh

        elif dsar.request_type in (
            DSARRequestType.ACCESS,
            DSARRequestType.PORTABILITY,
        ):
            portability = json.dumps(
                {
                    "dsar_id": str(dsar.id),
                    "tenant_id": str(dsar.tenant_id),
                    "subject_email_domain": dsar.subject_email.split("@")[-1],
                    "request_type": dsar.request_type,
                },
                sort_keys=True,
            ).encode("utf-8")
            pname = (
                "PORTABILITY/export.json"
                if dsar.request_type == DSARRequestType.PORTABILITY
                else "ACCESS/summary.json"
            )
            zf.writestr(pname, portability)
            k1, h1 = _manifest_entry(pname, portability)
            manifest[k1] = h1

            # Phase 232.2.7 — machine-readable CSV adjunct (mirrors JSON envelope).
            csv_lines = [
                "field,value",
                f"dsar_id,{dsar.id}",
                f"tenant_id,{dsar.tenant_id}",
                f"subject_email_domain,{dsar.subject_email.split('@')[-1]}",
                f"request_type,{dsar.request_type}",
            ]
            cname = (
                "PORTABILITY/export.csv"
                if dsar.request_type == DSARRequestType.PORTABILITY
                else "ACCESS/summary.csv"
            )
            csv_bytes = ("\n".join(csv_lines) + "\n").encode("utf-8")
            zf.writestr(cname, csv_bytes)
            ck, ch = _manifest_entry(cname, csv_bytes)
            manifest[ck] = ch

        else:
            note = json.dumps(
                {
                    "dsar_id": str(dsar.id),
                    "handler_message": (
                        "Request type queued for specialist review "
                        "(rectification / restriction / objection / automated decision)."
                    ),
                },
                indent=2,
            ).encode("utf-8")
            fname = "REVIEW/placeholder.json"
            zf.writestr(fname, note)
            mk, hv = _manifest_entry(fname, note)
            manifest[mk] = hv

        man_bytes = json.dumps({"files": manifest}, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        zf.writestr("MANIFEST.json", man_bytes)

    binary = buf.getvalue()
    return binary, hashlib.sha256(binary).hexdigest()


def registry_backup_for_erasure(dsar: DSARRequest) -> BackupAffectedBySubject:
    """D232.9 — annotate backup-exempt posture for cold-store operators."""
    return BackupAffectedBySubject.objects.create(
        tenant=dsar.tenant,
        dsar=dsar,
        subject_email_normalized=dsar.subject_email,
        backup_identifier=f"tenant:{dsar.tenant_id}:dsar:{dsar.id}:warm-store",
        exempt_from_cascade=True,
        notes="Immutable backups outside Hub SQL must be rotated per retention policy.",
    )


def execute_warm_erasure_if_linked(dsar: DSARRequest, *, actor_user_id: str | None) -> None:
    if dsar.request_type != DSARRequestType.ERASURE:
        return
    if not dsar.linked_user_id:
        return
    from hub.apps.gdpr.services import ErasureService

    svc = ErasureService(
        tenant_id=str(dsar.tenant_id), user_id=actor_user_id or str(dsar.linked_user_id)
    )
    req = svc.create_request(str(dsar.linked_user_id))
    svc.execute_erasure(str(req.id))


def materialize_dsar_package(dsar: DSARRequest, *, actor_user_id: str | None) -> DSARRequest:
    from django.conf import settings

    from hub.apps.dsar.models import DSARStatus

    transition_status(dsar, DSARStatus.PACKAGE_IN_PROGRESS, actor_user=None)

    if dsar.request_type == DSARRequestType.ERASURE:
        registry_backup_for_erasure(dsar)
        execute_warm_erasure_if_linked(dsar, actor_user_id=actor_user_id)

    zip_bytes, sha = build_dsar_zip_bytes(dsar)
    key_prefix = f"{dsar.tenant_id}/dsar_packages/{dsar.id}/"
    storage_key = f"{key_prefix}response.zip"

    storage = S3StorageClient()
    storage.upload_file(storage_key, zip_bytes, "application/zip")

    kms_hint = getattr(settings, "AWS_S3_SSE_KMS_KEY_ID", "") or getattr(
        settings, "AWS_KMS_KEY_ID", ""
    )

    DSARRequest.objects.filter(pk=dsar.pk).update(
        response_object_key=storage_key,
        response_manifest_sha256=sha,
        response_kms_key_id=(kms_hint or "")[:512],
        response_generated_at=timezone.now(),
    )
    dsar.refresh_from_db()
    transition_status(dsar, DSARStatus.AWAITING_DOWNLOAD, actor_user=None)
    return dsar
