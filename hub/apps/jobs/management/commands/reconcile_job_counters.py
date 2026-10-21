"""
W2.8 (B-10) — reconcile tenant job counters from the Job table.

The Redis job counters (`job:tenant:{id}:running|queued`) drift on
failed writes, TTL expiry, and restarts; the enforcement gate
reconciles on read, and this command is the operator-side sweep that
repairs every tenant's counters in one pass (scheduled alongside the
other job hygiene commands).
"""

from django.core.management.base import BaseCommand

from hub.apps.jobs.models import Job, JobStatus
from hub.apps.jobs.utils import reconcile_tenant_job_counters


class Command(BaseCommand):
    help = "Rebuild every tenant's Redis job counters from the Job table"

    def handle(self, *_args, **_options):
        """Reconcile counters for every tenant that has Job rows."""
        tenant_ids = (
            Job.objects.filter(status__in=[JobStatus.RUNNING, JobStatus.PENDING])
            .values_list("tenant_id", flat=True)
            .distinct()
        )
        repaired = 0
        for tenant_id in tenant_ids:
            counts = reconcile_tenant_job_counters(str(tenant_id))
            repaired += 1
            self.stdout.write(
                f"tenant={tenant_id} running={counts['running']} queued={counts['queued']}"
            )
        self.stdout.write(self.style.SUCCESS(f"Reconciled job counters for {repaired} tenant(s)"))
