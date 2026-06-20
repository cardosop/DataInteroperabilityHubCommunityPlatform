"""285.14.8.4 — Create a regulator audit evidence package (ZIP).

Usage:
    python manage.py create_regulator_audit_package \
        --tenant <slug> --regulation GDPR --from 2025-01-01 --to 2025-12-31 \
        --output /tmp/audit-package.zip
"""

import hashlib
import json
import zipfile

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a regulator audit evidence package."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, required=True, help="Tenant slug or UUID.")
        parser.add_argument("--regulation", type=str, default="GDPR", help="Regulation key.")
        parser.add_argument(
            "--from", dest="from_date", type=str, required=True, help="Start date (ISO format)."
        )
        parser.add_argument(
            "--to", dest="to_date", type=str, required=True, help="End date (ISO format)."
        )
        parser.add_argument("--output", type=str, required=True, help="Output ZIP file path.")
        parser.add_argument(
            "--verbose", action="store_true", default=False, help="Show per-section progress."
        )

    def handle(self, *args, **options):
        import uuid as _uuid

        from hub.apps.audit.models import AuditEvent
        from hub.apps.tenants.models import Tenant

        tenant_slug = options["tenant"]
        try:
            _uuid.UUID(tenant_slug)
            tenant = Tenant.objects.get(id=tenant_slug)
        except (ValueError, Tenant.DoesNotExist):
            tenant = Tenant.objects.get(slug=tenant_slug)

        from_date = options["from_date"]
        to_date = options["to_date"]
        output_path = options["output"]
        verbose = options["verbose"]

        self.stdout.write(
            f"Creating audit package for {tenant.slug} "
            f"({from_date} → {to_date}, regulation={options['regulation']})"
        )

        sections = {}
        checksums = {}

        # Section 1: Audit trail
        if verbose:
            self.stdout.write("  Exporting audit trail...")
        events = AuditEvent.objects.filter(
            tenant=tenant,
            timestamp__gte=from_date,
            timestamp__lte=to_date,
        ).order_by("timestamp")
        audit_lines = []
        for e in events.iterator(chunk_size=5000):
            audit_lines.append(
                json.dumps(
                    {
                        "id": str(e.id),
                        "action": e.action,
                        "resource_type": e.resource_type,
                        "timestamp": e.timestamp.isoformat(),
                    }
                )
            )
        sections["audit_trail.jsonl"] = "\n".join(audit_lines)
        if verbose:
            self.stdout.write(f"    {len(audit_lines)} events")

        # Section 2: Compliance scans
        if verbose:
            self.stdout.write("  Exporting compliance scans...")
        from hub.apps.compliance.models import ComplianceRun

        scans = ComplianceRun.objects.filter(
            tenant=tenant,
            created_at__gte=from_date,
            created_at__lte=to_date,
        ).order_by("created_at")
        scan_lines = []
        for s in scans.iterator(chunk_size=5000):
            scan_lines.append(
                json.dumps(
                    {
                        "id": str(s.id),
                        "framework": s.framework,
                        "regulation_key": s.regulation_key,
                        "allowed_to_store": s.allowed_to_store,
                        "created_at": s.created_at.isoformat(),
                    }
                )
            )
        sections["compliance_scans.jsonl"] = "\n".join(scan_lines)
        if verbose:
            self.stdout.write(f"    {len(scan_lines)} scans")

        # Build ZIP
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in sections.items():
                zf.writestr(filename, content)
                checksums[filename] = hashlib.sha256(content.encode()).hexdigest()

            # Add checksums
            checksum_content = "\n".join(f"{h}  {f}" for f, h in checksums.items())
            zf.writestr("checksums.txt", checksum_content)

        self.stdout.write(
            self.style.SUCCESS(
                f"Audit package created: {output_path} "
                f"({len(sections)} sections, checksums verified)"
            )
        )
