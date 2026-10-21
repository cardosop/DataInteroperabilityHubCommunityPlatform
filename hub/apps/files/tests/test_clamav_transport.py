"""Unit tests for clamd VERSION parsing helpers (Phase 260.0.17)."""

from __future__ import annotations

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
    def test_parse_major_minor_only(self) -> None:
        # Banners without a patch version (e.g. old ClamAV format).
        with self.assertRaises(ValueError):
            parse_clamd_semver("ClamAV 1.4/abcd")

    @pytest.mark.unit
    def test_parse_no_version_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_clamd_semver("ClamAV /abcd")

    @pytest.mark.unit
    def test_version_meets_minimum(self) -> None:
        ok, _eff = version_meets_minimum(daemon_banner="ClamAV 1.5.1/x", required_text="0.103.0")
        self.assertTrue(ok)

    @pytest.mark.unit
    def test_version_meets_exact_boundary(self) -> None:
        ok, _eff = version_meets_minimum(daemon_banner="ClamAV 1.0.0/a", required_text="1.0.0")
        self.assertTrue(ok)

    @pytest.mark.unit
    def test_version_below_minimum(self) -> None:
        ok, _ = version_meets_minimum(daemon_banner="ClamAV 0.96.5/x", required_text="1.0.0")
        self.assertFalse(ok)
