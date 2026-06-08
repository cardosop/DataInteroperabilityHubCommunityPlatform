"""Phase 232.8 — compliance routes must be mounted under /api/v1/compliance/."""

from __future__ import annotations
import pytest

import pytest
from django.test import SimpleTestCase
from django.urls import resolve, reverse


class ComplianceUrlMountTests(SimpleTestCase):
    @pytest.mark.unit
    def test_compliance_run_list_is_registered(self) -> None:
        url = reverse("compliance-run-list")
        self.assertEqual(url, "/api/v1/compliance/runs/")

    @pytest.mark.unit
    def test_compliance_run_list_resolves(self) -> None:
        match = resolve("/api/v1/compliance/runs/")
        self.assertIn("list", match.url_name or "")
