"""
Phase 26.9.2 — ODCS version boundary conditions.

Validates normalizer version routing without hypothesis
(deterministic boundary values instead of random generation).

Run: pytest hub/tests/test_odcs_version_boundaries.py -v \\
     --noconftest -p no:django
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


def _read(rel: str) -> str:
    return (REPO / rel).read_text()


class TestV31VersionMatching:
    """The v3.1.0 normalizer must accept 3.1.x semver."""

    @pytest.fixture()
    def src(self):
        return _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_1_0.py"
        )

    @pytest.fixture()
    def pattern(self, src):
        """Extract the compiled regex from source."""
        m = re.search(
            r're\.compile\(r"([^"]+)"\)', src,
        )
        assert m, "_V3_1_PATTERN not found"
        return re.compile(m.group(1))

    @pytest.mark.parametrize("version", [
        "3.1.0", "3.1.1", "3.1.2", "3.1.99",
    ])
    def test_accepts_valid_31x(self, pattern, version):
        assert pattern.match(version)

    @pytest.mark.parametrize("version", [
        "3.1.0beta", "3.1.0-rc1", "3.1.0+build",
        "3.10.0", "3.0.2", "2.2.2", "4.0.0",
    ])
    def test_rejects_non_31x(self, pattern, version):
        assert not pattern.match(version)


class TestV302VersionMatching:
    """The v3.0.2 normalizer must accept 3.0.2[+]."""

    def test_v302_supports_3_0_2(self):
        src = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_0_2.py"
        )
        # Must contain version check for 3.0.2
        assert '"3.0.2"' in src

    def test_v302_does_not_support_3_1_0(self):
        src = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_0_2.py"
        )
        idx = src.find("def _supports_version")
        body = src[idx:idx + 300]
        assert '"3.1.0"' not in body


class TestGeneratorRegistryVersions:
    """All expected versions are registered."""

    @pytest.fixture()
    def src(self):
        return _read("hub/apps/contracts/odcs_generator.py")

    @pytest.mark.parametrize("version", [
        "3.1.0", "3.0.2", "3.0.1", "3.0.0",
        "3.0.0-preview", "2.2.2",
    ])
    def test_version_registered(self, src, version):
        assert f'register_odcs_generator("{version}"' in src

    def test_latest_is_3_0_2_not_3_1_0(self, src):
        """Default must stay 3.0.2 for backward compat."""
        assert '_LATEST_ODCS_VERSION = "3.0.2"' in src


class TestNormalizerBaseVersionDetection:
    """_detect_odcs_version handles all apiVersion formats."""

    @pytest.fixture()
    def src(self):
        return _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_base.py"
        )

    def test_handles_odcs_io_prefix(self, src):
        idx = src.find("def _detect_odcs_version")
        body = src[idx:idx + 600]
        assert "/v" in body

    def test_handles_short_v_prefix(self, src):
        idx = src.find("def _detect_odcs_version")
        next_def = src.find("\n    def ", idx + 1)
        body = src[idx:next_def] if next_def != -1 else src[idx:]
        assert "startswith" in body

    def test_falls_back_to_3_0_2(self, src):
        idx = src.find("def _detect_odcs_version")
        body = src[idx:idx + 600]
        assert '"3.0.2"' in body
