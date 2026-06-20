"""
280.B.2.3 — Tests for Circuit Breaker Thresholds.

Validates:
- All production service thresholds are within safe bounds
- Default threshold is valid
- validate_threshold catches violations
- Each threshold has a documented rationale
- Services map to corresponding k6 load test journeys
"""

import pytest


class TestCircuitBreakerThresholds:
    """Validate the production circuit breaker threshold configuration."""

    @pytest.fixture(scope="class")
    def thresholds(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            PRODUCTION_THRESHOLDS,
        )

        assert len(PRODUCTION_THRESHOLDS) >= 12, (
            f"Expected >=12 service thresholds, got {len(PRODUCTION_THRESHOLDS)}"
        )
        return PRODUCTION_THRESHOLDS

    @pytest.fixture(scope="class")
    def default_threshold(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            get_default_threshold,
        )

        return get_default_threshold()

    # ── Threshold safety bounds ───────────────────────────────────────

    def test_all_failure_thresholds_above_minimum(self, thresholds):
        """No service may have failure_threshold < 3."""
        for name, t in thresholds.items():
            assert t.failure_threshold >= 3, (
                f"{name}: failure_threshold={t.failure_threshold} < 3 (minimum)"
            )

    def test_all_timeout_seconds_above_minimum(self, thresholds):
        """No service may have timeout_seconds < 30."""
        for name, t in thresholds.items():
            assert t.timeout_seconds >= 30, (
                f"{name}: timeout_seconds={t.timeout_seconds} < 30 (minimum)"
            )

    def test_all_success_thresholds_positive(self, thresholds):
        """No service may have success_threshold < 1."""
        for name, t in thresholds.items():
            assert t.success_threshold >= 1, f"{name}: success_threshold={t.success_threshold} < 1"

    def test_external_services_have_longer_timeouts(self, thresholds):
        """External services (Stripe, email) must have >= 300s timeout."""
        external_services = {"stripe_api", "email_provider"}
        for name, t in thresholds.items():
            if name in external_services:
                assert t.timeout_seconds >= 300, (
                    f"{name}: external service must have timeout >= 300s, got {t.timeout_seconds}s"
                )

    def test_external_services_have_stricter_success_threshold(self, thresholds):
        """Stripe (payment-critical) must require 3 successes to close."""
        stripe = thresholds.get("stripe_api")
        if stripe:
            assert stripe.success_threshold == 3, (
                f"stripe_api must have success_threshold=3 for payment safety, "
                f"got {stripe.success_threshold}"
            )

    # ── Threshold completeness ────────────────────────────────────────

    def test_all_thresholds_have_rationale(self, thresholds):
        """Every service threshold must document its rationale."""
        for name, t in thresholds.items():
            assert t.rationale, f"{name}: missing rationale"
            assert len(t.rationale) > 20, f"{name}: rationale too short ({len(t.rationale)} chars)"

    def test_all_thresholds_have_exercised_by_journey(self, thresholds):
        """Every service must reference which k6 journey exercises it."""
        for name, t in thresholds.items():
            assert t.exercised_by_journey, f"{name}: missing exercised_by_journey"

    def test_key_services_defined(self, thresholds):
        """Critical services must have configured thresholds."""
        required = {
            "compliance-service",
            "dq-service",
            "semantic-service",
            "search-service",
            "webhook-delivery",
            "stripe_api",
            "email_provider",
            "file-upload-s3",
            "asset-service",
            "contract-service",
            "marketplace-service",
            "governance-service",
        }
        missing = required - set(thresholds.keys())
        assert not missing, f"Missing thresholds for critical services: {missing}"

    def test_k6_journey_references_are_valid(self, thresholds):
        """exercised_by_journey values must reference known k6 journeys."""
        VALID_JOURNEYS = {
            "login",
            "asset-crud",
            "contract-workflow",
            "marketplace",
            "search",
            "sparql",
            "file-upload",
            "compliance-scan",
            "governance",
            "webhook",
            "unknown",
        }
        for name, t in thresholds.items():
            assert t.exercised_by_journey in VALID_JOURNEYS, (
                f"{name}: exercised_by_journey='{t.exercised_by_journey}' "
                f"not in known journeys: {sorted(VALID_JOURNEYS)}"
            )

    # ── validate_threshold function ────────────────────────────────────

    def test_validate_threshold_catches_low_failure_threshold(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            CircuitBreakerThreshold,
            validate_threshold,
        )

        t = CircuitBreakerThreshold(
            service_name="test",
            failure_threshold=1,
            timeout_seconds=60,
            success_threshold=2,
        )
        violations = validate_threshold(t)
        assert len(violations) >= 1
        assert any("failure_threshold" in v for v in violations)

    def test_validate_threshold_catches_low_timeout(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            CircuitBreakerThreshold,
            validate_threshold,
        )

        t = CircuitBreakerThreshold(
            service_name="test",
            failure_threshold=5,
            timeout_seconds=10,
            success_threshold=2,
        )
        violations = validate_threshold(t)
        assert len(violations) >= 1
        assert any("timeout_seconds" in v for v in violations)

    def test_validate_threshold_catches_zero_success_threshold(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            CircuitBreakerThreshold,
            validate_threshold,
        )

        t = CircuitBreakerThreshold(
            service_name="test",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=0,
        )
        violations = validate_threshold(t)
        assert len(violations) >= 1
        assert any("success_threshold" in v for v in violations)

    def test_validate_threshold_passes_valid_config(self):
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            CircuitBreakerThreshold,
            validate_threshold,
        )

        t = CircuitBreakerThreshold(
            service_name="test",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
        )
        violations = validate_threshold(t)
        assert len(violations) == 0

    def test_validate_all_thresholds_has_no_violations(self):
        """All production thresholds must pass validation."""
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            validate_all_thresholds,
        )

        violations = validate_all_thresholds()
        assert not violations, (
            f"Production thresholds have {len(violations)} violation(s): {violations}"
        )

    # ── Default threshold ─────────────────────────────────────────────

    def test_default_threshold_is_safe(self):
        """Default threshold must meet minimum safety requirements."""
        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            get_default_threshold,
            validate_threshold,
        )

        dt = get_default_threshold()
        violations = validate_threshold(dt)
        assert not violations, f"Default threshold has violations: {violations}"

    def test_default_threshold_values(self, default_threshold):
        """Default threshold must use reasonable production-safe values."""
        assert default_threshold.failure_threshold == 5
        assert default_threshold.timeout_seconds == 60
        assert default_threshold.success_threshold == 2

    # ── JSON serialization ────────────────────────────────────────────

    def test_thresholds_as_dict_is_valid(self):
        """thresholds_as_dict must return a JSON-serializable structure."""
        import json

        from hub.apps.core.resilience.circuit_breaker_thresholds import (
            thresholds_as_dict,
        )

        d = thresholds_as_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 500
        # Round-trip
        parsed = json.loads(json_str)
        assert len(parsed) >= 12
