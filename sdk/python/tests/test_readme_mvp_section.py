"""
Phase 215.4 — assert that ``sdk/python/README.md`` carries an
``## MVP Compatibility`` section that documents every MVP-gated prefix.

The test parses the rendered README (no regex over Python source) to extract
the section between the ``## MVP Compatibility`` heading and the next ``##``
heading, then asserts every gated prefix appears at least once inside that
slice. Locating the canonical prefix list via ``MVP_GATED_PREFIXES`` (not a
hardcoded copy) means the test stays in lock-step with whatever Phase 215.1
drift detection enforces — if the gating set ever grows, the README test
fails until the new entries are documented.

Phase 215.4 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from datahub_interoperability._mvp_gates import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_PREFIXES,
)


README_PATH = Path(__file__).resolve().parents[1] / "README.md"
SECTION_HEADING = "## MVP Compatibility"


def _extract_section(text: str, heading: str) -> str:
    """Return the body of a Markdown section bounded by ``heading`` and the
    next ``## ``-level heading (or end of file).
    """
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start = idx + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


@pytest.fixture(scope="module")
def readme_text() -> str:
    assert README_PATH.is_file(), f"SDK README not found at {README_PATH}"
    return README_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def mvp_section(readme_text: str) -> str:
    section = _extract_section(readme_text, SECTION_HEADING)
    assert section.strip(), (
        f"{SECTION_HEADING!r} section is missing or empty in {README_PATH}"
    )
    return section


# ---------------------------------------------------------------------------
# Section placement & structural anchors
# ---------------------------------------------------------------------------


def test_mvp_section_appears_between_error_handling_and_retry_logic(
    readme_text: str,
) -> None:
    """The new section MUST live between Error Handling and Retry Logic so
    readers see it in the natural flow of error/HTTP topics."""
    err_idx = readme_text.find("## Error Handling")
    retry_idx = readme_text.find("## Retry Logic")
    mvp_idx = readme_text.find(SECTION_HEADING)
    assert err_idx != -1, "## Error Handling section missing from README"
    assert retry_idx != -1, "## Retry Logic section missing from README"
    assert mvp_idx != -1, f"{SECTION_HEADING} section missing from README"
    assert err_idx < mvp_idx < retry_idx, (
        "MVP Compatibility section MUST be placed between "
        "Error Handling and Retry Logic. Current order: "
        f"err={err_idx}, mvp={mvp_idx}, retry={retry_idx}"
    )


# ---------------------------------------------------------------------------
# Coverage of every gated prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
def test_every_gated_prefix_is_documented_in_section(
    mvp_section: str, prefix: str
) -> None:
    """Each gated prefix MUST appear inside the new section.

    The check accepts either the bare prefix (``mesh/``) or the human label
    (``Data Mesh``) — both are acceptable forms in user-facing docs as long
    as the section unambiguously names the gated module.
    """
    label = MVP_GATED_FEATURE_NAMES[prefix]
    assert prefix in mvp_section or label in mvp_section, (
        f"Gated prefix {prefix!r} (label {label!r}) is not documented in "
        f"the {SECTION_HEADING} section. Add a row covering it."
    )


# ---------------------------------------------------------------------------
# Required content blocks
# ---------------------------------------------------------------------------


def test_section_includes_programmatic_detection_snippet(mvp_section: str) -> None:
    """The section MUST show how to branch on the stable error code."""
    assert MVP_FEATURE_GATED_CODE in mvp_section, (
        f"Section MUST mention {MVP_FEATURE_GATED_CODE!r} so readers know "
        "the machine-readable contract."
    )
    assert "MVPGatedFeatureError" in mvp_section, (
        "Section MUST reference MVPGatedFeatureError by name."
    )


def test_section_includes_introspection_snippet(mvp_section: str) -> None:
    """The section MUST document the offline-introspection import."""
    assert "MVP_GATED_PREFIXES" in mvp_section, (
        "Section MUST show ``from datahub_interoperability import "
        "MVP_GATED_PREFIXES`` so power users know they can pre-check paths."
    )


def test_section_includes_backwards_compat_note(mvp_section: str) -> None:
    """The section MUST tell users existing ``except NotFoundError`` still works."""
    assert "NotFoundError" in mvp_section, (
        "Section MUST include the backwards-compat note that "
        "``except NotFoundError:`` still catches MVP-gated 404s."
    )


def test_section_contains_a_markdown_table(mvp_section: str) -> None:
    """The section MUST include a Markdown table listing the gated modules.

    Tables are recognized by their separator row (``|---``).
    """
    has_table = any(
        line.strip().startswith("|") and "---" in line
        for line in mvp_section.splitlines()
    )
    assert has_table, (
        "Section MUST include a Markdown table (look for a `|---|` separator "
        "row). The table is the canonical at-a-glance view of which modules "
        "are gated."
    )
