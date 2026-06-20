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
            RiskLevel.risk_ordinal(RiskLevel.NONE.value),
            RiskLevel.risk_ordinal(RiskLevel.HIGH.value),
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
        self.assertGreater(
            RiskLevel.risk_ordinal(None), RiskLevel.risk_ordinal(RiskLevel.CRITICAL.value)
        )
        self.assertTrue(RiskLevel.exceeds(RiskLevel.UNKNOWN.value, RiskLevel.HIGH.value))
        self.assertTrue(RiskLevel.exceeds("not-a-real-level", RiskLevel.LOW.value))

    @pytest.mark.unit
    def test_invalid_or_unknown_threshold_configuration_fails_closed(self):
        """Garbage / UNKNOWN threshold strings must block (never widen gates vs HIGH)."""
        self.assertTrue(RiskLevel.exceeds(RiskLevel.NONE.value, "NOT-A-THRESHOLD"))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.HIGH.value, ""))
        self.assertTrue(RiskLevel.exceeds(RiskLevel.MEDIUM.value, RiskLevel.UNKNOWN.value))

    @pytest.mark.unit
    def test_exceeds_none_level_fail_closed(self):
        """None level (e.g. nullable DB field) must exceed a real threshold."""
        self.assertTrue(
            RiskLevel.exceeds(None, RiskLevel.HIGH.value),
            "None level must exceed HIGH (fail-closed)",
        )

    @pytest.mark.unit
    def test_exceeds_none_threshold_fail_closed(self):
        """None threshold (e.g. missing config key) must be exceeded by any level."""
        self.assertTrue(
            RiskLevel.exceeds(RiskLevel.LOW.value, None),
            "LOW must exceed None threshold (fail-closed)",
        )

    @pytest.mark.unit
    def test_exceeds_none_both_fail_closed(self):
        """Both level and threshold None must still fail closed."""
        self.assertTrue(
            RiskLevel.exceeds(None, None),
            "None vs None must fail closed",
        )

    # ── Comprehensive ordinal / fail-closed truth table ────────────────

    @pytest.mark.unit
    def test_risk_ordinal_exact_values(self):
        """risk_ordinal returns the expected exact ordinal for each level."""
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.NONE.value), 0)
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.LOW.value), 1)
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.MEDIUM.value), 2)
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.HIGH.value), 3)
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.CRITICAL.value), 4)
        self.assertEqual(RiskLevel.risk_ordinal(RiskLevel.UNKNOWN.value), 5)

    @pytest.mark.unit
    def test_risk_ordinal_sentinels(self):
        """risk_ordinal returns sentinel 999 for None, empty, and unrecognised."""
        self.assertEqual(RiskLevel.risk_ordinal(None), 999)
        self.assertEqual(RiskLevel.risk_ordinal(""), 999)
        self.assertEqual(RiskLevel.risk_ordinal("BOGUS"), 999)

    @pytest.mark.unit
    def test_exceeds_full_fail_closed_truth_table(self):
        """Every combination of level × threshold behaves correctly.

        Concrete ordinal logic (higher > lower), plus fail-closed for
        UNKNOWN level, UNKNOWN/garbage threshold, and None values.
        """
        # ── Same-level cases ──────────────────────────────────────────
        for rl in ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertFalse(
                RiskLevel.exceeds(rl, rl), f"{rl} must not exceed itself"
            )
        # UNKNOWN vs UNKNOWN — fail-closed (threshold is UNKNOWN)
        self.assertTrue(RiskLevel.exceeds("UNKNOWN", "UNKNOWN"))

        # ── Lower vs higher (must NOT exceed) ─────────────────────────
        non_exceed_pairs = [
            ("NONE", "LOW"), ("NONE", "MEDIUM"), ("NONE", "HIGH"), ("NONE", "CRITICAL"),
            ("LOW", "MEDIUM"), ("LOW", "HIGH"), ("LOW", "CRITICAL"),
            ("MEDIUM", "HIGH"), ("MEDIUM", "CRITICAL"),
            ("HIGH", "CRITICAL"),
        ]
        for lower, higher in non_exceed_pairs:
            self.assertFalse(
                RiskLevel.exceeds(lower, higher),
                f"{lower} must NOT exceed {higher}",
            )

        # ── Higher vs lower (must exceed) ─────────────────────────────
        exceed_pairs = [
            ("LOW", "NONE"), ("MEDIUM", "NONE"), ("HIGH", "NONE"), ("CRITICAL", "NONE"),
            ("MEDIUM", "LOW"), ("HIGH", "LOW"), ("CRITICAL", "LOW"),
            ("HIGH", "MEDIUM"), ("CRITICAL", "MEDIUM"),
            ("CRITICAL", "HIGH"),
        ]
        for higher, lower in exceed_pairs:
            self.assertTrue(
                RiskLevel.exceeds(higher, lower),
                f"{higher} must exceed {lower}",
            )

        # ── UNKNOWN level exceeds everything ──────────────────────────
        for threshold in ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertTrue(
                RiskLevel.exceeds("UNKNOWN", threshold),
                f"UNKNOWN level must exceed {threshold} (fail-closed)",
            )

        # ── Everything exceeds UNKNOWN threshold ─────────────────────
        for level in ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            self.assertTrue(
                RiskLevel.exceeds(level, "UNKNOWN"),
                f"{level} must exceed UNKNOWN threshold (fail-closed)",
            )

        # ── Garbage threshold → fail-closed ──────────────────────────
        for garbage in ("", "BOGUS", "NOT-A-THRESHOLD"):
            self.assertTrue(
                RiskLevel.exceeds("NONE", garbage),
                f"NONE must exceed garbage threshold {garbage!r} (fail-closed)",
            )

        # ── Garbage level → fail-closed ──────────────────────────────
        for garbage in ("", "BOGUS", "not-a-real-level"):
            self.assertTrue(
                RiskLevel.exceeds(garbage, "LOW"),
                f"Garbage level {garbage!r} must exceed LOW (fail-closed)",
            )

        # ── None level → fail-closed ─────────────────────────────────
        self.assertTrue(RiskLevel.exceeds(None, "HIGH"))
        self.assertTrue(RiskLevel.exceeds(None, "LOW"))
        self.assertTrue(RiskLevel.exceeds(None, None))

        # ── None threshold → fail-closed ─────────────────────────────
        self.assertTrue(RiskLevel.exceeds("LOW", None))
        self.assertTrue(RiskLevel.exceeds("NONE", None))
