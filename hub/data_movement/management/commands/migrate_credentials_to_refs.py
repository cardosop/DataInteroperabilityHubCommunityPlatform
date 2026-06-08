"""
Management command to migrate inline credentials to AWS Secrets Manager refs.

Extracts credential-related keys from ``source_config`` / ``destination_config``
on ``ScheduledIngestion`` and ``ScheduledExport`` rows, creates AWS SM secrets,
and sets ``credential_ref`` to the resulting ARN.  A ``_backup`` key is
preserved in the config JSON for rollback.

Usage:
    python manage.py migrate_credentials_to_refs --dry-run
    python manage.py migrate_credentials_to_refs --execute --tenant-id <uuid>
    python manage.py migrate_credentials_to_refs --rollback --tenant-id <uuid>
"""
from __future__ import annotations

import json
import logging
import uuid
from io import StringIO

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Keys recognised as credentials that should be extracted from inline configs.
_CREDENTIAL_KEYS = frozenset({
    "access_key_id", "secret_access_key", "session_token",
    "password", "private_key", "key_file", "credentials_json",
    "access_token", "api_key", "api_secret",
})


def _extract_credentials(config: dict) -> tuple[dict, dict]:
    """Return ``(secrets_dict, remaining_config)``."""
    secrets = {}
    rest = {}
    for k, v in config.items():
        if k in _CREDENTIAL_KEYS and v:
            secrets[k] = v
        else:
            rest[k] = v
    return secrets, rest


def _create_sm_secret(secrets_dict: dict, resource_type: str, resource_id: str) -> str | None:
    """Create an AWS SM secret and return its ARN.

    Returns None when ``boto3`` is unavailable or the write fails.
    """
    try:
        import boto3
    except ImportError:
        logger.warning("boto3_not_installed_cannot_create_sm_secret")
        return None

    try:
        client = boto3.client("secretsmanager")
        secret_name = f"data-movement/{resource_type}/{resource_id}"
        response = client.create_secret(
            Name=secret_name,
            SecretString=json.dumps(secrets_dict, default=str),
            Description=f"Data movement credentials for {resource_type} {resource_id}",
        )
        return response.get("ARN")
    except Exception:
        logger.exception(
            "sm_secret_create_failed",
            resource_type=resource_type,
            resource_id=resource_id,
        )
        return None


def _delete_sm_secret(credential_ref: str) -> bool:
    """Delete an AWS SM secret by ARN.  Returns True on success."""
    if not credential_ref or not credential_ref.startswith("arn:aws:secretsmanager:"):
        return False
    try:
        import boto3
    except ImportError:
        return False
    try:
        client = boto3.client("secretsmanager")
        client.delete_secret(SecretId=credential_ref, ForceDeleteWithoutRecovery=True)
        return True
    except Exception:
        logger.exception("sm_secret_delete_failed", arn=credential_ref)
        return False


class Command(BaseCommand):
    help = "Migrate inline credentials to AWS SM credential_ref."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview without changes.")
        parser.add_argument("--execute", action="store_true", help="Perform the migration.")
        parser.add_argument("--rollback", action="store_true", help="Restore from _backup.")
        parser.add_argument("--tenant-id", help="Limit to one tenant.")
        parser.add_argument("--model", default="both", choices=["ingestion", "export", "both"])

    def handle(self, **options):
        dry_run = options["dry_run"]
        execute = options["execute"]
        rollback = options["rollback"]
        tenant_id = options["tenant_id"]
        model_filter = options["model"]

        if not (dry_run or execute or rollback):
            self.stderr.write("ERROR: pass --dry-run, --execute, or --rollback")
            return

        if rollback:
            self._handle_rollback(tenant_id, model_filter, dry_run)
            return

        self._handle_migrate(tenant_id, model_filter, execute, dry_run)

    # ------------------------------------------------------------------
    # Migrate path
    # ------------------------------------------------------------------

    def _handle_migrate(self, tenant_id, model_filter, execute, dry_run):
        if model_filter in ("ingestion", "both"):
            self._migrate_ingestions(tenant_id, execute, dry_run)
        if model_filter in ("export", "both"):
            self._migrate_exports(tenant_id, execute, dry_run)

    def _migrate_ingestions(self, tenant_id, execute, dry_run):
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        qs = ScheduledIngestion.objects.filter(credential_ref__isnull=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        for obj in qs.iterator():
            config = obj.source_config or {}
            secrets, rest = _extract_credentials(config)
            if not secrets:
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] ingestion {obj.id}: would extract "
                    f"{sorted(secrets.keys())}"
                )
                continue

            arn = _create_sm_secret(secrets, "ingestion", str(obj.id))
            if not arn:
                self.stderr.write(f"ERROR: failed to create SM secret for ingestion {obj.id}")
                continue

            rest["_backup"] = dict(config)
            ScheduledIngestion.objects.filter(pk=obj.pk).update(
                source_config=rest,
                credential_ref=arn,
            )
            self.stdout.write(
                f"[MIGRATED] ingestion {obj.id} → credential_ref={arn}"
            )

    def _migrate_exports(self, tenant_id, execute, dry_run):
        from hub.apps.scheduled_export.models import ScheduledExport

        qs = ScheduledExport.objects.filter(credential_ref__isnull=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        for obj in qs.iterator():
            config = obj.destination_config or {}
            secrets, rest = _extract_credentials(config)
            if not secrets:
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] export {obj.id}: would extract "
                    f"{sorted(secrets.keys())}"
                )
                continue

            arn = _create_sm_secret(secrets, "export", str(obj.id))
            if not arn:
                self.stderr.write(f"ERROR: failed to create SM secret for export {obj.id}")
                continue

            rest["_backup"] = dict(config)
            ScheduledExport.objects.filter(pk=obj.pk).update(
                destination_config=rest,
                credential_ref=arn,
            )
            self.stdout.write(
                f"[MIGRATED] export {obj.id} → credential_ref={arn}"
            )

    # ------------------------------------------------------------------
    # Rollback path
    # ------------------------------------------------------------------

    def _handle_rollback(self, tenant_id, model_filter, dry_run):
        if model_filter in ("ingestion", "both"):
            self._rollback_ingestions(tenant_id, dry_run)
        if model_filter in ("export", "both"):
            self._rollback_exports(tenant_id, dry_run)

    def _rollback_ingestions(self, tenant_id, dry_run):
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        qs = ScheduledIngestion.objects.filter(credential_ref__isnull=False)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        for obj in qs.iterator():
            config = obj.source_config or {}
            backup = config.pop("_backup", None)
            if not backup:
                continue

            ref = obj.credential_ref
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] ingestion {obj.id}: would restore from "
                    f"_backup and delete SM secret {ref}"
                )
                continue

            if ref:
                _delete_sm_secret(ref)
            ScheduledIngestion.objects.filter(pk=obj.pk).update(
                source_config=backup,
                credential_ref=None,
            )
            self.stdout.write(f"[ROLLBACK] ingestion {obj.id} restored")

    def _rollback_exports(self, tenant_id, dry_run):
        from hub.apps.scheduled_export.models import ScheduledExport

        qs = ScheduledExport.objects.filter(credential_ref__isnull=False)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        for obj in qs.iterator():
            config = obj.destination_config or {}
            backup = config.pop("_backup", None)
            if not backup:
                continue

            ref = obj.credential_ref
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] export {obj.id}: would restore from "
                    f"_backup and delete SM secret {ref}"
                )
                continue

            if ref:
                _delete_sm_secret(ref)
            ScheduledExport.objects.filter(pk=obj.pk).update(
                destination_config=backup,
                credential_ref=None,
            )
            self.stdout.write(f"[ROLLBACK] export {obj.id} restored")
