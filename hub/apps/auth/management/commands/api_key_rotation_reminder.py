"""Daily API-key rotation reminder & expiry notification sweep (277.B.069)."""

from __future__ import annotations

import contextlib
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
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
    tenant_id=None,
) -> dict[str, int]:
    """
    Scan active API keys and send rotation/expiry reminders.

    Reminder thresholds are read from ``API_KEY_ROTATION_REMINDER_DAYS``
    (default: [30, 14, 7, 1]).  One reminder is sent per threshold
    crossing, and the claim is ATOMIC (W12.8): the guard check and the
    ``APIKey.last_rotation_reminder_at`` write run under a
    ``select_for_update`` row lock, so concurrent sweeps serialize and
    at most one reminder goes out per crossing.  The email is sent
    AFTER the claim commits — claim-then-send, at-most-once: a send
    failure is not retried (the send itself is best-effort), and a
    crash after the commit loses the reminder rather than duplicating
    it.

    ``tenant_id`` scopes the sweep to ONE tenant (ops: re-run a single
    tenant's reminder sweep; tests: isolate from other tenants' keys so the
    sweep is deterministic regardless of database state — the 2.3
    isolation fix).

    Returns a dict of counters keyed by outcome.
    """
    if now is None:
        now = timezone.now()

    thresholds: list[int] = getattr(settings, "API_KEY_ROTATION_REMINDER_DAYS", [30, 14, 7, 1])
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
    qs = APIKey.objects.filter(revoked_at__isnull=True, expires_at__isnull=False).select_related(
        "user", "tenant"
    )
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)

    for api_key in qs.iterator(chunk_size=200):
        counters["scanned"] += 1
        outcome = _sweep_one_key(api_key, now, thresholds)
        if outcome is None:
            continue
        if outcome == "already":
            counters["already_reminded"] += 1
        elif outcome == "expired":
            counters["expired"] += 1
        elif outcome == "no_recipient":
            counters["no_recipient"] += 1
        else:
            counters[f"reminder_{outcome}d"] += 1

    return counters


def _plan_reminder_claim(
    locked: APIKey,
    now,
    thresholds: list[int],
):
    """Decide + claim under the row lock; return the send plan.

    Returns None when there is nothing to do (outside every threshold
    window, or already reminded inside this window — no counter),
    ``("already",)`` for the expired-branch duplicate (the
    already_reminded counter), or
    ``("claim", locked, recipient, outcome, days_remaining)`` when the
    timestamp was just claimed and the email must go out AFTER the
    transaction commits.
    """
    days_remaining = (locked.expires_at - now).days  # may be negative

    # ── Expired keys ──────────────────────────────────────────────────
    if days_remaining < 0:
        # Notify once: last reminder was sent *before* expiry
        if not (
            locked.last_rotation_reminder_at is None
            or locked.last_rotation_reminder_at < locked.expires_at
        ):
            return ("already",)
        locked.last_rotation_reminder_at = now
        locked.save(update_fields=["last_rotation_reminder_at", "updated_at"])
        return ("claim", locked, _resolve_recipient(locked), "expired", None)

    # ── Upcoming expiry: tightest applicable threshold ────────────────
    # Smallest threshold >= days_remaining (the most urgent window the
    # key falls into).  Beyond every threshold — nothing to do.
    applicable = next((t for t in thresholds if days_remaining <= t), None)
    if applicable is None:
        return None

    # Reminded within this threshold window already?  When the last
    # reminder was sent, was the remaining time still GREATER than this
    # threshold?  If not, we have crossed into a new window and should
    # send.
    if locked.last_rotation_reminder_at is not None:
        days_at_last_reminder = (
            locked.expires_at - locked.last_rotation_reminder_at
        ).days
        if days_at_last_reminder <= applicable:
            return None

    locked.last_rotation_reminder_at = now
    locked.save(update_fields=["last_rotation_reminder_at", "updated_at"])
    return (
        "claim",
        locked,
        _resolve_recipient(locked),
        str(applicable),
        days_remaining,
    )


def _sweep_one_key(
    api_key: APIKey,
    now,
    thresholds: list[int],
) -> str | None:
    """Sweep ONE key with an atomic reminder claim (W12.8).

    The guard check and the ``last_rotation_reminder_at`` write run
    under a ``select_for_update`` row lock, so concurrent sweeps
    serialize and at most one reminder is sent per threshold crossing.
    The email send runs AFTER the claim commits — claim-then-send,
    at-most-once (matching the best-effort send: a failed send is not
    retried).

    Returns the counter outcome — "already" (expired branch only; the
    original counter semantics), "expired", "no_recipient", the
    threshold label ("30"/"14"/"7"/"1"), or None when the key is
    outside every threshold window or was deleted concurrently.
    """
    try:
        with transaction.atomic():
            locked = APIKey.objects.select_for_update().get(pk=api_key.pk)
            plan = _plan_reminder_claim(locked, now, thresholds)
    except APIKey.DoesNotExist:
        # Deleted between the iterator read and the claim.
        plan = None

    if plan is None:
        return None
    if plan[0] == "already":
        return "already"

    _kind, key, recipient, outcome, days_remaining = plan
    if recipient is None:
        return "no_recipient"
    if outcome == "expired":
        _send_expiry_email(key, recipient, now)
        return "expired"
    _send_expiring_email(key, recipient, days_remaining, now)
    return outcome


def _send_expiring_email(
    api_key: APIKey,
    recipient: str,
    days_remaining: int,
    _now,
) -> None:
    """Enqueue an API_KEY_EXPIRING notification."""
    from hub.apps.notifications.tasks import send_email_async

    # Best-effort: a single email failure must not abort the entire sweep
    with contextlib.suppress(Exception):
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


def _send_expiry_email(api_key: APIKey, recipient: str, _now) -> None:
    """Enqueue an API_KEY_EXPIRED notification."""
    from hub.apps.notifications.tasks import send_email_async

    with contextlib.suppress(Exception):
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


class Command(BaseCommand):
    help = "Scan API keys approaching expiry and send rotation reminders via email (277.B.069)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-job-row",
            action="store_true",
            help="Do not persist a Job row (useful for local smoke tests)",
        )

    def handle(self, *_args, **options):
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
            self.stdout.write(self.style.SUCCESS(f"API key rotation reminder scan: {counters}"))
            if job_row:
                job_row.mark_completed(result_json={"counters": counters})
        except Exception as exc:
            if job_row:
                job_row.mark_failed(str(exc))
            raise
