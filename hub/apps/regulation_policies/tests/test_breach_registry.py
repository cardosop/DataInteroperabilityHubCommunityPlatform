"""Phase 232.3 — breach statutory clock + supervisory routing (YAML-backed)."""

from __future__ import annotations
import pytest

import pytest
from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone

from hub.apps.regulation_policies.registry import (
    breach_statutory_clock_matrix,
    breach_notification_routing_map,
    compute_breach_supervisory_deadline_utc,
    merge_breach_incident_sla_windows,
    resolve_breach_supervisory_authority_ids,
)


class BreachRegistryTests(TestCase):
    @pytest.mark.integration
    def test_routing_map_non_empty_for_configured_regimes(self):
        m = breach_notification_routing_map()
        self.assertIn("GDPR", m)
        self.assertIn("ICO_UK", m["UK_GDPR"])

    @pytest.mark.integration
    def test_resolve_authorities_unknown_falls_back_to_gdpr(self):
        ids = resolve_breach_supervisory_authority_ids("UNKNOWN_REGIME_X")
        self.assertEqual(ids, resolve_breach_supervisory_authority_ids("GDPR"))

    @pytest.mark.integration
    def test_breach_matrix_has_supervisory_hours(self):
        mx = breach_statutory_clock_matrix("GDPR")
        self.assertGreater(mx["supervisory_notification_hours"], 0)
        self.assertGreater(mx["sla_warn_hours_before_deadline"], 0)

    @pytest.mark.integration
    def test_compute_deadline_is_min_across_regimes(self):
        # Django 5+ removed ``django.utils.timezone.utc``; use stdlib
        # ``datetime.timezone.utc`` instead.
        discovered = datetime(2026, 5, 1, 12, 0, tzinfo=dt_timezone.utc)
        d = compute_breach_supervisory_deadline_utc(discovered, ("GDPR", "LGPD"))
        g = breach_statutory_clock_matrix("GDPR")
        l = breach_statutory_clock_matrix("LGPD")
        expect_min = discovered + timedelta(
            hours=min(
                int(g["supervisory_notification_hours"]),
                int(l["supervisory_notification_hours"]),
            )
        )
        self.assertEqual(d, expect_min)

    @pytest.mark.integration
    def test_merge_sla_windows_uses_strictest_hours_before_deadline(self):
        merged = merge_breach_incident_sla_windows(["GDPR", "LGPD"])
        g = breach_statutory_clock_matrix("GDPR")
        l = breach_statutory_clock_matrix("LGPD")
        self.assertEqual(
            merged["sla_warn_hours_before_deadline"],
            min(
                float(g["sla_warn_hours_before_deadline"]),
                float(l["sla_warn_hours_before_deadline"]),
            ),
        )
        self.assertEqual(
            merged["sla_alert_hours_before_deadline"],
            min(
                float(g["sla_alert_hours_before_deadline"]),
                float(l["sla_alert_hours_before_deadline"]),
            ),
        )
