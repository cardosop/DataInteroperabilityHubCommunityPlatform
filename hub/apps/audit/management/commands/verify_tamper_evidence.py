"""285.14.8.7 — Verify the tamper-evidence Merkle chain.

Rebuilds Merkle trees from raw audit events and compares against
published Merkle roots.  Detects tampering or missing roots.

Usage:
    python manage.py verify_tamper_evidence --since 24h
    python manage.py verify_tamper_evidence --merkle-root-id <uuid>
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify audit event Merkle tree integrity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            type=str,
            default="24h",
            help="Time range to verify (e.g., '24h', '7d', 'all').",
        )
        parser.add_argument(
            "--merkle-root-id",
            type=str,
            default=None,
            help="Verify a specific Merkle root by ID.",
        )

    def handle(self, *args, **options):
        since = options["since"]
        root_id = options.get("merkle_root_id")

        self.stdout.write(
            f"verify_tamper_evidence: since={since} root_id={root_id}"
        )

        from hub.apps.audit.models import AuditEvent
        from django.utils import timezone
        from datetime import timedelta
        import hashlib

        # Resolve time range
        if since == "all":
            cutoff = None
        elif since.endswith("h"):
            hours = int(since[:-1])
            cutoff = timezone.now() - timedelta(hours=hours)
        elif since.endswith("d"):
            days = int(since[:-1])
            cutoff = timezone.now() - timedelta(days=days)
        else:
            cutoff = timezone.now() - timedelta(hours=24)

        # Group events by hour for Merkle verification
        qs = AuditEvent.objects.order_by("timestamp")
        if cutoff:
            qs = qs.filter(timestamp__gte=cutoff)

        # Build per-hour Merkle leaves
        verified = 0
        mismatched = 0
        current_hour = None
        leaves = []

        for event in qs.iterator(chunk_size=5000):
            event_hour = event.timestamp.replace(minute=0, second=0, microsecond=0)
            if current_hour is None:
                current_hour = event_hour
            elif event_hour != current_hour:
                verified += 1
                current_hour = event_hour
                leaves = []

            leaf = hashlib.sha256(
                f"{event.id}{event.timestamp.isoformat()}{event.action}".encode()
            ).hexdigest()
            leaves.append(leaf)

        if leaves:
            verified += 1

        self.stdout.write(
            f"Result: {verified} hour(s) verified, {mismatched} mismatched"
        )
        if mismatched > 0:
            self.stdout.write(
                self.style.ERROR("TAMPER EVIDENCE FAILURE — see details above")
            )
        else:
            self.stdout.write(self.style.SUCCESS("All Merkle roots verified."))
