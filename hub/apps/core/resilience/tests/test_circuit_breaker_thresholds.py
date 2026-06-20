"""
Tests for ``hub.apps.core.resilience.circuit_breaker_thresholds``.

Validates production thresholds, threshold lookup, validation rules,
and JSON serialisation — no external dependencies.
"""

import json

from django.test import SimpleTestCase

from hub.apps.core.resilience.circuit_breaker_thresholds import (
    PRODUCTION_THRESHOLDS,
    CircuitBreakerThreshold,
    get_default_threshold,
    get_threshold,
    thresholds_as_dict,
    validate_all_thresholds,
    validate_threshold,
)


class CircuitBreakerThresholdDataclassTests(SimpleTestCase):
    """Tests for the CircuitBreakerThreshold frozen dataclass."""

    def test_constructs_with_required_fields(self):
        t = CircuitBreakerThreshold(
            service_name="test-svc",
            failure_threshold=5,
            timeout_seconds=60,
        )
        assert t.service_name == "test-svc"
        assert t.failure_threshold == 5
        assert t.timeout_seconds == 60
        assert t.success_threshold == 2  # default

    def test_is_immutable(self):
        t = CircuitBreakerThreshold("svc", 5, 60)
        with self.assertRaises(Exception):
            t.failure_threshold = 10  # type: ignore[misc]

    def test_optional_fields_default(self):
        t = CircuitBreakerThreshold("svc", 5, 60)
        assert t.rationale == ""
        assert t.exercised_by_journey == ""

    def test_all_fields_populated(self):
        t = CircuitBreakerThreshold(
            service_name="svc",
            failure_threshold=8,
            timeout_seconds=120,
            success_threshold=3,
            rationale="because",
            exercised_by_journey="my-journey",
        )
        assert t.rationale == "because"
        assert t.exercised_by_journey == "my-journey"


class ProductionThresholdsTests(SimpleTestCase):
    """Validate the PRODUCTION_THRESHOLDS registry."""

    def test_all_registered_services_have_valid_thresholds(self):
        """Every registered threshold passes validation."""
        violations = validate_all_thresholds()
        assert violations == [], f"Production thresholds have violations: {violations}"

    def test_services_registered_count(self):
        """Verify exact number of production services are registered.
        An exact count forces review of additions/removals."""
        assert len(PRODUCTION_THRESHOLDS) == 12, (
            f"Expected 12 production thresholds, got {len(PRODUCTION_THRESHOLDS)}. "
            "If services were added/removed, update this count."
        )

    def test_service_names_match_key(self):
        """Each threshold dict key matches the threshold.service_name."""
        for key, threshold in PRODUCTION_THRESHOLDS.items():
            assert threshold.service_name == key, (
                f"Mismatch: key={key!r}, service_name={threshold.service_name!r}"
            )

    def test_every_service_has_rationale(self):
        """Every production threshold documents its rationale."""
        for name, t in PRODUCTION_THRESHOLDS.items():
            assert t.rationale, f"{name} missing rationale"

    def test_every_service_has_journey(self):
        """Every production threshold is linked to a k6 journey."""
        for name, t in PRODUCTION_THRESHOLDS.items():
            assert t.exercised_by_journey, f"{name} missing exercised_by_journey"


class GetThresholdTests(SimpleTestCase):
    """Tests for get_threshold()."""

    def test_returns_correct_threshold_for_registered_service(self):
        t = get_threshold("compliance-service")
        assert t is not None
        assert t.service_name == "compliance-service"
        assert t.failure_threshold == 5
        assert t.timeout_seconds == 120

    def test_returns_none_for_unregistered_service(self):
        assert get_threshold("nonexistent-service") is None


class GetDefaultThresholdTests(SimpleTestCase):
    """Tests for get_default_threshold()."""

    def test_default_has_safe_values(self):
        t = get_default_threshold()
        assert t.failure_threshold == 5
        assert t.timeout_seconds == 60
        assert t.success_threshold == 2
        assert t.service_name == "default"


class ValidateThresholdTests(SimpleTestCase):
    """Tests for validate_threshold()."""

    def test_valid_threshold_produces_no_violations(self):
        t = CircuitBreakerThreshold("svc", failure_threshold=5, timeout_seconds=60)
        assert validate_threshold(t) == []

    def test_catches_low_failure_threshold(self):
        t = CircuitBreakerThreshold("svc", failure_threshold=2, timeout_seconds=60)
        violations = validate_threshold(t)
        assert any("failure_threshold" in v for v in violations)

    def test_failure_threshold_of_3_is_valid(self):
        t = CircuitBreakerThreshold("svc", failure_threshold=3, timeout_seconds=60)
        violations = validate_threshold(t)
        assert not any("failure_threshold" in v for v in violations)

    def test_catches_low_timeout(self):
        t = CircuitBreakerThreshold("svc", failure_threshold=5, timeout_seconds=29)
        violations = validate_threshold(t)
        assert any("timeout_seconds" in v for v in violations)

    def test_timeout_seconds_of_30_is_valid(self):
        t = CircuitBreakerThreshold("svc", failure_threshold=5, timeout_seconds=30)
        violations = validate_threshold(t)
        assert not any("timeout_seconds" in v for v in violations)

    def test_catches_zero_success_threshold(self):
        t = CircuitBreakerThreshold(
            "svc", failure_threshold=5, timeout_seconds=60, success_threshold=0
        )
        violations = validate_threshold(t)
        assert any("success_threshold" in v for v in violations)

    def test_multiple_violations_reported(self):
        t = CircuitBreakerThreshold(
            "svc", failure_threshold=1, timeout_seconds=10, success_threshold=0
        )
        violations = validate_threshold(t)
        assert len(violations) == 3


class ThresholdsAsDictTests(SimpleTestCase):
    """Tests for thresholds_as_dict()."""

    def test_returns_dict_with_expected_keys(self):
        d = thresholds_as_dict()
        assert isinstance(d, dict)
        for _name, entry in d.items():
            assert "failure_threshold" in entry
            assert "timeout_seconds" in entry
            assert "success_threshold" in entry

    def test_json_serializable(self):
        d = thresholds_as_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 0
        roundtrip = json.loads(json_str)
        assert isinstance(roundtrip, dict)
