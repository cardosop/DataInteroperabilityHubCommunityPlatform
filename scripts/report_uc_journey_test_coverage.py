#!/usr/bin/env python3
"""
Report which use cases (USE_CASES.md) and user journeys (USER_JOURNEYS.md)
have at least one test, and scenario coverage (Success/Failure/Edge) per UC/journey.
Output: Markdown or JSON with UC→test mapping and scenario coverage column.
Integrates with Traceability CI Gate (openspec/changes/testsfix1 T.1–T.4): --ci-mode
exits 0 only when no critical gaps and coverage >= threshold; JSON artifact includes
scenario_coverage_use_cases and scenario_coverage_user_journeys for gate/PR use.

Usage:
  python scripts/report_uc_journey_test_coverage.py [--json] [--fail-if-zero] [--audit-traceability]
  python scripts/report_uc_journey_test_coverage.py --ci-mode [--output FILE] [--critical-list FILE]
  --json: output JSON (use_cases, user_journeys, scenario_coverage, broken_traceability_links)
  --output FILE: write report to FILE (default: stdout)
  --fail-if-zero: exit 1 if any UC or journey has zero tests
  --audit-traceability: check TEST_TRACEABILITY.md file paths exist; report broken links
  --ci-mode: Traceability CI Gate: exit 0 only when no critical gaps and coverage >= threshold
  --critical-list FILE: YAML with critical_use_cases, critical_journeys, thresholds
  --uc-threshold PERCENT: min UC coverage (default: from critical list or 70)
  --journey-threshold PERCENT: min journey coverage (default: from critical list or 60)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def repo_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


# Phase 226 E4 — restore the traceability gate after the docs reorg moved
# USE_CASES.md / USER_JOURNEYS.md / TEST_TRACEABILITY.md under
# `docs/deprecated-doc/`. Probe a tiered list of candidate locations so
# the script is robust to a future restoration of the canonical
# `docs/<file>.md` paths (or another move) without code change.
USE_CASES_CANDIDATES = (
    "docs/USE_CASES.md",
    "docs/deprecated-doc/product-originals/USE_CASES.md",
    "docs/deprecated-doc/feature-docs/USE_CASES.md",
)
USER_JOURNEYS_CANDIDATES = (
    "docs/USER_JOURNEYS.md",
    "docs/deprecated-doc/product-originals/USER_JOURNEYS.md",
    "docs/deprecated-doc/feature-docs/USER_JOURNEYS.md",
)
TRACEABILITY_CANDIDATES = (
    "docs/TEST_TRACEABILITY.md",
    "docs/deprecated-doc/test-reports/TEST_TRACEABILITY.md",
)


def resolve_doc(root: Path, candidates: tuple[str, ...]) -> Path | None:
    """Return the first existing path among `candidates`, or None.

    Tiered probe: prefers the canonical `docs/<file>.md` path (returned
    first if present) and falls back to the post-reorg
    `docs/deprecated-doc/...` location automatically. None means the
    caller should treat the doc as missing.
    """
    for rel in candidates:
        p = root / rel
        if p.is_file():
            return p
    return None


def extract_uc_ids(use_cases_path: Path) -> list[str]:
    """Extract UC-* IDs from USE_CASES.md (lines like **ID**: UC-XXX)."""
    ids: list[str] = []
    content = use_cases_path.read_text()
    for m in re.finditer(r"\*\*ID\*\*:\s*(UC-[A-Za-z0-9-]+)", content):
        ids.append(m.group(1))
    return sorted(set(ids))


def extract_journey_ids(user_journeys_path: Path) -> list[str]:
    """
    Extract JOURNEY-* IDs from USER_JOURNEYS.md.
    Matches: **Journey ID**: JOURNEY-XXX; list items - JOURNEY-XXX:; table cells | JOURNEY-XXX |.
    """
    ids: list[str] = []
    content = user_journeys_path.read_text()
    # Canonical section header
    for m in re.finditer(r"\*\*Journey ID\*\*:\s*(JOURNEY-[A-Za-z0-9-]+)", content):
        ids.append(m.group(1))
    # List items: - JOURNEY-XXX: or - JOURNEY-XXX 
    for m in re.finditer(r"^-\s+(JOURNEY-[A-Za-z0-9-]+)[:\s]", content, re.MULTILINE):
        ids.append(m.group(1))
    # Table cell: | JOURNEY-XXX |
    for m in re.finditer(r"\|\s*(JOURNEY-[A-Za-z0-9-]+)\s*\|", content):
        ids.append(m.group(1))
    return sorted(set(ids))


def collect_test_files(root: Path) -> list[Path]:
    """Collect backend and frontend test file paths."""
    files: list[Path] = []
    for pattern in [
        "hub/apps/**/tests/*.py",
        "hub/apps/**/tests/**/*.py",
        "tests/**/*.py",
        "frontend/e2e/**/*.spec.ts",
    ]:
        for p in root.glob(pattern):
            if p.is_file():
                files.append(p)
    return sorted(set(files))


_GAP_BLOCK_HEAD_RE = re.compile(r"\b(Coverage gap|NOT covered)\b")


def strip_gap_blocks(content: str) -> str:
    """
    Remove text inside ``Coverage gap`` / ``NOT covered`` comment blocks before
    substring matching, so IDs listed there are NOT attributed as covered.

    Convention: a gap block starts on a line containing ``Coverage gap`` or
    ``NOT covered`` and continues until a blank line, a blank-comment line
    (``*`` with no other content), or end of content.

    Why this exists: spec authors mark partial-coverage gaps with the literal
    UC IDs of the missing scenarios so a future implementer can grep
    ``UC-FOO-002`` and find the exact spec that needs the missing coverage
    added — bidirectional traceability for humans. Without this filter, the
    naive substring matcher in :func:`find_references_in_file` would falsely
    attribute those gap-listed IDs as covered. See the
    ``Coverage gap (intentionally out of scope; ...)`` blocks in the
    transformation specs (Phase 226.D4) for the canonical use of this
    convention.
    """
    out: list[str] = []
    in_gap = False
    for line in content.splitlines(keepends=True):
        if not in_gap:
            if _GAP_BLOCK_HEAD_RE.search(line):
                in_gap = True
                # Drop the head line entirely so a same-line declaration like
                # "Coverage gap: UC-XXX-002" doesn't slip through. The label
                # itself does not contain UC IDs by convention.
                continue
            out.append(line)
            continue
        # in_gap == True
        stripped = line.strip()
        # Block ends at a blank line, a blank JSDoc/Python-docstring line
        # (`*` or `#` alone), or any line that's not continuing a comment.
        is_blank_comment = stripped in ("", "*", "*/", "#") or re.fullmatch(
            r"[*#/]+\s*", stripped or ""
        ) is not None
        is_continuing_comment = bool(re.match(r"^\s*(\*|#|//)", line))
        if is_blank_comment or not is_continuing_comment:
            in_gap = False
            out.append(line)
        # else: drop the line — it is inside the gap region.
    return "".join(out)


def find_references_in_file(file_path: Path, ids: list[str]) -> list[str]:
    """
    Return which of the given IDs appear in the file content (docstring, name).

    Text inside ``Coverage gap`` / ``NOT covered`` comment blocks is removed
    before matching — see :func:`strip_gap_blocks`.
    """
    try:
        content = file_path.read_text()
    except Exception:
        return []
    scanned = strip_gap_blocks(content)
    found: list[str] = []
    for id_ in ids:
        if id_ in scanned:
            found.append(id_)
    return found


def find_markers_in_file(file_path: Path) -> tuple[list[str], list[str]]:
    """
    Extract UC and journey IDs from pytest markers in file content.
    Supports: @pytest.mark.uc("UC-XXX"), @pytest.mark.journey("JOURNEY-XXX"),
    pytestmark = [pytest.mark.uc("UC-XXX"), ...].
    Returns (uc_ids, journey_ids).
    """
    try:
        content = file_path.read_text()
    except Exception:
        return [], []
    uc_ids: list[str] = []
    journey_ids: list[str] = []
    # @pytest.mark.uc("UC-XXX") or pytest.mark.uc("UC-XXX")
    for m in re.finditer(r'pytest\.mark\.uc\s*\(\s*["\'](UC-[A-Za-z0-9-]+)["\']', content):
        uc_ids.append(m.group(1))
    for m in re.finditer(r'pytest\.mark\.journey\s*\(\s*["\'](JOURNEY-[A-Za-z0-9-]+)["\']', content):
        journey_ids.append(m.group(1))
    return sorted(set(uc_ids)), sorted(set(journey_ids))


def infer_scenario_coverage_from_file(file_path: Path) -> dict[str, bool]:
    """
    Infer Success / Failure / Edge scenario coverage from test file content.
    Scans for describe('Success'), describe('Failure'), describe('Edge') (Playwright/Jest)
    and for status 401/403/404/400/429, failure/edge keywords in test names.
    Returns {"success": bool, "failure": bool, "edge": bool}.
    """
    try:
        content = file_path.read_text()
    except Exception:
        return {"success": False, "failure": False, "edge": False}
    content_lower = content.lower()
    success = (
        "describe('success'" in content_lower
        or 'describe("success"' in content_lower
        or "test.describe('success'" in content_lower
        or "describe('Success'" in content
        or "test.describe('Success'" in content
    )
    failure = (
        "describe('failure'" in content_lower
        or 'describe("failure"' in content_lower
        or "test.describe('Failure'" in content
        or "401" in content
        or "403" in content
        or "404" in content
        or "400" in content
        or "429" in content
        or "unauthorized" in content_lower
        or "forbidden" in content_lower
    )
    edge = (
        "describe('edge'" in content_lower
        or 'describe("edge"' in content_lower
        or "test.describe('Edge'" in content
        or " edge " in content_lower
        or "empty" in content_lower
        or "pagination" in content_lower
        or "max length" in content_lower
        or "special char" in content_lower
    )
    return {"success": success, "failure": failure, "edge": edge}


def build_scenario_coverage(
    root: Path,
    uc_to_files: dict[str, list[str]],
    journey_to_files: dict[str, list[str]],
) -> tuple[dict[str, dict[str, bool]], dict[str, dict[str, bool]]]:
    """
    For each UC and each journey, aggregate scenario coverage (Success/Failure/Edge)
    from the test files that reference them.
    Returns (uc_scenario, journey_scenario) where each value is
    {"success": bool, "failure": bool, "edge": bool}.
    """
    def aggregate(files: list[str]) -> dict[str, bool]:
        out: dict[str, bool] = {"success": False, "failure": False, "edge": False}
        for rel in files:
            path = root / rel
            if not path.is_file():
                continue
            cov = infer_scenario_coverage_from_file(path)
            out["success"] = out["success"] or cov["success"]
            out["failure"] = out["failure"] or cov["failure"]
            out["edge"] = out["edge"] or cov["edge"]
        return out

    uc_scenario: dict[str, dict[str, bool]] = {
        uc: aggregate(uc_to_files.get(uc, [])) for uc in uc_to_files
    }
    journey_scenario: dict[str, dict[str, bool]] = {
        j: aggregate(journey_to_files.get(j, [])) for j in journey_to_files
    }
    return uc_scenario, journey_scenario


def build_coverage(
    root: Path,
    uc_ids: list[str],
    journey_ids: list[str],
    test_files: list[Path],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Build UC → [files] and Journey → [files] by scanning test files.
    Uses both content scan (docstrings, names) and pytest marker scan.
    """
    uc_to_files: dict[str, list[str]] = {uc: [] for uc in uc_ids}
    journey_to_files: dict[str, list[str]] = {j: [] for j in journey_ids}
    all_ids = uc_ids + journey_ids

    for f in test_files:
        rel = str(f.relative_to(root))
        found = find_references_in_file(f, all_ids)
        for id_ in found:
            if id_.startswith("UC-"):
                uc_to_files.setdefault(id_, []).append(rel)
            else:
                journey_to_files.setdefault(id_, []).append(rel)
        marker_ucs, marker_journeys = find_markers_in_file(f)
        for id_ in marker_ucs:
            if id_ in uc_ids:
                uc_to_files.setdefault(id_, []).append(rel)
        for id_ in marker_journeys:
            if id_ in journey_ids:
                journey_to_files.setdefault(id_, []).append(rel)

    for k in list(uc_to_files.keys()):
        uc_to_files[k] = sorted(set(uc_to_files[k]))
    for k in list(journey_to_files.keys()):
        journey_to_files[k] = sorted(set(journey_to_files[k]))
    return uc_to_files, journey_to_files


def audit_traceability(root: Path, traceability_path: Path) -> list[str]:
    """Extract file paths from TEST_TRACEABILITY.md and check they exist. Return broken."""
    content = traceability_path.read_text()
    # Paths like `hub/apps/...` or hub/apps/... or tests/... or frontend/...
    pattern = r"(?:^|\s|`)((?:hub/apps/|tests/|frontend/)[a-zA-Z0-9_/.-]+\.(?:py|ts))\b"
    paths = set(re.findall(pattern, content))
    broken: list[str] = []
    for p in paths:
        if "..." in p or "**" in p:
            continue
        full = root / p
        if not full.is_file():
            broken.append(p)
    return sorted(broken)


def load_critical_list(path: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    """
    Load critical UC/journey IDs and thresholds from YAML.
    Returns (critical_use_cases, critical_journeys, thresholds).
    thresholds may contain uc_coverage_percent, journey_coverage_percent.
    """
    if not yaml:
        raise RuntimeError("PyYAML is required for --ci-mode; install pyyaml")
    raw = yaml.safe_load(path.read_text()) or {}
    critical_ucs: list[str] = list(raw.get("critical_use_cases") or [])
    critical_journeys: list[str] = list(raw.get("critical_journeys") or [])
    thresholds: dict[str, Any] = dict(raw.get("thresholds") or {})
    return critical_ucs, critical_journeys, thresholds


def run_ci_mode(
    root: Path,
    uc_ids: list[str],
    journey_ids: list[str],
    uc_to_files: dict[str, list[str]],
    journey_to_files: dict[str, list[str]],
    critical_ucs: list[str],
    critical_journeys: list[str],
    uc_threshold_pct: float,
    journey_threshold_pct: float,
    output_path: Path | None,
    broken_links: list[str],
    uc_scenario: dict[str, dict[str, bool]] | None = None,
    journey_scenario: dict[str, dict[str, bool]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Run CI gate logic: no critical gaps and coverage >= thresholds.
    Returns (exit_code, ci_result dict for JSON artifact).
    Fails if any critical ID in the YAML is not present in USE_CASES.md / USER_JOURNEYS.md (misconfiguration).
    """
    # Validate critical list: every critical ID must exist in the docs (avoid typos / stale YAML)
    critical_ucs_not_in_docs = [u for u in critical_ucs if u not in uc_ids]
    critical_journeys_not_in_docs = [j for j in critical_journeys if j not in journey_ids]
    if critical_ucs_not_in_docs or critical_journeys_not_in_docs:
        ci_result_misconfig: dict[str, Any] = {
            "ci_mode": True,
            "passed": False,
            "error": "critical_list_mismatch",
            "critical_use_cases_not_in_docs": critical_ucs_not_in_docs,
            "critical_journeys_not_in_docs": critical_journeys_not_in_docs,
            "summary": (
                "Traceability gate failed: critical list contains IDs not in USE_CASES.md / USER_JOURNEYS.md. "
                "Update docs/CRITICAL_UC_JOURNEY_IDS.yaml to match docs."
            ),
        }
        if output_path:
            output_path.write_text(json.dumps(ci_result_misconfig, indent=2))
        else:
            print(json.dumps(ci_result_misconfig, indent=2))
        return 1, ci_result_misconfig

    # Critical gaps: critical IDs with zero tests (only among IDs that exist in docs)
    critical_ucs_in_docs = [u for u in critical_ucs if u in uc_to_files]
    critical_journeys_in_docs = [j for j in critical_journeys if j in journey_to_files]
    critical_gaps_uc = [u for u in critical_ucs_in_docs if not uc_to_files.get(u)]
    critical_gaps_journey = [j for j in critical_journeys_in_docs if not journey_to_files.get(j)]

    # Overall coverage (over all UC/journey from USE_CASES.md and USER_JOURNEYS.md)
    total_uc = len(uc_ids)
    total_journey = len(journey_ids)
    covered_uc = sum(1 for u in uc_ids if uc_to_files.get(u))
    covered_journey = sum(1 for j in journey_ids if journey_to_files.get(j))
    uc_coverage_pct = (covered_uc / total_uc * 100.0) if total_uc else 100.0
    journey_coverage_pct = (covered_journey / total_journey * 100.0) if total_journey else 100.0

    no_critical_gaps = not critical_gaps_uc and not critical_gaps_journey
    uc_meets = uc_coverage_pct >= uc_threshold_pct
    journey_meets = journey_coverage_pct >= journey_threshold_pct
    passed = no_critical_gaps and uc_meets and journey_meets

    ci_result: dict[str, Any] = {
        "ci_mode": True,
        "passed": passed,
        "critical_gaps_uc": critical_gaps_uc,
        "critical_gaps_journey": critical_gaps_journey,
        "uc_coverage_percent": round(uc_coverage_pct, 2),
        "journey_coverage_percent": round(journey_coverage_pct, 2),
        "uc_threshold_percent": uc_threshold_pct,
        "journey_threshold_percent": journey_threshold_pct,
        "total_use_cases": total_uc,
        "total_journeys": total_journey,
        "covered_use_cases": covered_uc,
        "covered_journeys": covered_journey,
        "critical_use_cases_count": len(critical_ucs_in_docs),
        "critical_journeys_count": len(critical_journeys_in_docs),
        "broken_traceability_links": broken_links,
    }
    if uc_scenario is not None:
        ci_result["scenario_coverage_use_cases"] = uc_scenario
    if journey_scenario is not None:
        ci_result["scenario_coverage_user_journeys"] = journey_scenario
    # Include summary for PR comment (short message)
    if passed:
        ci_result["summary"] = (
            f"Traceability gate passed: UC coverage {uc_coverage_pct:.1f}% (≥{uc_threshold_pct}%), "
            f"journey coverage {journey_coverage_pct:.1f}% (≥{journey_threshold_pct}%), no critical gaps."
        )
    else:
        parts = []
        if critical_gaps_uc:
            parts.append(f"{len(critical_gaps_uc)} critical UC(s) with no tests: {', '.join(critical_gaps_uc[:10])}{'...' if len(critical_gaps_uc) > 10 else ''}")
        if critical_gaps_journey:
            parts.append(f"{len(critical_gaps_journey)} critical journey(s) with no tests: {', '.join(critical_gaps_journey[:10])}{'...' if len(critical_gaps_journey) > 10 else ''}")
        if not uc_meets:
            parts.append(f"UC coverage {uc_coverage_pct:.1f}% below threshold {uc_threshold_pct}%")
        if not journey_meets:
            parts.append(f"Journey coverage {journey_coverage_pct:.1f}% below threshold {journey_threshold_pct}%")
        ci_result["summary"] = "Traceability gate failed: " + "; ".join(parts)

    if output_path:
        output_path.write_text(json.dumps(ci_result, indent=2))
    else:
        print(json.dumps(ci_result, indent=2))

    return (0 if passed else 1, ci_result)


def _scenario_cell(scenario: dict[str, bool]) -> str:
    """Format scenario coverage as a compact cell: S/F/E with ✅/⏳."""
    s = "S✅" if scenario.get("success") else "S⏳"
    f = "F✅" if scenario.get("failure") else "F⏳"
    e = "E✅" if scenario.get("edge") else "E⏳"
    return f"{s} {f} {e}"


def output_markdown(
    uc_to_files: dict[str, list[str]],
    journey_to_files: dict[str, list[str]],
    broken_links: list[str] | None,
    uc_scenario: dict[str, dict[str, bool]] | None = None,
    journey_scenario: dict[str, dict[str, bool]] | None = None,
) -> None:
    """Print Markdown report to stdout. Optionally include scenario coverage (Success/Failure/Edge)."""
    print("# Use Case and User Journey Test Coverage Report\n")
    print("## Use cases → test files | scenario coverage\n")
    print("| UC ID | Tests | Scenario (S=Success, F=Failure, E=Edge) |")
    print("|-------|-------|------------------------------------------|")
    for uc, files in sorted(uc_to_files.items()):
        status = "✅" if files else "⚠️ no tests"
        scenario_cell = _scenario_cell(uc_scenario[uc]) if uc_scenario and uc in uc_scenario else "—"
        files_preview = ", ".join(f"[{Path(f).name}]({f})" for f in files[:3]) if files else "—"
        if len(files) > 3:
            files_preview += f" +{len(files) - 3} more"
        print(f"| **{uc}** | {status} {files_preview} | {scenario_cell} |")
    print("\n## User journeys → test files | scenario coverage\n")
    print("| Journey ID | Tests | Scenario (S=Success, F=Failure, E=Edge) |")
    print("|------------|-------|------------------------------------------|")
    for j, files in sorted(journey_to_files.items()):
        status = "✅" if files else "⚠️ no tests"
        scenario_cell = _scenario_cell(journey_scenario[j]) if journey_scenario and j in journey_scenario else "—"
        files_preview = ", ".join(f"[{Path(f).name}]({f})" for f in files[:3]) if files else "—"
        if len(files) > 3:
            files_preview += f" +{len(files) - 3} more"
        print(f"| **{j}** | {status} {files_preview} | {scenario_cell} |")
    zero_uc = [uc for uc, files in uc_to_files.items() if not files]
    zero_journey = [j for j, files in journey_to_files.items() if not files]
    if zero_uc or zero_journey:
        print("\n## Zero-test items\n")
        if zero_uc:
            print(f"- Use cases with no tests: {len(zero_uc)} — {', '.join(zero_uc[:15])}{'...' if len(zero_uc) > 15 else ''}")
        if zero_journey:
            print(f"- Journeys with no tests: {len(zero_journey)} — {', '.join(zero_journey[:15])}{'...' if len(zero_journey) > 15 else ''}")
    if broken_links:
        print("\n## Broken file links (TEST_TRACEABILITY.md)\n")
        for p in broken_links:
            print(f"- `{p}`")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report UC/journey → test file coverage (task 5.5)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of Markdown",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write report to FILE (default: stdout)",
    )
    parser.add_argument(
        "--fail-if-zero",
        action="store_true",
        help="Exit 1 if any UC or journey has zero tests",
    )
    parser.add_argument(
        "--audit-traceability",
        action="store_true",
        help="Check TEST_TRACEABILITY.md file paths exist; report broken links",
    )
    parser.add_argument(
        "--ci-mode",
        action="store_true",
        help="CI gate: exit 0 only when no critical gaps and coverage >= threshold; output JSON artifact",
    )
    parser.add_argument(
        "--critical-list",
        metavar="FILE",
        default=None,
        help="YAML file with critical_use_cases, critical_journeys, thresholds (default: docs/CRITICAL_UC_JOURNEY_IDS.yaml)",
    )
    parser.add_argument(
        "--uc-threshold",
        type=float,
        default=None,
        metavar="PERCENT",
        help="Min UC coverage percent (default: from critical list or 70)",
    )
    parser.add_argument(
        "--journey-threshold",
        type=float,
        default=None,
        metavar="PERCENT",
        help="Min journey coverage percent (default: from critical list or 60)",
    )
    args = parser.parse_args()

    root = repo_root()
    docs = root / "docs"
    # Phase 226 E4 — tiered path resolver. Probes the canonical
    # `docs/<file>.md` location first, then falls back to
    # `docs/deprecated-doc/...` so the script stays runnable after the
    # docs reorg moved the source files. CLI override (--use-cases-path
    # / --user-journeys-path) wins over the probe when present.
    use_cases_path = resolve_doc(root, USE_CASES_CANDIDATES)
    user_journeys_path = resolve_doc(root, USER_JOURNEYS_CANDIDATES)
    traceability_path = resolve_doc(root, TRACEABILITY_CANDIDATES)

    if use_cases_path is None:
        print(
            "USE_CASES.md not found in any candidate location: "
            + ", ".join(USE_CASES_CANDIDATES),
            file=sys.stderr,
        )
        return 1
    if user_journeys_path is None:
        print(
            "USER_JOURNEYS.md not found in any candidate location: "
            + ", ".join(USER_JOURNEYS_CANDIDATES),
            file=sys.stderr,
        )
        return 1

    uc_ids = extract_uc_ids(use_cases_path)
    journey_ids = extract_journey_ids(user_journeys_path)
    test_files = collect_test_files(root)
    uc_to_files, journey_to_files = build_coverage(
        root, uc_ids, journey_ids, test_files
    )
    uc_scenario, journey_scenario = build_scenario_coverage(
        root, uc_to_files, journey_to_files
    )

    broken_links: list[str] = []
    if args.audit_traceability or args.ci_mode:
        # Phase 226 E4 — `traceability_path` is `Path | None` after the
        # tiered resolver: None means TEST_TRACEABILITY.md was not found
        # in any candidate location (canonical or deprecated-doc). The
        # broken-links check is auxiliary, so silently skip the check
        # when the doc is missing — do not fail the gate over an
        # optional auxiliary input.
        if traceability_path is not None and traceability_path.is_file():
            broken_links = audit_traceability(root, traceability_path)

    if args.ci_mode:
        critical_list_path = Path(args.critical_list) if args.critical_list else docs / "CRITICAL_UC_JOURNEY_IDS.yaml"
        if not critical_list_path.is_file():
            print(f"Critical list not found: {critical_list_path}", file=sys.stderr)
            return 1
        try:
            critical_ucs, critical_journeys, thresholds = load_critical_list(critical_list_path)
        except Exception as e:
            print(f"Failed to load critical list: {e}", file=sys.stderr)
            return 1
        uc_threshold = args.uc_threshold if args.uc_threshold is not None else float(thresholds.get("uc_coverage_percent", 70))
        journey_threshold = args.journey_threshold if args.journey_threshold is not None else float(thresholds.get("journey_coverage_percent", 60))
        output_path = Path(args.output) if args.output else None
        exit_code, ci_result = run_ci_mode(
            root=root,
            uc_ids=uc_ids,
            journey_ids=journey_ids,
            uc_to_files=uc_to_files,
            journey_to_files=journey_to_files,
            critical_ucs=critical_ucs,
            critical_journeys=critical_journeys,
            uc_threshold_pct=uc_threshold,
            journey_threshold_pct=journey_threshold,
            output_path=output_path,
            broken_links=broken_links,
            uc_scenario=uc_scenario,
            journey_scenario=journey_scenario,
        )
        if exit_code != 0 and ci_result.get("summary"):
            print(ci_result["summary"], file=sys.stderr)
        return exit_code

    def write_report() -> None:
        if args.json:
            out = {
                "use_cases": uc_to_files,
                "user_journeys": journey_to_files,
                "scenario_coverage": {
                    "use_cases": uc_scenario,
                    "user_journeys": journey_scenario,
                },
                "broken_traceability_links": broken_links,
            }
            print(json.dumps(out, indent=2))
        else:
            output_markdown(
                uc_to_files,
                journey_to_files,
                broken_links or None,
                uc_scenario=uc_scenario,
                journey_scenario=journey_scenario,
            )

    if args.output:
        import contextlib
        with open(args.output, "w") as f:
            with contextlib.redirect_stdout(f):
                write_report()
    else:
        write_report()

    if args.fail_if_zero:
        zero_uc = [uc for uc, files in uc_to_files.items() if not files]
        zero_journey = [j for j, files in journey_to_files.items() if not files]
        if zero_uc or zero_journey:
            print(
                f"\nExit: {len(zero_uc)} UC(s) and {len(zero_journey)} journey(s) with zero tests.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
