"""
Phase 231.2 — RiskLevel ordinal comparison for tenant compliance thresholds.

Real unit tests (no mocks): exercises ``RiskLevel.exceeds`` / ``RiskLevel.risk_ordinal``.
"""

import pytest

from django.test import SimpleTestCase

from hub.apps.compliance.models import RiskLevel


class RiskLevelExceedsTest(SimpleTestCase):
    @pytest.mark.unit
    def test_ordinal_ordering(self):
        self.assertLess(
            RiskLevel.risk_ordinal(RiskLevel.NONE.value), RiskLevel.risk_ordinal(RiskLevel.HIGH.value)
        )
        self.assertLess(
            RiskLevel.risk_ordinal(RiskLevel.HIGH.value),
            RiskLevel.risk_ordinal(RiskLevel.CRITICAL.value),
        )

    @pytest.mark.unit
    def test_exceeds_when_strictly_above_threshold(self):
        self.assertFalse(RiskLevel.exceeds(RiskLevel.HIGH.value, RiskLevel.HIGH.value))
        self.assertFalse(RiskLevel.exceeds(RiskLevel.MEDIUM.value, RiskLevel.HIGH.value))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.CRITICAL.value, RiskLevel.HIGH.value))

    @pytest.mark.unit
    def test_unknown_and_null_fail_closed(self):
        self.assertGreater(RiskLevel.risk_ordinal(None), RiskLevel.risk_ordinal(RiskLevel.CRITICAL.value))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.UNKNOWN.value, RiskLevel.HIGH.value))
        self.assertTrue(RiskLevel.exceeds("not-a-real-level", RiskLevel.LOW.value))

    @pytest.mark.unit
    def test_invalid_or_unknown_threshold_configuration_fails_closed(self):
        """Garbage / UNKNOWN threshold strings must block (never widen gates vs HIGH)."""
        self.assertTrue(RiskLevel.exceeds(RiskLevel.NONE.value, "NOT-A-THRESHOLD"))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.HIGH.value, ""))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.MEDIUM.value, RiskLevel.UNKNOWN.value))
