"""Unit tests for clamd VERSION parsing helpers (Phase 260.0.17)."""

from __future__ import annotations
import pytest

import pytest
from django.test import SimpleTestCase

from hub.apps.files.clamav_transport import (
    parse_clamd_semver,
    version_meets_minimum,
)


class ClamdVersionParseTests(SimpleTestCase):
    @pytest.mark.unit
    def test_parse_typical_banner(self) -> None:
        self.assertEqual(parse_clamd_semver("ClamAV 1.4.2/abcd"), (1, 4, 2))

    @pytest.mark.unit
    def test_version_meets_minimum(self) -> None:
        ok, eff = version_meets_minimum(daemon_banner="ClamAV 1.5.1/x", required_text="0.103.0")
        self.assertTrue(ok)

    @pytest.mark.unit
    def test_version_below_minimum(self) -> None:
        ok, _ = version_meets_minimum(daemon_banner="ClamAV 0.96.5/x", required_text="1.0.0")
        self.assertFalse(ok)
