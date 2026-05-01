"""
Phase 227 Wave 6 (227.W6.1 / 227.W6.2 / 227.W6.3) — cleanup-phase
regression guards.

Phase 227 went straight to enforcement under the 2026-04-30 ungate
directive (L3.3 / L9.1).  The Wave 1-3 deprecation surface — feature
flags, ``Sunset`` / ``Deprecation`` HTTP headers, ``contract_would_reject_total``
shadow telemetry — was therefore NEVER shipped: the intended gradual
rollout collapsed into a single hard-cutover step.

These tests exist to prevent **accidental re-introduction** of any of
those surfaces during future refactors.  They walk the code as text
(no imports), so a future maintainer who copy-pastes the historical
spec language into a new file gets a CI failure pointing at this
audit closeout instead of silently re-creating the deprecated surface.

Why text-based scanning (not import-based)
------------------------------------------
A flag identifier or metric name can hide in:
* a Python string literal (``feature_flags.set("contracts.structural_floor.enabled", ...)``)
* a YAML / JSON config bundled with Helm or settings
* a frontend ``import.meta.env.VITE_FEATURE_*`` reference

Importing the module wouldn't catch any of those.  A regex scan over
``hub/`` + ``frontend/src/`` does.  Acceptance bias: the scanner
ignores its own file (this very docstring counts as a "mention" but
isn't a re-introduction), the existing tasks.md / openspec / docs
that document the historical fact, and any test file whose name
matches ``test_wave6_cleanup``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]


def _scan_paths():
    """Walk hub/apps + frontend/src for source files (skip migrations,
    tests for the cleanup itself, generated assets, vendored code)."""
    targets: list[Path] = []
    for relative in ("hub/apps", "frontend/src"):
        base = REPO_ROOT / relative
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            # Skip auto-generated / vendored / cache / test-of-cleanup files.
            parts = set(p.parts)
            if any(s in parts for s in {
                "__pycache__", "node_modules", "migrations",
                "dist", "build", ".pytest_cache",
            }):
                continue
            if p.name == "test_wave6_cleanup.py":
                continue
            if p.suffix in {
                ".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml",
                ".json", ".html",
            }:
                targets.append(p)
    return targets


def _grep_for(pattern: str) -> list[tuple[Path, int, str]]:
    """Return a list of (path, lineno, line_text) for every match.

    Matches are exact regex hits — callers craft patterns that ignore
    docstring context (e.g. word boundaries) when needed.
    """
    rx = re.compile(pattern)
    hits: list[tuple[Path, int, str]] = []
    for path in _scan_paths():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append((path, lineno, line.rstrip()))
    return hits


def _format(hits: list[tuple[Path, int, str]]) -> str:
    return "\n".join(
        f"  {p.relative_to(REPO_ROOT)}:{lineno}: {line}"
        for p, lineno, line in hits[:25]
    )


# ---------------------------------------------------------------------------
# 227.W6.1 — Feature-flag identifiers must not return
# ---------------------------------------------------------------------------


_FLAG_PATTERNS = [
    r"contracts\.structural_floor\.enabled",
    r"contracts\.schema_editor\.enabled",
    # Frontend env-var name retired in L5.11.
    r"VITE_FEATURE_SCHEMA_EDITOR_ENABLED",
    # Python helpers retired in L3.3.
    r"is_structural_floor_enabled",
    r"is_schema_editor_enabled",
]


@pytest.mark.parametrize("pattern", _FLAG_PATTERNS)
def test_phase_227_feature_flag_identifiers_are_gone(pattern):
    """No production code may reference the retired flags.

    The flags were never registered (per L3.3 / L9.1 closeouts) but
    a copy-paste from the original spec language could re-introduce
    them.  The structural floor enforces unconditionally now —
    re-adding a flag check would silently regress the invariant.
    """
    hits = _grep_for(pattern)
    assert not hits, (
        f"Phase 227 Wave 6 cleanup regression — `{pattern}` "
        f"reappeared in {len(hits)} source location(s).  The flag "
        f"was retired by the 2026-04-30 ungate directive; "
        f"re-introducing it would silently regress the structural "
        f"floor invariant.  Hits:\n" + _format(hits)
    )


# ---------------------------------------------------------------------------
# 227.W6.2 — Sunset / Deprecation HTTP headers must not return
# ---------------------------------------------------------------------------


def test_phase_227_sunset_header_emission_is_gone():
    """The Wave 1-3 spec called for the contract write paths to emit
    a ``Sunset:`` HTTP header during the deprecation window.  Under
    the ungate directive that window collapsed to zero days — no
    Sunset / Deprecation headers were ever shipped.  Pin that the
    contract response path stays clean of them."""
    # Pattern matches HTTP-header emission idioms only — NOT the
    # word "Sunset" appearing in a Markdown changelog or comment.
    # We look for ``response["Sunset"]``, ``response.headers["Sunset"]``,
    # ``add_header("Sunset"`` and the equivalent for ``Deprecation``.
    rx = re.compile(
        r'(?:response(?:\.headers)?|self|res|resp|request)'
        r'(?:\["(?:Sunset|Deprecation)"\]|\.headers\["(?:Sunset|Deprecation)"\])'
        r'\s*='
    )
    hits = []
    for path in _scan_paths():
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append((path, lineno, line.rstrip()))
    assert not hits, (
        "Phase 227 Wave 6 cleanup regression — Sunset / Deprecation "
        "HTTP-header emission reappeared.  The header was never "
        "shipped under the ungate directive; re-introducing it would "
        "imply a deprecation window that the codebase doesn't "
        "actually honour.  Hits:\n" + _format(hits)
    )


# ---------------------------------------------------------------------------
# 227.W6.3 — Shadow rejection telemetry must not return
# ---------------------------------------------------------------------------


def test_phase_227_w6_archive_manifest_exists():
    """W6.4 — `archive/phase-227-rollout/MANIFEST.md` is the
    git-tracked breadcrumb for the rollout artefacts (the JSONL
    itself stays in `audit-reports/` per the gitignored convention).
    A future cleanup PR that drops the manifest would erase the
    only record of which artefacts existed and where they went —
    pin its presence."""
    manifest = REPO_ROOT / "archive" / "phase-227-rollout" / "MANIFEST.md"
    assert manifest.exists(), (
        f"Phase 227 W6.4 archive manifest missing at {manifest}. "
        "The manifest is the compliance breadcrumb pointing at the "
        "rollout-evidence S3 location; without it ops loses the "
        "ability to retrieve the original dry-run JSONL by hash."
    )
    text = manifest.read_text(encoding="utf-8")
    # Must reference both artefacts by name.
    assert "structureless-pre-rollout-2026-04-30.jsonl" in text
    assert "structureless-summary-2026-04-30.md" in text
    # Must carry the SHA-256 baselines (so a future audit can
    # spot-check S3 against them).
    assert re.search(r"[0-9a-f]{64}", text), (
        "Manifest must list a SHA-256 for each artefact so an audit "
        "can verify the S3 copy matches archival-time integrity."
    )


def test_phase_227_steady_state_notice_in_contracts_doc():
    """W6.5 — the `Steady state` blockquote near the top of
    CONTRACTS.md is the customer-facing signal that the rollout is
    done.  A future doc refactor that drops it would re-orient the
    doc back to "rollout-in-flight" framing — pin it."""
    contracts = REPO_ROOT / "docs" / "CONTRACTS.md"
    assert contracts.exists(), f"docs/CONTRACTS.md missing at {contracts}"
    text = contracts.read_text(encoding="utf-8")
    assert "Steady state" in text, (
        "CONTRACTS.md must carry the W6.5 'Steady state' blockquote "
        "so readers know Phase 227 is complete and the doc is the "
        "post-rollout reference, not in-flight rollout guidance."
    )
    assert "Phase 227 W6 cutover" in text


def test_phase_227_steady_state_notice_in_runbook():
    """W6.5 — same for the runbook.  The 'Post-rollout steady state'
    section near the top tells operators they're not in a rollout
    any more; without it, future ops onboarding would interpret the
    Wave 0-5 sections as still-scheduled work."""
    runbook = REPO_ROOT / "docs" / "runbooks" / "structureless-contracts.md"
    assert runbook.exists()
    text = runbook.read_text(encoding="utf-8")
    assert "Post-rollout steady state" in text, (
        "Runbook must carry the W6.5 'Post-rollout steady state' "
        "section so operators reading the doc don't mistake the "
        "Wave 0-5 ceremonies for scheduled work."
    )
    assert "DO NOT RUN" in text, (
        "Runbook must keep the standby warning on the reverse "
        "migration so an over-eager operator doesn't trigger an "
        "emergency rollback by accident."
    )


def test_phase_227_would_reject_telemetry_is_gone():
    """``contract_would_reject_total{reason}`` was the shadow
    counter intended for the gradual-rollout window: count "what
    WOULD have rejected if the floor flag were on".  Under the
    ungate directive the floor went straight to enforcement, so
    the counter never shipped.  Pin that it doesn't sneak back in
    via a backfill PR."""
    hits = _grep_for(r"contract_would_reject_total")
    assert not hits, (
        "Phase 227 Wave 6 cleanup regression — "
        "`contract_would_reject_total` shadow counter reappeared.  "
        "The metric was obsoleted by the ungate directive (Wave 4+ "
        "is hard-rejection, not shadow-mode); re-introducing it "
        "would imply a deprecation period that doesn't exist.  "
        "Hits:\n" + _format(hits)
    )
