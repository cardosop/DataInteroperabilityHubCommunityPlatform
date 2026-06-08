"""Phase 232.8.8 — time-travel pattern for statutory deadline helpers (`freezegun`)."""

from __future__ import annotations
import pytest

import pytest
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone
from freezegun import freeze_time

from hub.apps.regulation_policies.registry import (
    compute_dsar_ack_deadline_utc,
    compute_dsar_fulfilment_deadline_utc,
)


class DsarDeadlineComputeFreezeTimeTests(SimpleTestCase):
    databases: set[str] = set()

    @freeze_time("2026-03-10T09:30:00Z")
    @pytest.mark.unit
    def test_compute_deadlines_anchor_on_frozen_now(self) -> None:
        now = timezone.now()
        ack = compute_dsar_ack_deadline_utc(now, ("GDPR",))
        fulfil = compute_dsar_fulfilment_deadline_utc(
            now, ("GDPR",), use_extension_path=False
        )
        self.assertEqual(ack, now + timedelta(hours=72))
        self.assertEqual(fulfil, now + timedelta(days=30))
