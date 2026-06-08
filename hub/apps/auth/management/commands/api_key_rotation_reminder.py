"""Daily API-key rotation reminder & expiry notification sweep (277.B.069)."""

from __future__ import annotations
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.auth.models import APIKey
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.notifications.models import EmailType


def _resolve_recipient(api_key: APIKey) -> str | None:
    """Return the best email address to notify for an API key."""
    if api_key.customer_email:
        return api_key.customer_email
    if api_key.user_id:
        return api_key.user.email
    return None


def run_api_key_rotation_reminder_scan(
    *,
    now=None,
) -> dict[str, int]:
    """
    Scan active API keys and send rotation/expiry reminders.

    Reminder thresholds are read from ``API_KEY_ROTATION_REMINDER_DAYS``
    (default: [30, 14, 7, 1]).  One reminder is sent per threshold crossing;
    idempotency is enforced via ``APIKey.last_rotation_reminder_at``.

    Returns a dict of counters keyed by outcome.
    """
    if now is None:
        now = timezone.now()

    thresholds: list[int] = getattr(
        settings, "API_KEY_ROTATION_REMINDER_DAYS", [30, 14, 7, 1]
    )
    if not thresholds:
        return {"skipped (no thresholds configured)": 0}

    # Sort ascending so we test most-urgent first
    thresholds = sorted(thresholds)

    counters: dict[str, int] = {
        "scanned": 0,
        "expired": 0,
        "no_recipient": 0,
        "already_reminded": 0,
        **{f"reminder_{t}d": 0 for t in thresholds},
    }

    # Only keys that (a) are not revoked, (b) have an expiry set
    qs = (
        APIKey.objects.filter(revoked_at__isnull=True, expires_at__isnull=False)
        .select_related("user", "tenant")
    )

    for api_key in qs.iterator(chunk_size=200):
        counters["scanned"] += 1
        days_remaining = (api_key.expires_at - now).days  # may be negative

        # ── Expired keys ──────────────────────────────────────────────────
        if days_remaining < 0:
            # Notify once: last reminder was sent *before* the key expired
            if (
                api_key.last_rotation_reminder_at is None
                or api_key.last_rotation_reminder_at < api_key.expires_at
            ):
                recipient = _resolve_recipient(api_key)
                if recipient:
                    _send_expiry_email(api_key, recipient, now)
                    counters["expired"] += 1
                else:
                    counters["no_recipient"] += 1
                api_key.last_rotation_reminder_at = now
                api_key.save(update_fields=["last_rotation_reminder_at", "updated_at"])
            else:
                counters["already_reminded"] += 1
            continue

        # ── Upcoming expiry: find the tightest applicable threshold ───────
        applicable: int | None = None
        for t in thresholds:
            if days_remaining <= t:
                applicable = t
                break  # smallest (most urgent) threshold wins

        if applicable is None:
            # Still further out than the widest threshold — nothing to do
            continue

        # Has a reminder already been sent within this threshold window?
        # We check: when the last reminder was sent, was the remaining time
        # still GREATER than this threshold?  If so, we have crossed into
        # a new window and should send.
        if api_key.last_rotation_reminder_at is not None:
            days_at_last_reminder = (
                api_key.expires_at - api_key.last_rotation_reminder_at
            ).days
            if days_at_last_reminder <= applicable:
                # Already reminded within this threshold window
                continue

        recipient = _resolve_recipient(api_key)
        if not recipient:
            api_key.last_rotation_reminder_at = now
            api_key.save(update_fields=["last_rotation_reminder_at", "updated_at"])
            counters["no_recipient"] += 1
            continue

        _send_expiring_email(api_key, recipient, days_remaining, now)
        api_key.last_rotation_reminder_at = now
        api_key.save(update_fields=["last_rotation_reminder_at", "updated_at"])
        counters[f"reminder_{applicable}d"] += 1

    return counters


def _send_expiring_email(
    api_key: APIKey,
    recipient: str,
    days_remaining: int,
    now,
) -> None:
    """Enqueue an API_KEY_EXPIRING notification."""
    from hub.apps.notifications.tasks import send_email_async

    try:
        send_email_async(
            email_type=EmailType.API_KEY_EXPIRING,
            to_email=recipient,
            subject=f"API key '{api_key.name}' expires in {days_remaining} day(s)",
            template_name="notifications/emails/api_key_expiring.html",
            context={
                "api_key_name": api_key.name,
                "api_key_id": str(api_key.id),
                "tenant_name": api_key.tenant.name if api_key.tenant_id else "",
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else "",
                "days_remaining": days_remaining,
            },
            tenant_id=str(api_key.tenant_id) if api_key.tenant_id else None,
            user_id=str(api_key.user_id) if api_key.user_id else None,
        )
    except Exception:
        # Best-effort: a single email failure must not abort the entire sweep
        pass


def _send_expiry_email(api_key: APIKey, recipient: str, now) -> None:
    """Enqueue an API_KEY_EXPIRED notification."""
    from hub.apps.notifications.tasks import send_email_async

    try:
        send_email_async(
            email_type=EmailType.API_KEY_EXPIRED,
            to_email=recipient,
            subject=f"API key '{api_key.name}' has expired",
            template_name="notifications/emails/api_key_expired.html",
            context={
                "api_key_name": api_key.name,
                "api_key_id": str(api_key.id),
                "tenant_name": api_key.tenant.name if api_key.tenant_id else "",
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else "",
            },
            tenant_id=str(api_key.tenant_id) if api_key.tenant_id else None,
            user_id=str(api_key.user_id) if api_key.user_id else None,
        )
    except Exception:
        pass


class Command(BaseCommand):
    help = (
        "Scan API keys approaching expiry and send rotation reminders "
        "via email (277.B.069)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job row (useful for local smoke tests)",
        )

    def handle(self, *args, **options):
        skip_job = options["skip_job_row"]
        job_id = uuid.uuid4()
        job_row = None
        if not skip_job:
            job_row = Job.objects.create(
                tenant=None,
                type=JobType.API_KEY_ROTATION_REMINDER,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                resource_type="SYSTEM",
                resource_id=job_id,
                started_at=timezone.now(),
            )
        counters: dict[str, int] = {}
        try:
            counters = run_api_key_rotation_reminder_scan()
            self.stdout.write(
                self.style.SUCCESS(f"API key rotation reminder scan: {counters}")
            )
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
