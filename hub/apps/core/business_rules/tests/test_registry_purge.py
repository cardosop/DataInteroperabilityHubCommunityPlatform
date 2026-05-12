"""
Phase 274.6.6 — registry purge regression test.

Asserts that deleted methods raise NotImplementedError and
existing 28-rule registration still works after the purge.
"""
import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class TestRegistryPurge(TestCase):
    """Phase 274.6 — deleted methods raise NotImplementedError."""

    def setUp(self):
        from hub.apps.core.business_rules.registry import get_registry
        self.registry = get_registry()

    def test_execute_rules_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.registry.execute_rules()

    def test_enable_rule_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.registry.enable_rule("any_rule")

    def test_disable_rule_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.registry.disable_rule("any_rule")

    def test_register_instance_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self.registry.register_instance(object())

    def test_register_still_works(self):
        """Existing registration decorator still functions."""
        rule = self.registry.get_rule("marketplace_validation")
        assert rule is not None, "marketplace_validation must still be registered"
