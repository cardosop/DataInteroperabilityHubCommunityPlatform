"""Phase P.8 D4 — /api/v1/health/business-rules over HTTP.

The health handler existed in ``hub.apps.core.business_rules.health`` but
no URL configuration exposed it, and its test called the function
directly. Per the paid-runtime-integrity spec, endpoint tests SHALL
exercise the URL configuration, not only the underlying function: every
test here issues a real request through the route.
"""

from __future__ import annotations

from django.test import Client, TestCase
from django.urls import reverse

from hub.apps.core.business_rules.health import (
    clear_degraded_rules,
    mark_rule_degraded,
)

DOCUMENTED_PATH = "/api/v1/health/business-rules/"


class BusinessRulesHealthEndpointTests(TestCase):
    def setUp(self):
        clear_degraded_rules()
        self.client = Client()

    def tearDown(self):
        clear_degraded_rules()

    def test_healthy_payload_over_the_documented_path(self):
        response = self.client.get(DOCUMENTED_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "HEALTHY", "degraded_rules": [], "degraded_count": 0},
        )

    def test_degraded_payload_names_the_failed_rules(self):
        mark_rule_degraded("test_rule", "ImportError: module not found")
        response = self.client.get(DOCUMENTED_PATH)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "DEGRADED")
        self.assertEqual(payload["degraded_rules"], ["test_rule"])
        self.assertEqual(payload["degraded_count"], 1)

    def test_route_is_reversible_and_matches_the_documented_path(self):
        self.assertEqual(reverse("health-business-rules"), DOCUMENTED_PATH)

    def test_route_resolves_through_the_url_configuration(self):
        """The route must be found by the resolver (not only by the test
        client hitting the literal string)."""
        from django.urls import resolve

        match = resolve(DOCUMENTED_PATH)
        self.assertIsNotNone(match.func)
