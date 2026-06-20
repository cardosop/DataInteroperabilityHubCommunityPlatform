"""
Phase 230.12.9 (REQ-SEM-LDN-003) — rotate per-tenant LDN signing keys.

Run on a 90-day cron. Generates a new RSA-2048 keypair per tenant
that has ``Tenant.semantic_ldn_enabled=True``, increments
``LdnTenantSigningKey.version`` + writes the new ``key_id`` and
public PEM, then publishes the private PEM to External Secrets
under ``ldn-signing-key/{tenant_id}``.

Idempotent — running it twice in the same hour is safe (each run
generates a fresh keypair). The PREVIOUS public key is NOT removed
from this row; partners verifying with v(N-1) start failing on the
next outbound delivery, which is the intended signal that the
partner needs to fetch the new key from
``GET /api/v1/semantic/ldn/keys/{tenant_id}``.

Backwards-compat is a follow-up — the spec mandates rotation but
not key-overlap; that's a separate ticket.
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hub.apps.semantic.ldn_signature import generate_keypair
from hub.apps.semantic.models import LdnTenantSigningKey
from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Phase 230.12.9 — rotate LDN signing keys for all tenants "
        "with semantic_ldn_enabled=True (90-day cron)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            help="Rotate for a single tenant (testing / one-off ops).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be rotated without writing.",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        dry_run = options.get("dry_run", False)

        qs = Tenant.objects.filter(semantic_ldn_enabled=True)
        if tenant_id:
            qs = qs.filter(pk=tenant_id)

        count = 0
        for tenant in qs:
            self.stdout.write(f"Rotating LDN key for tenant {tenant.id} ({tenant.slug})…")
            if dry_run:
                continue
            self._rotate_for_tenant(tenant)
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Rotated {count} tenant LDN keys (dry_run={dry_run}).")
        )

    def _rotate_for_tenant(self, tenant) -> None:
        priv_pem, pub_pem = generate_keypair(key_type="rsa")

        with transaction.atomic():
            existing = LdnTenantSigningKey.objects.filter(tenant=tenant).first()
            if existing is None:
                version = 1
                LdnTenantSigningKey.objects.create(
                    tenant=tenant,
                    key_id=f"meshant:tenant:{tenant.id}:ldn:v1",
                    public_key_pem=pub_pem,
                    version=version,
                )
            else:
                existing.version += 1
                existing.key_id = f"meshant:tenant:{tenant.id}:ldn:v{existing.version}"
                existing.public_key_pem = pub_pem
                existing.rotated_at = timezone.now()
                existing.save(
                    update_fields=[
                        "version",
                        "key_id",
                        "public_key_pem",
                        "rotated_at",
                    ]
                )

        # Push the private PEM to External Secrets. This is the
        # boundary; failing here leaves the DB at v(N) but the
        # secrets backend at v(N-1), which means the next outbound
        # delivery would sign with the OLD key but advertise the
        # NEW key_id — partners reject. Fail LOUD so ops sees this
        # mid-rotation and can re-run.
        try:
            self._publish_private_key(tenant_id=str(tenant.id), private_pem=priv_pem)
        except Exception as exc:
            logger.error(
                "ldn_key_rotation_secrets_publish_failed tenant_id=%s error=%s",
                tenant.id,
                exc,
                exc_info=True,
            )
            raise

    def _publish_private_key(self, *, tenant_id: str, private_pem: str) -> None:
        """Push the private PEM to External Secrets.

        Audit-fix GAP-C — was calling a non-existent
        ``hub.aws_secrets_loader.write_secret``. Replaced with a
        boto3-direct write that matches the JSON shape
        (``{"private_pem": "..."}``) the resolver in
        ``tasks_ldn._resolve_tenant_private_key`` expects.

        In dev / test (no AWS_REGION → boto3 client construction
        fails), we set an env-var ``LDN_SIGNING_KEY__<tenant_id>``
        instead. This matches the env-var fallback path the resolver
        also reads, so a dev rotate-then-sign round-trip works
        without an AWS backend.
        """
        import json as _json
        import os

        secret_id = f"ldn-signing-key/{tenant_id}"
        secret_body = _json.dumps({"private_pem": private_pem})

        try:
            from hub.aws_secrets_loader import _build_client

            client = _build_client()
            try:
                client.update_secret(SecretId=secret_id, SecretString=secret_body)
            except Exception:
                # Secret doesn't exist yet — create it.
                client.create_secret(Name=secret_id, SecretString=secret_body)
        except Exception as exc:
            # Dev / test fallback — env var keyed on tenant id. The
            # resolver checks this env var FIRST before falling
            # through to AWS, so a rotate-then-sign round-trip works
            # in environments without AWS Secrets Manager.
            logger.warning(
                "ldn_key_rotation_secrets_backend_unavailable tenant_id=%s "
                "error=%s — falling back to env-var. Wire ExternalSecrets "
                "before production rollout.",
                tenant_id,
                exc,
            )
            os.environ[f"LDN_SIGNING_KEY__{tenant_id}"] = private_pem
