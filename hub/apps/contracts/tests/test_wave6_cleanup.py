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
    """Walk every surface a retired identifier could plausibly hide in.

    Coverage tiers (W6 audit):

    * ``hub/apps`` + ``frontend/src`` — production source.
    * ``helm/`` — chart values + templates (env-var injection happens
      here for Vite-baked frontend flags).
    * ``.github/workflows/`` — CI workflows that set bundle-time env
      vars on the deploy job.
    * ``frontend/.env.example`` + ``frontend/vite.config.*`` —
      per-developer env-var bootstrap.

    Skip migrations (historical state), node_modules (vendored), build
    output, and the test file itself (its docstring would otherwise
    grep-match against its own assertions).
    """
    targets: list[Path] = []

    # Source trees — recurse.
    for relative in ("hub/apps", "frontend/src", "helm", ".github/workflows"):
        base = REPO_ROOT / relative
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            parts = set(p.parts)
            if any(
                s in parts
                for s in (
                    "__pycache__",
                    "node_modules",
                    "migrations",
                    "dist",
                    "build",
                    ".pytest_cache",
                )
            ):
                continue
            if p.name == "test_wave6_cleanup.py":
                continue
            if p.suffix in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".yaml",
                ".yml",
                ".json",
                ".html",
                ".toml",
                ".sh",
            }:
                targets.append(p)

    # Specific files — env bootstrap + Vite config.
    for relative in (
        "frontend/.env.example",
        "frontend/vite.config.ts",
        "frontend/vite.config.js",
    ):
        p = REPO_ROOT / relative
        if p.is_file():
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
        f"  {p.relative_to(REPO_ROOT)}:{lineno}: {line}" for p, lineno, line in hits[:25]
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
    contract response path stays clean of them.

    W6-AUDIT-2 (post-W6 audit): the original regex only matched
    double-quoted header names.  Django (and most Python web
    frameworks) treat single and double quotes interchangeably, so
    ``response['Sunset'] = X`` and ``response.headers['Deprecation']``
    were silently slipping through the guard.  The pattern below
    matches **any** header-emission idiom — bracket-subscript
    (``[]``), attribute access (``.``), or call expression (``(``)
    — followed by either quote style around ``Sunset`` or
    ``Deprecation``.  This catches:

    * ``response["Sunset"] = ...``        (double-quote subscript)
    * ``response['Sunset'] = ...``        (single-quote subscript)
    * ``response.headers["Sunset"] = ...``
    * ``response.headers['Sunset'] = ...``
    * ``response.headers.add("Sunset", v)`` (call form, used by some libs)
    * ``response.setdefault('Deprecation', v)``

    And does NOT match:

    * ``# the Sunset header would have ...``  (free-text mention)
    * ``## Sunset``                            (markdown heading)
    * ``"Sunset is documented elsewhere."``   (quoted prose without
      a preceding ``[``, ``.``, or ``(``)
    """
    # The leading anchor `[\.\(]` requires the quoted name to be
    # preceded immediately by one of `[`, `.`, or `(` (with optional
    # whitespace) — i.e. an indexing / attribute / call operator.
    # That's what distinguishes header emission from prose.
    rx = re.compile(r"""[\[.\(]\s*['"](?:Sunset|Deprecation)['"]""")
    hits = []
    for path in _scan_paths():
        if path.suffix != ".py":
            continue
        # Only scan contract-related source — the Wave 1-3 deprecation
        # was specifically about contract write paths.  Other apps
        # (datasets/, api/versioning.py) legitimately emit Sunset /
        # Deprecation as part of general endpoint deprecation infra.
        parts = set(path.parts)
        if not ("contracts" in parts or path.name.startswith("test_wave6")):
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


def test_phase_227_w6_archive_manifest_hashes_match_local_files():
    """W6-AUDIT-3 (post-W6 audit) — the manifest's hash baselines
    must actually match the artefacts they describe.

    The original test only checked the SHA-256 SHAPE (any 64-hex
    string), not that the hash was correct.  A copy-paste error or
    typo in the manifest would slip through, then surface years
    later when an auditor's S3 hash-check fails against a wrong
    baseline.  Engineering-grade fix: re-compute the hash at test
    time and compare.

    The audit-reports/ directory is gitignored, so CI (which clones
    fresh) won't have the local files.  Skip the assertion in that
    case — the test still provides value when ops runs it locally
    before the artefact moves to S3, and the in-shape check above
    keeps the pattern guard in place for CI.
    """
    import hashlib

    manifest = REPO_ROOT / "archive" / "phase-227-rollout" / "MANIFEST.md"
    text = manifest.read_text(encoding="utf-8")

    # Parse the manifest's table rows: each row carries an artefact
    # path in backticks and a SHA-256 in backticks.  We extract them
    # by walking the lines and pairing path/hash within each row.
    table_rx = re.compile(
        r"`(audit-reports/[^`]+)`.*?`([0-9a-f]{64})`",
    )
    pairs = table_rx.findall(text)
    assert pairs, (
        "Manifest must declare at least one (artefact-path, SHA-256) "
        "pair in its artefact table.  Without a parseable table the "
        "hash-verification path can't run and this regression guard "
        "becomes a no-op."
    )

    skipped: list[str] = []
    verified: list[str] = []
    mismatches: list[str] = []
    for relpath, declared_hash in pairs:
        artefact = REPO_ROOT / relpath
        if not artefact.is_file():
            skipped.append(relpath)
            continue
        actual_hash = hashlib.sha256(artefact.read_bytes()).hexdigest()
        if actual_hash != declared_hash:
            mismatches.append(f"  {relpath}: declared={declared_hash}, actual={actual_hash}")
        else:
            verified.append(relpath)

    # Hard-fail on any mismatch.  A skipped (gitignored / not in
    # working tree) artefact is acceptable in CI; a wrong hash is
    # never acceptable anywhere.
    assert not mismatches, (
        "Phase 227 W6.4 manifest hash mismatch — the SHA-256 "
        "declared in the manifest does NOT match the actual file "
        "content.  Either the manifest was edited without "
        "re-hashing, or the artefact mutated post-archival.  "
        "A future S3 retrieval that compares against this baseline "
        "would falsely flag tamper-evidence.\n" + "\n".join(mismatches)
    )
    # If all listed artefacts were skipped, surface that as a soft
    # warning via pytest.skip — the test ran but couldn't verify
    # anything.  When ops runs locally with the audit-reports files
    # present, this skip becomes a real verification.
    if not verified:
        pytest.skip(  # noqa: skip-in-body — runtime service dependency
            "All declared artefacts are absent from the working tree "
            "(gitignored or already moved to S3).  Hash-shape check "
            f"in the prior test still applies.  Skipped: {skipped}"
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


def test_phase_227_w6_scanner_covers_infra_and_build_configs():
    """W6-AUDIT-1 (post-W6 audit) — pin the scanner's coverage scope.

    A future refactor that quietly drops ``helm/``, ``.github/workflows/``,
    or ``frontend/.env.example`` from ``_scan_paths`` would re-open the
    door to a flag identifier sneaking back in via a Helm values file
    or a CI bundle-time env var without CI catching it.  This test
    asserts each tier is represented in the scan output.

    Each assertion is conservative: we don't require N specific files,
    just that **at least one** file exists from each tier.  That's
    enough to detect a wholesale scope shrinkage without breaking on
    repo-layout changes that move a single file.
    """
    paths = _scan_paths()

    helm_files = [p for p in paths if "helm" in p.parts]
    assert helm_files, (
        "Scanner must cover helm/ — Vite-baked frontend env vars get "
        "injected here at chart-render time; a re-introduction of "
        "VITE_FEATURE_SCHEMA_EDITOR_ENABLED in chart values would "
        "slip through the W6.1 guard otherwise."
    )

    workflow_files = [p for p in paths if ".github" in p.parts and "workflows" in p.parts]
    assert workflow_files, (
        "Scanner must cover .github/workflows/ — deploy.yml sets "
        "bundle-time env vars on the deploy job; a re-introduction "
        "there would slip through the W6.1 guard otherwise."
    )

    env_example = [p for p in paths if p.name == ".env.example" and "frontend" in p.parts]
    assert env_example, (
        "Scanner must cover frontend/.env.example — it's the per-"
        "developer env-var bootstrap, and a copy-pasted example "
        "of VITE_FEATURE_SCHEMA_EDITOR_ENABLED here would propagate "
        "to every developer's local build."
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
