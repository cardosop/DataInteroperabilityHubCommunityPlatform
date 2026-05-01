"""
Phase 228 X (228.X.3.2 / REQ-LIN-X-003) — GDPR user cascade.

Lineage data is tenant-scoped, NOT user-scoped — purging "user X's
lineage" would over-delete other tenants' lineage. The user cascade
therefore SCRUBS user identifiers from lineage-related artifacts:

  * ``AuditEvent.actor_user`` set to NULL where action ∈
    ``LINEAGE_AUDIT_ACTIONS`` AND ``actor_user_id == <user-id>``.
  * ``LineageEdge.created_by_run`` is a free-form string; if it
    contains the user UUID, replace with ``"REDACTED"``.

The audit row itself survives (tenant-level audit trail is preserved
by design). Only the personal-data link is severed.

Usage::

    python manage.py delete_lineage_edges_for_user --user=<uuid>
"""
from __future__ import annotations

import json
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Phase 228 X (228.X.3.2): scrub user identifiers from lineage "
        "audit rows + created_by_run markers. Tenant-scoped lineage "
        "data is preserved — only personal-data links severed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *_args, **options):
        User = get_user_model()
        user_id = options["user"]
        dry_run = options["dry_run"]

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {user_id!r} not found") from exc

        from hub.apps.audit.models import AuditEvent, LINEAGE_AUDIT_ACTIONS
        from hub.apps.contracts.models import LineageEdge

        audit_qs = AuditEvent.objects.filter(
            actor_user_id=user.pk,
            action__in=LINEAGE_AUDIT_ACTIONS,
        )
        edge_qs = LineageEdge.objects.filter(
            created_by_run__contains=str(user.pk),
        )

        audit_count = audit_qs.count()
        edge_count = edge_qs.count()

        if dry_run:
            self.stdout.write(json.dumps({
                "phase": "228.X.3.2",
                "dry_run": True,
                "user_id": str(user.pk),
                "audit_rows_to_scrub": audit_count,
                "edge_rows_to_scrub": edge_count,
            }, sort_keys=True))
            return

        with transaction.atomic():
            # 1. Set actor_user to NULL on lineage audit rows.
            audit_qs.update(actor_user=None)
            # 2. Replace user UUID in created_by_run markers with
            #    a stable redaction sentinel so future audits can
            #    still see "this run wrote this row" without
            #    revealing the operator id.
            for row in edge_qs:
                row.created_by_run = (
                    row.created_by_run.replace(str(user.pk), "REDACTED")
                )
                row.save(update_fields=["created_by_run"])

        self.stdout.write(json.dumps({
            "phase": "228.X.3.2",
            "dry_run": False,
            "user_id": str(user.pk),
            "audit_rows_scrubbed": audit_count,
            "edge_rows_scrubbed": edge_count,
        }, sort_keys=True))
        logger.info(
            "lineage_gdpr_cascade_user_complete",
            extra={
                "user_id": str(user.pk),
                "audit": audit_count,
                "edges": edge_count,
            },
        )
