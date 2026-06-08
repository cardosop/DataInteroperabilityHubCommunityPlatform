"""
285.12.7.9 7I — Send deprecation notices for flags approaching sunset.

Queries feature_flag_registry for GA flags with retire_by within
90/60/30 days and emits audit events.  Designed as a weekly cron job.
"""
from __future__ import annotations
import structlog
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.feature_flag_registry import REGISTRY

logger = structlog.get_logger(__name__)

class Command(BaseCommand):
    help = "285.12.7.9 — Send deprecation notices for flags approaching sunset"

    def handle(self, *args, **options):
        now = datetime.now(tz=timezone.utc)
        windows = {"90-day": 90, "60-day": 60, "30-day": 30}
        notices = 0

        for flag in REGISTRY:
            if not flag.retire_by or flag.stage not in ("GA", "CANARY"):
                continue
            days_left = (flag.retire_by - now).days
            for label, window in windows.items():
                if 0 <= days_left <= window and days_left > window - 7:
                    self.stdout.write(
                        f"[{flag.name}] {days_left}d until sunset (retire_by={flag.retire_by.date()})"
                    )
                    try:
                        create_audit_event(
                            resource_type="FEATURE_FLAG",
                            action="FLAG_DEPRECATION_NOTICE",
                            actor_user=None,
                            resource_id=flag.name,
                            details={"days_until_sunset": days_left, "retire_by": str(flag.retire_by.date())},
                        )
                        notices += 1
                    except Exception as exc:
                        logger.warning("deprecation_notice_failed", flag=flag.name, error=str(exc))
                    break

        if notices:
            self.stdout.write(self.style.SUCCESS(f"Sent {notices} deprecation notice(s)"))
        else:
            self.stdout.write("No flags approaching sunset in notification windows")
