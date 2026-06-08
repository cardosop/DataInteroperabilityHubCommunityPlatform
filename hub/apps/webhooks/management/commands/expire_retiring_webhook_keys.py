"""
Phase 233.1 — expire_retiring_webhook_keys hourly cron.

Pins REQ-WH-ROT-004 (hourly retiring → retired transition with shared
distributed-lock primitive) + the 7-day auto-prune half of REQ-WH-ROT-001.

Two operations per run, both inside the same Redis distributed lock so
two concurrent runs cannot double-finalise:

1. Transition every ``WebhookSigningKey`` whose ``status=RETIRING`` and
   ``retired_at <= now()`` to ``status=RETIRED``. Emit one
   ``WEBHOOK_KEY_RETIRED`` audit row per affected key.

2. Auto-prune every ``WebhookSigningKey`` whose ``status=RETIRED`` and
   ``retired_at < now() - interval '7 days'`` (REQ-WH-ROT-001
   "Auto-prune sweeps retired keys after 7 days"). The prune is
   idempotent — re-running the command against an already-pruned key
   is a no-op.

Lock semantics mirror ``purge_deleted_files``: SET NX with tokenised
release via Lua compare-and-del. Lock TTL = 30 minutes — generous
enough for a slow batch but short enough that a crashed run frees the
lock before the next hourly tick.
"""
from __future__ import annotations
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


# Distributed-lock key — versioned so a future schema change to the
# rotation lifecycle (e.g. tighter overlap window) can re-key without
# colliding with in-flight runs of the old version.
_EXPIRE_LOCK_KEY = "meshant:expire_retiring_webhook_keys:v1"

# Auto-prune retention — REQ-WH-ROT-001 "7 days after retired_at".
_AUTO_PRUNE_RETENTION = timedelta(days=7)


class Command(BaseCommand):
    help = (
        "Phase 233.1 — transition retiring webhook signing keys to retired "
        "and auto-prune retired keys older than 7 days. Idempotent. "
        "Acquires a Redis distributed lock so two concurrent runs cannot "
        "double-finalise."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Identify keys that WOULD transition or be pruned, but make "
                "no database changes."
            ),
        )

    def handle(self, *args, **options) -> None:
        dry_run = bool(options.get("dry_run", False))

        from hub.apps.api.middleware.idempotency_utils import get_redis_client
        from hub.apps.core.distributed_lock import (
            distributed_lock_acquire,
            distributed_lock_release,
        )

        try:
            redis_client = get_redis_client()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Redis unavailable: {exc}"))
            sys.exit(2)

        acquired, lock_token = distributed_lock_acquire(
            redis_client,
            _EXPIRE_LOCK_KEY,
            ttl_seconds=1800,  # 30 min — generous for a slow batch
            wait_seconds=5,
            retry_interval_seconds=0.1,
        )
        if not acquired:
            self.stderr.write(
                self.style.ERROR(
                    "Another expire_retiring_webhook_keys instance holds "
                    "the distributed lock; exiting."
                )
            )
            sys.exit(1)

        try:
            transitions, prunes = self._run(dry_run=dry_run)
        finally:
            distributed_lock_release(
                redis_client,
                _EXPIRE_LOCK_KEY,
                token=lock_token,
            )

        verb_t = "would transition" if dry_run else "transitioned"
        verb_p = "would prune" if dry_run else "pruned"
        self.stdout.write(
            self.style.SUCCESS(
                f"expire_retiring_webhook_keys: {verb_t} {transitions} "
                f"retiring → retired; {verb_p} {prunes} retired key(s) "
                f"older than 7 days."
            )
        )

    @staticmethod
    def _run(*, dry_run: bool) -> tuple[int, int]:
        """Run both passes (transition + auto-prune) and return their counts.

        Each pass runs under its own ``transaction.atomic`` so a failure
        in pass 2 does not roll back pass 1's audited transitions.
        """
        from hub.apps.audit import event_types as audit_event_types
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.webhooks.models import (
            WebhookSigningKey,
            WebhookSigningKeyStatus,
        )

        now = timezone.now()
        transitions = 0
        prunes = 0

        # -----------------------------------------------------------------
        # Pass 1 — RETIRING → RETIRED for keys whose 24h overlap has lapsed.
        #
        # 233.1.R1 GAP-A — eager-load ``webhook.tenant`` via
        # ``select_related`` so the per-iteration audit emission
        # (``tenant=key.webhook.tenant``) does NOT trigger an N+1
        # JOIN cascade. With a fleet of webhooks all rotating on the
        # same daily cycle, a batch of N keys would otherwise produce
        # 2N additional queries (one for ``key.webhook`` lookup, one
        # for ``webhook.tenant``). The ``select_related`` fetches all
        # three rows per key in a single SELECT.
        # -----------------------------------------------------------------
        with transaction.atomic():
            ready_to_retire = list(
                WebhookSigningKey.objects.select_for_update()
                .select_related("webhook", "webhook__tenant")
                .filter(
                    status=WebhookSigningKeyStatus.RETIRING,
                    retired_at__lte=now,
                )
                .order_by("retired_at")
            )

            for key in ready_to_retire:
                if not dry_run:
                    key.status = WebhookSigningKeyStatus.RETIRED
                    # Stamp the ACTUAL transition timestamp; the prior
                    # ``retired_at`` was the SCHEDULED transition target.
                    # Distinguishing the two would require a third
                    # column — for the operational use case (auto-prune
                    # after 7d) the scheduled timestamp is sufficient
                    # because the prune is bounded by "retired_at
                    # < now() - 7d" and the scheduled target is at
                    # most ``now() - retain - 24h`` once we get here.
                    key.save(update_fields=["status"])

                    # Audit row commits in the same transaction as the
                    # state change (REQ-WH-ROT-006 pattern, applied to
                    # the cron path as well).
                    create_audit_event(
                        resource_type="WEBHOOK",
                        action=audit_event_types.WEBHOOK_KEY_RETIRED,
                        actor_user=None,
                        tenant=key.webhook.tenant,
                        resource_id=str(key.webhook_id),
                        details={
                            "webhook_id": str(key.webhook_id),
                            "key_id": str(key.key_id),
                            "scheduled_retired_at": (
                                key.retired_at.isoformat()
                                if key.retired_at else None
                            ),
                            "actual_retired_at": now.isoformat(),
                        },
                    )
                transitions += 1

        # -----------------------------------------------------------------
        # Pass 2 — auto-prune RETIRED keys older than 7 days
        # (REQ-WH-ROT-001 invariant).
        # -----------------------------------------------------------------
        prune_cutoff = now - _AUTO_PRUNE_RETENTION
        with transaction.atomic():
            stale = (
                WebhookSigningKey.objects.select_for_update()
                .filter(
                    status=WebhookSigningKeyStatus.RETIRED,
                    retired_at__lt=prune_cutoff,
                )
            )
            if dry_run:
                prunes = stale.count()
            else:
                # ``delete()`` returns ``(count, {model_label: count})``.
                deleted_count, _ = stale.delete()
                prunes = int(deleted_count)

        return transitions, prunes
