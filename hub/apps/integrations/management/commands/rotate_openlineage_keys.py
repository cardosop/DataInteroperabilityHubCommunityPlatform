"""
Phase 228 F4 (228.F4.11) — operator-driven key rotation.

Rotates the OpenLineage ingest API key for one tenant with a
**7-day grace window**: a fresh successor key is issued, and the
old key's ``expires_at`` is set to ``now + 7 days``. During the
grace window both keys authenticate; after the grace expires only
the new key works.

Usage::

    # Plan only:
    python manage.py rotate_openlineage_keys --tenant=<uuid> --dry-run

    # Issue the rotation (returns the new plaintext key ONCE on stdout):
    python manage.py rotate_openlineage_keys --tenant=<uuid>

    # Override the grace window:
    python manage.py rotate_openlineage_keys --tenant=<uuid> --grace-days=14
"""

from __future__ import annotations

import datetime as _dt
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEFAULT_GRACE_DAYS = 7


def _emit_rotation_audit(*, tenant, new_key, outgoing_count, grace_window_ends):
    """Phase 228 F4 (REQ-LIN-F4-003 / DoD self-audit GAP-D8) — best-
    effort audit emission for ``OPENLINEAGE_KEY_ROTATED``. Failures
    are swallowed: an audit-emit error MUST NOT fail the rotation
    (the rotation is the load-bearing operation; audit is a
    downstream signal).
    """
    try:
        from hub.apps.audit.models import OPENLINEAGE_KEY_ROTATED
        from hub.apps.audit.utils import create_audit_event
    except Exception:
        return
    try:
        create_audit_event(
            resource_type="OPENLINEAGE_KEY",
            action=OPENLINEAGE_KEY_ROTATED,
            actor_user=None,  # CLI rotation has no auth user; ops-driven.
            tenant=tenant,
            resource_id=str(new_key.id),
            details={
                "new_key_prefix": new_key.key_prefix,
                "outgoing_keys_graced": outgoing_count,
                "grace_window_ends": grace_window_ends.isoformat(),
            },
        )
    except Exception:
        pass


class Command(BaseCommand):
    help = (
        "Phase 228 F4 (228.F4.11): rotate the OpenLineage ingest API "
        "key for one tenant with a 7-day grace window."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument(
            "--grace-days",
            type=int,
            default=DEFAULT_GRACE_DAYS,
            help=f"Grace window in days (default {DEFAULT_GRACE_DAYS}).",
        )
        parser.add_argument("--label", default=None)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *_args, **options):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
            generate_ingest_key_plaintext,
            hash_ingest_key,
        )
        from hub.apps.tenants.models import Tenant

        tenant_id = options["tenant"]
        grace_days = max(0, int(options["grace_days"]))
        dry_run = options["dry_run"]
        label = options.get("label") or f"rotated-{_dt.date.today().isoformat()}"

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant {tenant_id!r} not found") from exc

        # Outgoing keys: every still-active key gets ``expires_at``
        # set to ``now + grace_days``. Already-revoked / expired
        # keys are untouched.
        now = timezone.now()
        cutoff = now + _dt.timedelta(days=grace_days)
        outgoing = OpenLineageIngestApiKey.objects.filter(
            tenant=tenant,
            revoked_at__isnull=True,
        )
        # Keys that have NO expiry yet OR an expiry beyond the cutoff
        # are the ones being rotated. (A key with expires_at < cutoff
        # is already in its grace tail; don't extend.)
        outgoing = outgoing.filter(
            expires_at__isnull=True,
        ) | outgoing.filter(expires_at__gt=cutoff)
        outgoing_count = outgoing.count()

        # New plaintext + persistent hash. Do NOT log the plaintext
        # — only the prefix.
        plaintext = generate_ingest_key_plaintext()
        prefix = plaintext.removeprefix("msh_ol_")[:8]

        if dry_run:
            self.stdout.write(
                json.dumps(
                    {
                        "phase": "228.F4.11",
                        "dry_run": True,
                        "tenant_id": str(tenant.id),
                        "outgoing_keys_to_grace": outgoing_count,
                        "grace_window_ends": cutoff.isoformat(),
                        "would_create_prefix": prefix,
                    },
                    sort_keys=True,
                )
            )
            return

        outgoing.update(expires_at=cutoff)

        new_key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label=label,
            key_prefix=prefix,
            key_hash=hash_ingest_key(plaintext),
        )
        # Phase 228 F4 (REQ-LIN-F4-003 / DoD self-audit GAP-D8) —
        # emit OPENLINEAGE_KEY_ROTATED so the audit trail captures
        # operator-driven rotations alongside UI create/revoke events.
        _emit_rotation_audit(
            tenant=tenant,
            new_key=new_key,
            outgoing_count=outgoing_count,
            grace_window_ends=cutoff,
        )

        # Output: structured JSON + a separate, plain-text plaintext
        # line so an operator pasting into a vault GUI gets it cleanly.
        self.stdout.write(
            json.dumps(
                {
                    "phase": "228.F4.11",
                    "tenant_id": str(tenant.id),
                    "new_key_id": str(new_key.id),
                    "new_key_prefix": prefix,
                    "outgoing_keys_graced": outgoing_count,
                    "grace_window_ends": cutoff.isoformat(),
                },
                sort_keys=True,
            )
        )
        self.stdout.write("")
        self.stdout.write("=== NEW INGEST KEY (visible ONCE) ===")
        self.stdout.write(plaintext)
        self.stdout.write("=== STORE IT NOW — Meshant cannot recover it ===")
