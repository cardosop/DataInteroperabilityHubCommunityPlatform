"""Pins for scripts/extract_persona_journey_mapping.py (task 0.17 root-cause fix).

The extractor's import regex historically required a BARE ``import`` with
no whitespace or ``await`` prefix — it matched NOTHING from the persona
aggregators (which use ``await import('../journeys/...')``) and silently
dropped every persona using the bare ``import '../journeys/...';`` form.
Regenerating with that bug WIPED 72 lines of the checked-in mapping.

These pins lock all three import forms used by the repo's aggregators.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from extract_persona_journey_mapping import (
    JOURNEY_IMPORT_RE,
    extract_persona_journeys,
)

PERSONAS_DIR = REPO_ROOT / "frontend" / "e2e" / "personas"

REAL_AGGREGATORS = [
    "community-manager.spec.ts",  # bare `import '../journeys/...';`
    "data-engineer.spec.ts",  # `await import('../journeys/...')`
]


class TestImportRegex:
    def test_matches_await_dynamic_import_with_semicolon(self):
        line = "  await import('../journeys/de/JOURNEY-DB-001.spec');"
        assert JOURNEY_IMPORT_RE.findall(line) == ["JOURNEY-DB-001"]

    def test_matches_await_dynamic_import_without_semicolon(self):
        line = "  await import('../journeys/de/JOURNEY-DE-014.spec')"
        assert JOURNEY_IMPORT_RE.findall(line) == ["JOURNEY-DE-014"]

    def test_matches_bare_side_effect_import(self):
        line = "import '../journeys/cm/JOURNEY-CM-001.spec';"
        assert JOURNEY_IMPORT_RE.findall(line) == ["JOURNEY-CM-001"]

    def test_matches_named_from_import(self):
        line = "import { test } from '../journeys/x/JOURNEY-X-001.spec';"
        assert JOURNEY_IMPORT_RE.findall(line) == ["JOURNEY-X-001"]

    def test_does_not_match_unrelated_imports(self):
        assert JOURNEY_IMPORT_RE.findall("import { expect } from '@playwright/test';") == []


class TestExtractAllPersonas:
    @pytest.mark.parametrize("filename", REAL_AGGREGATORS)
    def test_real_aggregators_produce_journeys(self, filename):
        content = (PERSONAS_DIR / filename).read_text()
        journey_ids = JOURNEY_IMPORT_RE.findall(content)
        assert journey_ids, f"{filename} produced no journey ids — regex regression"

    def test_extract_returns_all_thirteen_personas(self):
        mapping = extract_persona_journeys(PERSONAS_DIR)
        # The mapping must never silently drop personas — the pre-fix bug
        # collapsed 13 personas to 7 and wiped the checked-in mapping.
        assert len(mapping) == 13, sorted(mapping.keys())
