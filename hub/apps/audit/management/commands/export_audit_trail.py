"""285.14.8.7 — Export audit trail as JSON Lines.

Usage:
    python manage.py export_audit_trail --tenant <slug> --since 2025-01-01 --until 2025-12-31
    python manage.py export_audit_trail --tenant <slug> --format jsonl --output /tmp/audit.jsonl
"""
import json
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export audit trail events to JSON Lines for regulator/compliance use."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", type=str, required=True, help="Tenant slug or UUID."
        )
        parser.add_argument(
            "--since", type=str, default=None, help="Start date (ISO format)."
        )
        parser.add_argument(
            "--until", type=str, default=None, help="End date (ISO format)."
        )
        parser.add_argument(
            "--format", type=str, default="jsonl", choices=["jsonl", "csv"],
            help="Output format."
        )
        parser.add_argument(
            "--output", type=str, default=None, help="Output file path."
        )
        parser.add_argument(
            "--batch-size", type=int, default=10000,
            help="Events per batch."
        )

    def handle(self, *args, **options):
        tenant_slug = options["tenant"]
        output_path = options["output"]
        fmt = options["format"]
        batch_size = options["batch_size"]

        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.models import AuditEvent
        from django.utils import timezone
        import uuid as _uuid

        # Resolve tenant
        try:
            _uuid.UUID(tenant_slug)
            tenant = Tenant.objects.get(id=tenant_slug)
        except (ValueError, Tenant.DoesNotExist):
            tenant = Tenant.objects.get(slug=tenant_slug)

        qs = AuditEvent.objects.filter(tenant=tenant).order_by("timestamp")

        if options["since"]:
            qs = qs.filter(timestamp__gte=options["since"])
        if options["until"]:
            qs = qs.filter(timestamp__lte=options["until"])

        total = qs.count()
        self.stdout.write(f"Exporting {total} audit events for tenant {tenant.slug}")

        out = open(output_path, "w") if output_path else self.stdout
        exported = 0

        try:
            for event in qs.iterator(chunk_size=batch_size):
                record = {
                    "id": str(event.id),
                    "tenant_id": str(event.tenant_id),
                    "action": event.action,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "result": event.result,
                    "timestamp": event.timestamp.isoformat(),
                }
                if fmt == "jsonl":
                    out.write(json.dumps(record) + "\n")
                exported += 1

            self.stdout.write(f"Exported {exported} events.")
        finally:
            if output_path:
                out.close()
