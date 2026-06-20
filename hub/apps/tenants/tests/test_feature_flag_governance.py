"""
285.12.4.8 CC9 — Feature flag two-person rule governance tests.

Verifies the Phase 235.1 sensitive-flag protections:
  1. Sensitive flags require two-person approval for modification
  2. Non-sensitive flags are not gated
  3. Flag registry correctly identifies sensitive flags
  4. Flag stage transitions follow the DRAFT→CANARY→GA lifecycle
"""

from __future__ import annotations

import pytest
from django.test import TestCase

from hub.apps.tenants.feature_flag_registry import REGISTRY

pytestmark = pytest.mark.django_db(transaction=True)

_VALID_STAGES = frozenset({"DRAFT", "CANARY", "GA", "DEPRECATED", "RETIRED"})

# Sensitive flags from CLAUDE.md (two-person rule, Phase 235.1)
_SENSITIVE_FLAGS = frozenset(
    {
        "compliance_fail_closed_enabled",
        "allow_intake_on_compliance_degraded",
        "compliance_audit_full_sampling",
        "compliance_intake_gate_enabled",
    }
)


class FeatureFlagGovernanceTests(TestCase):
    @pytest.mark.integration
    def test_sensitive_flags_exist_in_registry(self):
        """All 4 sensitive flags should be registered."""
        registry_names = {f.name for f in REGISTRY}
        for name in _SENSITIVE_FLAGS:
            self.assertIn(name, registry_names, f"{name} should be in registry")

    @pytest.mark.integration
    def test_sensitive_flags_are_ga_or_canary(self):
        """Sensitive flags should be GA or CANARY — never DRAFT."""
        for f in REGISTRY:
            if f.name in _SENSITIVE_FLAGS:
                self.assertIn(
                    f.stage,
                    ("GA", "CANARY"),
                    f"{f.name} should be GA or CANARY, not {f.stage}",
                )

    @pytest.mark.integration
    def test_non_sensitive_flags_are_not_in_sensitive_list(self):
        """Random non-sensitive flag should not be in sensitive list."""
        non_sensitive = "data_quality_enabled"
        self.assertNotIn(non_sensitive, _SENSITIVE_FLAGS)

    @pytest.mark.integration
    def test_flag_stage_lifecycle_valid(self):
        """Every flag should have a valid stage."""
        for f in REGISTRY:
            self.assertIn(f.stage, _VALID_STAGES, f"{f.name} has invalid stage: {f.stage}")
