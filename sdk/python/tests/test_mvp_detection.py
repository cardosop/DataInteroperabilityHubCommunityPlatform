"""
Pure-function tests for ``sdk/python/datahub_interoperability/_mvp_detection.py``.

Mirrors ``cli/tests/test_mvp_detection.py``. Real functions, no mocks.

Phase 215.2 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

import pytest

from datahub_interoperability._mvp_detection import (
    detect_mvp_gated_feature,
    extract_environment_url,
)
from datahub_interoperability._mvp_gates import MVP_GATED_PREFIXES

# ---------------------------------------------------------------------------
# detect_mvp_gated_feature
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
def test_detect_returns_match_for_each_known_prefix(prefix: str) -> None:
    result = detect_mvp_gated_feature(prefix)
    assert result is not None
    matched_prefix, feature = result
    assert matched_prefix == prefix
    assert isinstance(feature, str) and feature


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
def test_detect_matches_prefix_with_trailing_path(prefix: str) -> None:
    result = detect_mvp_gated_feature(prefix + "abc/123")
    assert result is not None
    assert result[0] == prefix


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
def test_detect_matches_when_path_is_full_api_v1_url(prefix: str) -> None:
    result = detect_mvp_gated_feature(f"/api/v1/{prefix}list")
    assert result is not None
    assert result[0] == prefix


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
def test_detect_matches_when_path_is_full_url(prefix: str) -> None:
    result = detect_mvp_gated_feature(f"https://meshant-internal.example.com/api/v1/{prefix}list")
    assert result is not None
    assert result[0] == prefix


@pytest.mark.parametrize(
    "path",
    [
        "",
        "contracts/",
        "/api/v1/contracts/",
        "/api/v1/marketplace/listings/",
        "https://meshant-internal.example.com/api/v1/auth/login/",
        "auth/login/",
        "totally-unrelated/path",
    ],
)
def test_detect_returns_none_for_non_gated_paths(path: str) -> None:
    assert detect_mvp_gated_feature(path) is None


def test_detect_is_deterministic_under_multiple_matches() -> None:
    result = detect_mvp_gated_feature("mesh/clusters/abc")
    assert result is not None
    assert result[0] == "mesh/"


# ---------------------------------------------------------------------------
# extract_environment_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://meshant-internal.example.com/api/v1/mesh/", "https://meshant-internal.example.com"),
        ("http://localhost:8000/api/v1/mesh/", "http://localhost:8000"),
        (
            "https://meshant-internal.example.com:443/api/v1/ml/jobs",
            "https://meshant-internal.example.com:443",
        ),
        ("https://meshant.com", "https://meshant.com"),
    ],
)
def test_extract_environment_url_returns_origin(url: str, expected: str) -> None:
    assert extract_environment_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "/api/v1/mesh/",
        "not a url at all",
    ],
)
def test_extract_environment_url_falls_back_gracefully(url: str) -> None:
    result = extract_environment_url(url)
    assert isinstance(result, str)
    if url == "":
        assert result == ""
    else:
        assert result
