"""Phase 232.0 — regulation_policies registry (YAML + statutory defaults)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.test import TestCase

from hub.apps.regulation_policies.registry import (
    compute_dsar_ack_deadline_utc,
    compute_dsar_fulfilment_deadline_utc,
    data_retention_period_days_for_regime_keys,
    dsar_statutory_clock_matrix,
    get_authority_by_id,
    load_regulation_authorities,
    retention_defaults,
    statutory_deadlines_for,
)


class RegulationPoliciesRegistryTests(TestCase):
    @pytest.mark.integration
    def test_yaml_authority_ids_are_unique(self):
        authorities = load_regulation_authorities()
        ids = [a.id for a in authorities]
        self.assertEqual(len(ids), len(set(ids)))

    @pytest.mark.integration
    def test_yaml_loads_at_least_one_authority(self):
        authorities = load_regulation_authorities()
        self.assertGreaterEqual(len(authorities), 1)
        self.assertTrue(all(a.id and a.name and a.jurisdiction for a in authorities))

    @pytest.mark.integration
    def test_authority_lookup_ico(self):
        auth = get_authority_by_id("ICO_UK")
        self.assertIsNotNone(auth)
        assert auth is not None  # narrow for pyright
        self.assertEqual(auth.jurisdiction, "United Kingdom")

    @pytest.mark.integration
    def test_statutory_deadlines_gdpr_hours_not_zero(self):
        gdpr = statutory_deadlines_for("GDPR")
        self.assertGreater(gdpr["dsar_acknowledgement_hours"], 0)
        self.assertGreater(gdpr["breach_supervisory_authority_hours"], 0)

    @pytest.mark.integration
    def test_retention_defaults_align_with_audit_governance(self):
        rd = retention_defaults()
        self.assertGreaterEqual(rd["audit_event_retention_years_min"], 3)

    @pytest.mark.integration
    def test_dsar_clock_matrix_defaults_for_unknown_regime_follow_gdpr_pattern(self):
        mx = dsar_statutory_clock_matrix("UNKNOWN_JURISDICTION")
        gdpr = dsar_statutory_clock_matrix("GDPR")
        self.assertEqual(mx["fulfilment_calendar_days"], gdpr["fulfilment_calendar_days"])

    @pytest.mark.integration
    def test_compute_dsar_deadlines_ordering(self):
        # Django 5+ removed ``django.utils.timezone.utc``; stdlib
        # ``datetime.timezone.utc`` is the replacement.
        submitted = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
        ack = compute_dsar_ack_deadline_utc(submitted, ("LGPD", "GDPR"))
        fulfil = compute_dsar_fulfilment_deadline_utc(submitted, ("LGPD", "GDPR"))
        self.assertLess(ack, submitted + timedelta(days=7))
        self.assertLess(fulfil, submitted + timedelta(days=20))

    @pytest.mark.integration
    def test_data_retention_regime_keys_max_across_known_regimes(self):
        yrs = retention_defaults().get("audit_event_retention_years_min") or 3
        lgpd_fallback = int(yrs * 365)
        d = data_retention_period_days_for_regime_keys(["LGPD", "CUSTOM_STATE_REGIME"])
        self.assertEqual(d, max(1825, lgpd_fallback))

    @pytest.mark.integration
    def test_data_retention_period_empty_keys_returns_zero(self):
        self.assertEqual(data_retention_period_days_for_regime_keys([]), 0)

    @pytest.mark.integration
    def test_data_retention_gdpr_vs_ccpa_uses_strictest_horizon(self):
        d = data_retention_period_days_for_regime_keys(["GDPR", "CCPA"])
        self.assertEqual(d, 2555)
