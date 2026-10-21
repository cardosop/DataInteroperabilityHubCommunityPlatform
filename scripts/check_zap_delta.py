#!/usr/bin/env python3
"""GATE-64 — ZAP DAST delta gate (oss-release-remediation W11.11).

Compares a ZAP ``-J`` JSON report against a committed baseline and
fails on NEW HIGH-risk alerts.  An alert's identity is its
``(pluginid, normalized-URI)`` pair:

* **new high** — a HIGH pair absent from the baseline entirely.
* **escalation** — a pair the baseline carried at MEDIUM/LOW that now
  reports HIGH (also fails; the gate must never hide a worsening).
  Escalated pairs are reported ONLY in the escalation bucket — a
  single pair is never double-counted across buckets.
* new MEDIUM/LOW, resolved HIGHs, and count drift on known HIGHs are
  REPORTED but do not fail — the W11.11 acceptance is
  *delta vs baseline zero-new-highs*.

Matching is conservative by construction: URIs are normalized only by
scheme/host case, default-port elision, trailing-slash elision, and
fragment removal — query strings keep their values, so a high at a NEW
query value counts as new (an over-merge could hide a new finding;
false-positive gate failures are the safe direction).

``--verify-baselines`` validates every committed baseline named in the
surface manifest (parseable, real ``site`` payload) — the quality-gates
wiring that runs without ZAP or a staging target.

Exit codes: 0 = no new highs; 1 = new highs / baseline verification
failure; 2 = usage or parse error (a broken report is NOT a pass).

Usage:
  python scripts/check_zap_delta.py --scan zap.json --baseline base.json \
      --report delta.json --surface TENANT_ADMIN --ci
  python scripts/check_zap_delta.py --verify-baselines [--manifest FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "scripts" / "zap" / "w1111_role_matrix.json"
DEFAULT_BASELINE_DIR = PROJECT_ROOT / "docs" / "security" / "zap" / "baselines"

HIGH_RISK = "3"

_USAGE_ERROR = 2
_GATE_FAILURE = 1
_OK = 0


class ReportError(ValueError):
    """A ZAP report that cannot be parsed as the wire shape."""


def _norm_uri(uri: str) -> str:
    """Conservative URI identity normalization (see module docstring)."""
    try:
        parts = urlsplit(uri)
    except ValueError:
        # Malformed URI (e.g. invalid port) — keep the raw form as its
        # identity; the gate must never crash on scanner output.
        return uri.strip()
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    default = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if (port is None or default) else f"{host}:{port}"
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # Query params keep their values (conservative matching); sort the
    # pairs so equivalent orderings do not manufacture drift.
    query = "&".join(sorted(parts.query.split("&"))) if parts.query else ""
    return urlunsplit((scheme, netloc, path, query, ""))


def _risk_of(alert: dict) -> str:
    """The alert's risk code, with the riskdesc prefix as fallback."""
    code = str(alert.get("riskcode", "")).strip()
    if code:
        return code
    desc = (alert.get("riskdesc") or "").split(" ")[0].lower()
    return {"high": HIGH_RISK, "medium": "2", "low": "1"}.get(desc, "0")


def _load_report(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"{label} report unreadable: {path}: {exc}") from exc
    if "site" not in data:
        raise ReportError(f"{label} report has no 'site' key: {path}")
    return data


def _identity_pairs(data: dict) -> dict[tuple[str, str], str]:
    """Map every (pluginid, normalized-URI) pair to its risk code."""
    pairs: dict[tuple[str, str], str] = {}
    for site in data.get("site", []):
        site_name = site.get("@name", "")
        for alert in site.get("alerts", []):
            pluginid = str(alert.get("pluginid", alert.get("alertRef", "")))
            if not pluginid:
                continue
            risk = _risk_of(alert)
            instances = alert.get("instances") or []
            if not instances:
                # Site-level alert (e.g. header-missing checks) — its
                # identity is the site itself.
                pairs[(pluginid, _norm_uri(site_name))] = risk
                continue
            for instance in instances:
                uri = instance.get("uri") or site_name
                pairs[(pluginid, _norm_uri(uri))] = risk
    return pairs


def _alert_summaries(data: dict, pairs: set[tuple[str, str]]) -> list[dict]:
    """Human-readable entries for the pairs that FAILED the gate."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for site in data.get("site", []):
        site_name = site.get("@name", "")
        for alert in site.get("alerts", []):
            pluginid = str(alert.get("pluginid", alert.get("alertRef", "")))
            instances = alert.get("instances") or [{}]
            for instance in instances:
                uri = instance.get("uri") or site_name
                key = (pluginid, _norm_uri(uri))
                if key in pairs and key not in seen:
                    seen.add(key)
                    out.append(
                        {
                            "pluginid": pluginid,
                            "name": alert.get("name", ""),
                            "uri": uri,
                            "method": instance.get("method", ""),
                        }
                    )
    return out


def _compare(scan: dict, baseline: dict) -> dict:
    scan_pairs = _identity_pairs(scan)
    baseline_pairs = _identity_pairs(baseline)

    scan_high = {k for k, r in scan_pairs.items() if r == HIGH_RISK}
    baseline_high = {k for k, r in baseline_pairs.items() if r == HIGH_RISK}
    baseline_any = set(baseline_pairs)

    escalated = scan_high & (baseline_any - baseline_high)
    new_highs = scan_high - baseline_any
    resolved = baseline_high - scan_high
    new_medium_low = sum(
        1 for k, r in scan_pairs.items() if r != HIGH_RISK and k not in baseline_any
    )

    verdict = "FAIL" if (new_highs or escalated) else "PASS"
    return {
        "verdict": verdict,
        "new_highs": _alert_summaries(scan, new_highs),
        "escalated": _alert_summaries(scan, escalated),
        "resolved_high_count": len(resolved),
        "new_medium_low_count": new_medium_low,
        "scan_high_count": len(scan_high),
        "baseline_high_count": len(baseline_high),
    }


def _verify_baselines(manifest_path: Path, baseline_dir: Path) -> int:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: manifest unreadable ({manifest_path}): {exc}", file=sys.stderr)
        return _GATE_FAILURE
    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        print(f"FAIL: manifest {manifest_path} has no surfaces", file=sys.stderr)
        return _GATE_FAILURE

    failures = 0
    for surface in surfaces:
        baseline_path = Path(surface["baseline"])
        if not baseline_path.is_absolute():
            baseline_path = baseline_dir / surface["baseline"]
        key = surface.get("key", "?")
        if not baseline_path.is_file():
            print(f"FAIL: baseline missing for {key}: {baseline_path}", file=sys.stderr)
            failures += 1
            continue
        try:
            data = _load_report(baseline_path, key)
        except ReportError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            failures += 1
            continue
        pairs = _identity_pairs(data)
        sites = len(data.get("site", []))
        print(f"OK: {key}: {sites} site(s), {len(pairs)} alert identity pair(s)")
    if failures:
        return _GATE_FAILURE
    return _OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", help="ZAP -J JSON report (the new scan)")
    parser.add_argument("--baseline", help="committed baseline ZAP -J JSON")
    parser.add_argument("--report", help="write the machine-readable delta JSON here")
    parser.add_argument("--surface", default="zap", help="surface label for the report")
    parser.add_argument("--ci", action="store_true", help="CI mode (summary to stdout)")
    parser.add_argument(
        "--verify-baselines", action="store_true", help="validate all committed baselines"
    )
    parser.add_argument(
        "--manifest", default=str(DEFAULT_MANIFEST), help="surface manifest (test seam)"
    )
    parser.add_argument(
        "--baseline-dir", default=str(DEFAULT_BASELINE_DIR), help="baseline directory"
    )
    args = parser.parse_args(argv)

    if args.verify_baselines:
        return _verify_baselines(Path(args.manifest), Path(args.baseline_dir))

    if not args.scan or not args.baseline:
        parser.error("--scan and --baseline are required (or --verify-baselines)")
        return _USAGE_ERROR

    try:
        scan = _load_report(Path(args.scan), "scan")
        baseline = _load_report(Path(args.baseline), "baseline")
    except ReportError as exc:
        print(str(exc), file=sys.stderr)
        return _USAGE_ERROR

    result = _compare(scan, baseline)
    result["surface"] = args.surface
    result["scan"] = args.scan
    result["baseline"] = args.baseline

    if args.report:
        Path(args.report).write_text(json.dumps(result, indent=2) + "\n")

    if result["verdict"] == "FAIL":
        for entry in result["new_highs"]:
            print(f"NEW HIGH: {entry['pluginid']} {entry['name']} {entry['method']} {entry['uri']}")
        for entry in result["escalated"]:
            print(
                f"ESCALATED TO HIGH: {entry['pluginid']} {entry['name']} "
                f"{entry['method']} {entry['uri']}"
            )
        print(
            f"GATE-64 FAIL: {args.surface} — "
            f"{len(result['new_highs'])} new high(s), "
            f"{len(result['escalated'])} escalated"
        )
        return _GATE_FAILURE

    print(
        f"GATE-64 PASS: {args.surface} — 0 new highs, "
        f"{result['resolved_high_count']} resolved, "
        f"{result['new_medium_low_count']} new medium/low"
    )
    return _OK


if __name__ == "__main__":
    sys.exit(main())
