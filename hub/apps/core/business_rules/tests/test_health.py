"""
Phase 274.16.12 — /health/business-rules endpoint test.
"""
from __future__ import annotations
import pytest

import pytest
from django.test import TestCase

from hub.apps.core.business_rules.health import (
    mark_rule_degraded,
    get_degraded_rules,
    clear_degraded_rules,
    health_check,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestBusinessRulesHealth(TestCase):
    def setUp(self):
        clear_degraded_rules()

    def tearDown(self):
        clear_degraded_rules()

    @pytest.mark.integration
    def test_healthy_when_no_degraded_rules(self):
        result = health_check()
        assert result["status"] == "HEALTHY"
        assert result["degraded_count"] == 0

    @pytest.mark.integration
    def test_degraded_when_rule_registration_fails(self):
        mark_rule_degraded("test_rule", "ImportError: module not found")
        result = health_check()
        assert result["status"] == "DEGRADED"
        assert "test_rule" in result["degraded_rules"]
        assert result["degraded_count"] == 1

    @pytest.mark.integration
    def test_clear_resets_degraded_rules(self):
        mark_rule_degraded("rule_x", "error")
        clear_degraded_rules()
        assert len(get_degraded_rules()) == 0
