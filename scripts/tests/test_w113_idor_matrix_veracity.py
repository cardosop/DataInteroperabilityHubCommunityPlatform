"""W11.3 (oss-release-remediation) — ASVS V4 access-control matrix veracity pins.

The IDOR probe matrix ships as a generated manifest plus a human-authored
allowlist, a rendered matrix doc, a committed coverage report, and the
parametrized probe suite that consumes the manifest.  These pins keep the
matrix HONEST (the P4 rule, applied to security coverage claims):

  * the manifest exists, parses, and every route key carries a complete
    disposition (probe / allowlist / platform_admin / no_tenant_fk /
    unresolved);
  * the allowlist exists and EVERY entry carries a written reason — an
    unreasoned entry is the vibe-code signature of "defense in depth as
    prose" (register row 9);
  * every allowlist entry still matches a route in the manifest — a dead
    entry fails (the W12 house ratchet, dead-anchor convention);
  * every probed route has a synthesis strategy recorded (generic or a
    named creator) — unexplained synthesis failures are blocked;
  * the static coverage math — probed / (probed + allowlisted) — is at
    least the 95% task threshold;
  * the matrix doc and the coverage report exist and carry the numbers;
  * the probe suite exists and consumes the manifest (string-cited);
  * this pin is actually wired into the CI lint pin list — an unwired
    gate is register row 20 (machinery built but never adopted).

RED phase: before the manifest shipped, the existence pins fail
(collection-level FileNotFoundError); after, the mechanical checks verify
every cross-artifact claim — no mocks, the real tree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = REPO_ROOT / "docs" / "api-audit" / "idor-probe-manifest.json"
ALLOWLIST = REPO_ROOT / "lint" / "idor-coverage-allowlist.yml"
MATRIX_DOC = (
    REPO_ROOT / "docs" / "security" / "adversarial-matrices" / "w113-access-control-matrix.md"
)
COVERAGE_REPORT = REPO_ROOT / "docs" / "audits" / "w113-idor-coverage-2026-10-15.md"
PROBE_SUITE = REPO_ROOT / "tests" / "security" / "test_w113_asvs_v4_access_control.py"
CI_LINT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "_reusable.lint.yml"

COVERAGE_THRESHOLD_PCT = 95.0

# Dispositions the generator is allowed to record.  Everything outside
# {probe, allowlist} is excluded from the denominator by the documented
# scope rule; the coverage math only counts probe vs allowlist.
VALID_DISPOSITIONS = {"probe", "allowlist", "platform_admin", "no_tenant_fk", "unresolved"}

REQUIRED_ROUTE_FIELDS = (
    "key",
    "method",
    "path_template",
    "url_name",
    "url_mode",
    "lookup_field",
    "view_class",
    "model",
    "app",
    "disposition",
    "probe_role",
    "synthesis",
    "allowlist_reason",
    "methods_present",
)


def _load_manifest():
    if not MANIFEST.is_file():
        raise FileNotFoundError(str(MANIFEST))
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _load_allowlist():
    if not ALLOWLIST.is_file():
        raise FileNotFoundError(str(ALLOWLIST))
    return yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8")) or {}


def test_manifest_exists_and_parses():
    data = _load_manifest()
    assert isinstance(data.get("routes"), list), "manifest routes must be a list"
    assert data["routes"], "manifest must carry a non-empty routes list"
    assert data.get("generated_at"), "manifest must record generated_at"
    missing_fields: list[str] = []
    for route in data["routes"]:
        for field in REQUIRED_ROUTE_FIELDS:
            if field not in route:
                missing_fields.append(f"{route.get('key')}: missing {field}")
    assert not missing_fields, "manifest routes missing fields:\n" + "\n".join(
        sorted(missing_fields)
    )


def test_every_manifest_disposition_is_valid():
    data = _load_manifest()
    bad = sorted(
        {
            f"{r['key']}: {r['disposition']}"
            for r in data["routes"]
            if r["disposition"] not in VALID_DISPOSITIONS
        }
    )
    assert not bad, "unknown dispositions:\n" + "\n".join(bad)


def test_every_probed_route_has_a_synthesis_strategy():
    """A probed route with no synthesis strategy means the suite cannot
    build the tenant-A object — the coverage claim would be prose."""
    data = _load_manifest()
    bad = [
        f"{r['key']}: synthesis={r['synthesis']!r}"
        for r in data["routes"]
        if r["disposition"] == "probe" and not r.get("synthesis")
    ]
    assert not bad, "probed routes without a synthesis strategy:\n" + "\n".join(sorted(bad))


def test_manifest_route_keys_are_unique():
    data = _load_manifest()
    keys = [r["key"] for r in data["routes"]]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate route keys in manifest: {dupes}"


def test_allowlist_exists_and_every_entry_has_a_reason():
    """Zero entries is the IDEAL state (every route probed); when entries
    exist, each must carry a written reason."""
    allow = _load_allowlist()
    entries = allow.get("entries") or []
    for entry in entries:
        method = entry.get("method")
        path = entry.get("path")
        reason = (entry.get("reason") or "").strip()
        assert method, f"allowlist entry missing method: {entry}"
        assert path, f"allowlist entry missing path: {entry}"
        assert reason, (
            f"allowlist entry {method} {path} has no written reason — "
            "every allowlisted route must say why (register row 9)"
        )


def test_every_allowlist_entry_matches_a_manifest_route():
    """Dead allowlist entries fail — the W12 dead-anchor ratchet."""
    data = _load_manifest()
    manifest_keys = {(r["method"], r["path_template"]) for r in data["routes"]}
    allow = _load_allowlist()
    dead = [
        f"{e.get('method')} {e.get('path')}"
        for e in (allow.get("entries") or [])
        if (e.get("method"), e.get("path")) not in manifest_keys
    ]
    assert not dead, "dead allowlist entries (no matching manifest route):\n" + "\n".join(
        sorted(dead)
    )


def test_allowlisted_manifest_routes_carry_the_reason():
    """The manifest is the single source of truth: every allowlisted route
    there must also carry its reason, copied from the allowlist file."""
    data = _load_manifest()
    bad = [
        r["key"]
        for r in data["routes"]
        if r["disposition"] == "allowlist" and not (r.get("allowlist_reason") or "").strip()
    ]
    assert not bad, "allowlisted manifest routes without a reason:\n" + "\n".join(sorted(bad))


def test_static_coverage_meets_the_95_percent_threshold():
    data = _load_manifest()
    probed = sum(1 for r in data["routes"] if r["disposition"] == "probe")
    allowlisted = sum(1 for r in data["routes"] if r["disposition"] == "allowlist")
    denominator = probed + allowlisted
    assert denominator > 0, "no tenant-scoped routes in the manifest denominator"
    coverage = 100.0 * probed / denominator
    assert coverage >= COVERAGE_THRESHOLD_PCT, (
        f"coverage {coverage:.2f}% is below the {COVERAGE_THRESHOLD_PCT}% task threshold "
        f"(probed={probed}, allowlisted={allowlisted})"
    )
    recorded = data.get("coverage_pct")
    assert recorded is not None, "manifest must record coverage_pct"
    assert abs(float(recorded) - coverage) < 0.05, (
        f"manifest coverage_pct {recorded} disagrees with the route dispositions ({coverage:.2f}%)"
    )


def test_matrix_doc_exists_and_cites_the_manifest():
    assert MATRIX_DOC.is_file(), "the W11.3 access-control matrix doc must be committed"
    text = MATRIX_DOC.read_text(encoding="utf-8")
    assert "idor-probe-manifest.json" in text, "matrix doc must cite the manifest path"
    for token in ("tenant-scoped", "probe", "allowlist"):
        assert token in text, f"matrix doc must discuss the {token!r} disposition"
    coverage_match = re.search(r"(9[5-9]|[1-9]\d{2})(?:\.\d+)?\s*%", text)
    assert coverage_match, "matrix doc must state the coverage figure (≥95%)"


def test_coverage_report_exists_with_the_figure():
    assert COVERAGE_REPORT.is_file(), "the W11.3 coverage report must be committed"
    text = COVERAGE_REPORT.read_text(encoding="utf-8")
    coverage_match = re.search(r"(9[5-9]|[1-9]\d{2})(?:\.\d+)?\s*%", text)
    assert coverage_match, "coverage report must state the coverage figure (≥95%)"


def test_probe_suite_exists_and_consumes_the_manifest():
    assert PROBE_SUITE.is_file(), "the parametrized probe suite must be committed"
    text = PROBE_SUITE.read_text(encoding="utf-8")
    assert "idor-probe-manifest.json" in text, (
        "probe suite must consume the manifest (string-cited path)"
    )
    assert "coverage" in text.lower(), "probe suite must carry the in-suite coverage gate test"


def test_pin_is_wired_into_ci_lint_pin_list():
    """An unwired gate is register row 20 — machinery built but never adopted."""
    assert CI_LINT_WORKFLOW.is_file(), "CI lint workflow missing"
    text = CI_LINT_WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/tests/test_w113_idor_matrix_veracity.py" in text, (
        "this pin must be listed in the GATE-29 pin list of _reusable.lint.yml"
    )
