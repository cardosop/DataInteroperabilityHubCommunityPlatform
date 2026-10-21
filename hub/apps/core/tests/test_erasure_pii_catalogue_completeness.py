"""Phase 232.8.5 — PII registry rows must have explicit erasure coverage decisions."""

from __future__ import annotations

import pytest
from django.test import SimpleTestCase

from hub.apps.core.pii_erasure_coverage import PII_ERASURE_COVERAGE, erasure_coverage_labels
from hub.apps.core.pii_registry import registered_model_labels


class ErasurePICatalogueCompletenessTests(SimpleTestCase):
    @pytest.mark.unit
    def test_coverage_matches_pii_registry_exactly(self):
        reg = set(registered_model_labels())
        cov = set(erasure_coverage_labels())
        self.assertEqual(
            reg,
            cov,
            msg=f"Drift: registry_only={sorted(reg - cov)} coverage_only={sorted(cov - reg)}",
        )
        self.assertEqual(len(PII_ERASURE_COVERAGE), len(cov))

    @pytest.mark.unit
    def test_each_entry_has_nonempty_reference(self):
        for row in PII_ERASURE_COVERAGE:
            self.assertTrue(row.reference.strip(), row.model_label)
            self.assertTrue(row.mechanism.strip(), row.model_label)
