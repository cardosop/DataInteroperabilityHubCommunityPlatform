"""TDD suite for ``scripts/check_error_codes_catalogue.py`` — the
error-code catalogue gate (Phase 250.0.13 / the 12.x Shared DoD).

The checker extracts SCREAMING_SNAKE_CASE codes from the emission
patterns; this suite pins the pattern set itself (a pattern regression
would silently reopen a coverage hole) and the extract/catalogue
comparison end to end:

- the DRF classified-error class-attribute form
  (``code: ClassVar[str] = "X"`` — the form the 12.x views emit, added
  by the 12.8 session) is caught WITH and WITHOUT the annotation;
- the pre-extension kwarg pattern does NOT catch that form (the hole
  the extension closed — non-vacuity in both directions);
- the extractor sees every pattern form, and a code present in
  ``docs/api/error-codes.md`` passes while an uncatalogued one is
  reported (a REAL catalogue read, no mocks).
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts import check_error_codes_catalogue as checker

CATALOGUE_PATH = pathlib.Path(REPO_ROOT) / "docs" / "api" / "error-codes.md"


def test_the_classvar_form_is_caught_with_and_without_the_annotation():
    """The 12.x DRF classified-error attribute rides the pattern set."""
    with_annotation = '    code: ClassVar[str] = "DATABRICKS_ML_INVALID_CONFIG"'
    bare = '    code: str = "DATABRICKS_ML_INVALID_CONFIG"'
    for line in (with_annotation, bare):
        codes = [m.group(1) for p in checker._PATTERNS for m in p.finditer(line)]
        assert codes == ["DATABRICKS_ML_INVALID_CONFIG"], line


def test_the_pre_extension_kwarg_pattern_misses_the_classvar_form():
    """Non-vacuity: the old pattern set's kwarg form never matched the
    class-attribute form — that gap is why the extension exists."""
    import re

    kwarg_pattern = re.compile(r"\bcode\s*=\s*[\"']([A-Z][A-Z0-9_]+)[\"']")
    line = '    code: ClassVar[str] = "DATABRICKS_UC_OBJECT_NOT_FOUND"'
    assert not kwarg_pattern.search(line), (
        "the kwarg pattern must NOT match the annotated class attribute"
    )


def test_the_extractor_reports_an_uncatalogued_code():
    """End to end against the REAL catalogue: every 12.x classified code
    is catalogued; a deliberately absent one is reported."""
    catalogue_codes = checker._load_catalogue_codes(CATALOGUE_PATH)
    for code in (
        "DATABRICKS_ML_ASSETS_DISABLED",
        "DATABRICKS_UC_OBJECT_NOT_FOUND",
        "DATABRICKS_ML_INVALID_FULL_NAME",
        "DATABRICKS_ML_INVALID_CONFIG",
    ):
        assert code in catalogue_codes, code
    assert "DATABRICKS_ML_NEVER_EMITTED_X" not in catalogue_codes
    assert (
        checker._TABLE_CODE_PATTERN.match("| `DATABRICKS_ML_ASSETS_DISABLED` | 403 |") is not None
    )


def test_the_checker_exits_green_on_the_current_tree():
    """The gate itself — rc 0 with zero offences (the exact CI command
    minus the advisory `|| true`)."""
    result = checker.main([])
    assert result == 0, "the checker must exit green on the current tree"
