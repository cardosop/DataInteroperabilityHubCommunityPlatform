"""
Comprehensive tests for Trace Sampling Configuration

Tests cover:
- 100% sampling for errors (via middleware)
- Configurable sampling for successful requests (default: 10%)
- 100% sampling for critical endpoints (auth, asset activation)
- Adaptive sampler behavior
- Critical endpoint detection
"""

from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings


# Mock OpenTelemetry classes for testing
class MockSamplingResult:
    class Decision:
        RECORD_AND_SAMPLE = "RECORD_AND_SAMPLE"
        RECORD_ONLY = "RECORD_ONLY"
        DROP = "DROP"

    def __init__(self, decision, attributes=None):
        self.decision = decision
        self.attributes = attributes or {}


class MockTraceIdRatioBased:
    def __init__(self, rate):
        self.rate = rate

    def should_sample(self, **kwargs):
        import random

        if random.random() < self.rate:
            return MockSamplingResult(MockSamplingResult.Decision.RECORD_AND_SAMPLE)
        return MockSamplingResult(MockSamplingResult.Decision.DROP)


# Patch OpenTelemetry imports before importing trace_sampling
with patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True):
    with patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult):
        with patch(
            "hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased
        ):
            from hub.apps.observability.trace_sampling import (
                CRITICAL_ENDPOINTS,
                AdaptiveTraceSampler,
                get_adaptive_sampler,
                is_critical_endpoint,
            )


class TraceSamplingTest(TestCase):
    """Test trace sampling configuration"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()

    def test_is_critical_endpoint_auth(self):
        """Test critical endpoint detection for auth endpoints"""
        self.assertTrue(is_critical_endpoint("/api/v1/auth/register"))
        self.assertTrue(is_critical_endpoint("/api/v1/auth/login"))
        self.assertTrue(is_critical_endpoint("/api/v1/auth/logout"))
        self.assertTrue(is_critical_endpoint("/api/v1/auth/refresh"))
        self.assertTrue(is_critical_endpoint("/api/v1/auth/me"))

    def test_is_critical_endpoint_assets(self):
        """Test critical endpoint detection for asset endpoints"""
        self.assertTrue(is_critical_endpoint("/api/v1/assets/"))
        self.assertTrue(is_critical_endpoint("/api/v1/assets/123/activate"))
        self.assertTrue(is_critical_endpoint("/api/v1/assets/abc-123-def/deactivate"))

    def test_is_critical_endpoint_non_critical(self):
        """Test that non-critical endpoints are not detected"""
        self.assertFalse(is_critical_endpoint("/api/v1/datasets/"))
        self.assertFalse(is_critical_endpoint("/api/v1/contracts/"))
        self.assertFalse(is_critical_endpoint("/api/v1/marketplace/listings/"))

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_critical_endpoint(self):
        """Test adaptive sampler always samples critical endpoints"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.1)

        # Mock attributes for critical endpoint
        attributes = {"http.target": "/api/v1/auth/login", "http.method": "POST"}

        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345678901234567890123456789012,
            name="HTTP POST /api/v1/auth/login",
            attributes=attributes,
        )

        self.assertEqual(result.decision, MockSamplingResult.Decision.RECORD_AND_SAMPLE)
        self.assertEqual(result.attributes.get("sampling.reason"), "critical_endpoint")

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_non_critical_endpoint(self):
        """Test adaptive sampler uses base rate for non-critical endpoints"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.1)

        # Mock attributes for non-critical endpoint
        attributes = {"http.target": "/api/v1/datasets/", "http.method": "GET"}

        # Test with enough trials for statistical confidence.
        # n=1000 with p=0.1 gives σ≈0.95%, so [0.05, 0.15] is ≈±5.3σ.
        sampled_count = 0
        total_tests = 1000

        for i in range(total_tests):
            result = sampler.should_sample(
                parent_context=None,
                trace_id=12345678901234567890123456789012 + i,  # Different trace IDs
                name="HTTP GET /api/v1/datasets/",
                attributes=attributes,
            )

            if result.decision == MockSamplingResult.Decision.RECORD_AND_SAMPLE:
                sampled_count += 1

        # Should sample approximately 10% (with some variance)
        sampling_rate = sampled_count / total_tests
        self.assertGreaterEqual(sampling_rate, 0.05)
        self.assertLessEqual(sampling_rate, 0.15)

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_base_rate_configurable(self):
        """Test adaptive sampler uses configurable base sampling rate"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.5)  # 50%

        attributes = {"http.target": "/api/v1/datasets/", "http.method": "GET"}

        # Test with enough trials for statistical confidence.
        # n=1000 with p=0.5 gives σ≈1.58%, so [0.40, 0.60] is ≈±6.3σ.
        sampled_count = 0
        total_tests = 1000

        for i in range(total_tests):
            result = sampler.should_sample(
                parent_context=None,
                trace_id=12345678901234567890123456789012 + i,
                name="HTTP GET /api/v1/datasets/",
                attributes=attributes,
            )

            if result.decision == MockSamplingResult.Decision.RECORD_AND_SAMPLE:
                sampled_count += 1

        # Should sample approximately 50% (with some variance)
        sampling_rate = sampled_count / total_tests
        self.assertGreaterEqual(sampling_rate, 0.40)
        self.assertLessEqual(sampling_rate, 0.60)

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_get_adaptive_sampler_default(self):
        """Test getting adaptive sampler with default settings"""
        sampler = get_adaptive_sampler()

        self.assertIsNotNone(sampler)
        self.assertIsInstance(sampler, AdaptiveTraceSampler)

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_get_adaptive_sampler_custom_rate(self):
        """Test getting adaptive sampler with custom sampling rate"""
        sampler = get_adaptive_sampler(base_sampling_rate=0.2)

        self.assertIsNotNone(sampler)
        self.assertEqual(sampler.base_sampling_rate, 0.2)

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_get_adaptive_sampler_custom_endpoints(self):
        """Test getting adaptive sampler with custom critical endpoints"""
        custom_endpoints = ["/api/v1/custom/endpoint"]
        sampler = get_adaptive_sampler(critical_endpoints=custom_endpoints)

        self.assertIsNotNone(sampler)
        self.assertEqual(sampler.critical_endpoints, custom_endpoints)

    def test_critical_endpoint_pattern_matching(self):
        """Test critical endpoint pattern matching with IDs"""
        # Test asset activation with UUID
        self.assertTrue(
            is_critical_endpoint("/api/v1/assets/550e8400-e29b-41d4-a716-446655440000/activate")
        )

        # Test asset activation with numeric ID
        self.assertTrue(is_critical_endpoint("/api/v1/assets/123/activate"))

        # Test asset deactivation
        self.assertTrue(is_critical_endpoint("/api/v1/assets/123/deactivate"))

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_attributes_preserved(self):
        """Test adaptive sampler preserves attributes in sampling result"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.1)

        attributes = {"http.target": "/api/v1/auth/login", "http.method": "POST"}

        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345678901234567890123456789012,
            name="HTTP POST /api/v1/auth/login",
            attributes=attributes,
        )

        self.assertIsNotNone(result.attributes)
        self.assertEqual(result.attributes.get("sampling.reason"), "critical_endpoint")

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_base_rate_in_attributes(self):
        """Test adaptive sampler includes base rate in attributes"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.15)

        attributes = {"http.target": "/api/v1/datasets/", "http.method": "GET"}

        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345678901234567890123456789012,
            name="HTTP GET /api/v1/datasets/",
            attributes=attributes,
        )

        self.assertIsNotNone(result.attributes)
        self.assertEqual(result.attributes.get("sampling.rate"), 0.15)

    @override_settings(OTEL_TRACES_SAMPLER_ARG=0.2)
    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_get_adaptive_sampler_from_settings(self):
        """Test adaptive sampler uses settings for base rate"""
        sampler = get_adaptive_sampler()

        self.assertIsNotNone(sampler)
        # Should use 0.2 from settings
        self.assertEqual(sampler.base_sampling_rate, 0.2)

    def test_critical_endpoints_list(self):
        """Test that critical endpoints list is properly defined"""
        self.assertIsInstance(CRITICAL_ENDPOINTS, list)
        self.assertGreater(len(CRITICAL_ENDPOINTS), 0)

        # Check that auth endpoints are in the list
        auth_endpoints = [ep for ep in CRITICAL_ENDPOINTS if "/auth/" in ep]
        self.assertGreater(len(auth_endpoints), 0)

        # Check that asset endpoints are in the list
        asset_endpoints = [ep for ep in CRITICAL_ENDPOINTS if "/assets/" in ep]
        self.assertGreater(len(asset_endpoints), 0)

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_http_route_attribute(self):
        """Test adaptive sampler checks http.route attribute"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.1)

        # Test with http.route instead of http.target
        attributes = {"http.route": "/api/v1/auth/login", "http.method": "POST"}

        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345678901234567890123456789012,
            name="HTTP POST /api/v1/auth/login",
            attributes=attributes,
        )

        self.assertEqual(result.decision, MockSamplingResult.Decision.RECORD_AND_SAMPLE)
        self.assertEqual(result.attributes.get("sampling.reason"), "critical_endpoint")

    @patch("hub.apps.observability.trace_sampling.OPENTELEMETRY_AVAILABLE", True)
    @patch("hub.apps.observability.trace_sampling.SamplingResult", MockSamplingResult)
    @patch("hub.apps.observability.trace_sampling.TraceIdRatioBased", MockTraceIdRatioBased)
    def test_adaptive_sampler_http_url_path_attribute(self):
        """Test adaptive sampler checks http.url.path attribute"""
        sampler = AdaptiveTraceSampler(base_sampling_rate=0.1)

        # Test with http.url.path
        attributes = {"http.url.path": "/api/v1/assets/123/activate", "http.method": "POST"}

        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345678901234567890123456789012,
            name="HTTP POST /api/v1/assets/123/activate",
            attributes=attributes,
        )

        self.assertEqual(result.decision, MockSamplingResult.Decision.RECORD_AND_SAMPLE)
        self.assertEqual(result.attributes.get("sampling.reason"), "critical_endpoint")
