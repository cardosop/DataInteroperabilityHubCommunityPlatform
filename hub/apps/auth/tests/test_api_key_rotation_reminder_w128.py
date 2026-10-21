"""
W12.8 (oss-release-remediation) — api_key_rotation_reminder veracity pins.

The named liar: the sweep's docstring claimed "idempotency is enforced
via ``APIKey.last_rotation_reminder_at``" while the guard was
check-then-act — the email went out BEFORE the timestamp was saved,
with no row lock, so two simultaneous sweeps (or a crash between the
send and the save) double-sent.  Root fix: the guard check + timestamp
write now run under a ``select_for_update`` row lock, and the email is
sent AFTER the claim commits — claim-then-send, at-most-once per
threshold crossing (matching the pre-existing best-effort send: a
failed send is not retried).

Pins run against the REAL sweep with the REAL locmem email backend
(no mocks): the serialization property is observable through
``django.core.mail.outbox`` while a sibling transaction holds the key
row lock, and a concurrent double-sweep delivers exactly one email.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import timedelta

import pytest
from django.core import mail
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from hub.apps.auth.management.commands.api_key_rotation_reminder import (
    run_api_key_rotation_reminder_scan,
)
from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant

pytestmark = [pytest.mark.django_db]


def _make_scan_env(test_case):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Reminder W128 {uid}",
        slug=f"reminder-w128-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    test_case.tenant = tenant
    test_case.now = timezone.now()
    test_case.key = APIKey.objects.create(
        tenant=tenant,
        user=None,
        customer_email=f"ops-{uid}@example.com",
        key_hash=APIKey.hash_key(APIKey.generate_key()),
        name=f"w128-key-{uid[:6]}",
        expires_at=test_case.now + timedelta(days=7),
    )
    return tenant


class ScanDocClaimTest(TestCase):
    """The docstring must state the REAL contract."""

    def test_docstring_claims_the_atomic_claim(self):
        import inspect

        from hub.apps.auth.management.commands import api_key_rotation_reminder

        doc = inspect.getdoc(api_key_rotation_reminder.run_api_key_rotation_reminder_scan)
        assert "select_for_update" in doc, (
            "the docstring must state the guard runs under a "
            "select_for_update row lock"
        )
        assert "at-most-once" in doc, (
            "the docstring must state the at-most-once semantics of the "
            "claim-then-send order"
        )


@override_settings(API_KEY_ROTATION_REMINDER_DAYS=[30, 14, 7, 1])
class SweepSerializationTest(TransactionTestCase):
    """The guard is serialized on the key row (the RED property)."""

    reset_sequences = True

    def setUp(self):
        _make_scan_env(self)

    def test_sweep_blocks_while_a_sibling_holds_the_key_row_lock(self):
        # Sibling transaction holds the key row lock without changing it.
        holder_done = threading.Event()
        holder_error: list[BaseException] = []

        def hold_lock():
            try:
                with transaction.atomic():
                    APIKey.objects.select_for_update().get(pk=self.key.pk)
                    holder_done.set()
                    time.sleep(0.6)  # noqa: sleep-needed  # INTENTIONAL: holds the select_for_update row lock while the sibling thread races the reminder update
            except BaseException as exc:  # noqa: BLE001 — thread boundary
                holder_error.append(exc)
                holder_done.set()

        holder = threading.Thread(target=hold_lock, daemon=True)
        holder.start()
        assert holder_done.wait(timeout=10), "holder failed to take the lock"

        result_holder: dict = {}

        def sweep():
            result_holder["counters"] = run_api_key_rotation_reminder_scan(
                now=self.now, tenant_id=str(self.tenant.id)
            )

        sweeper = threading.Thread(target=sweep, daemon=True)
        sweeper.start()

        # While the holder's transaction is open, the sweep's atomic claim
        # must be BLOCKED on the row lock — no email may go out.
        sweeper.join(timeout=0.3)
        assert not result_holder, "the sweep completed without waiting for the row lock"
        assert len(mail.outbox) == 0, (
            "an email went out while a sibling transaction held the key "
            "row lock — the guard is not serialized"
        )

        holder.join(timeout=10)
        assert not holder_error, holder_error
        sweeper.join(timeout=10)
        assert result_holder.get("counters", {}).get("reminder_7d") == 1
        assert len(mail.outbox) == 1

    def test_concurrent_double_sweep_delivers_exactly_one_email(self):
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def sweep():
            try:
                barrier.wait(timeout=10)
                run_api_key_rotation_reminder_scan(
                    now=self.now, tenant_id=str(self.tenant.id)
                )
            except BaseException as exc:  # noqa: BLE001 — thread boundary
                errors.append(exc)

        threads = [threading.Thread(target=sweep, daemon=True) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, errors
        assert len(mail.outbox) == 1, (
            f"concurrent sweeps delivered {len(mail.outbox)} emails — "
            f"the row-lock claim must admit exactly one"
        )
        self.key.refresh_from_db()
        assert self.key.last_rotation_reminder_at is not None
