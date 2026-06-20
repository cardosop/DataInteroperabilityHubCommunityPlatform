"""
Phase 274.6.6 — registry purge regression test.

Asserts that the 28-rule registration still works after the Phase 274.6
purge.  NotImplementedError tests for deleted methods now live in
test_registry.py.
"""

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class TestRegistryPurge(TestCase):
    """Phase 274.6 — existing registration still functions after purge."""

    def setUp(self):
        from hub.apps.core.business_rules.registry import get_registry

        self.registry = get_registry()

    def test_register_still_works(self):
        """Existing registration decorator still functions."""
        rule = self.registry.get_rule("marketplace_validation")
        assert rule is not None, "marketplace_validation must still be registered"
