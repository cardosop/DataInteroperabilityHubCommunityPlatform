#!/usr/bin/env python3
"""
Phase 250.0.15 / D250.13 — stale feature-flag detector.

Loads ``hub.apps.tenants.feature_flag_registry.REGISTRY``, computes
age-since-retire-by for each {GA, DEPRECATED} flag, classifies severity,
and prints a structured report. Per the lifecycle policy, this script
NEVER fails CI (stale flags are tech debt, not merge gates) — it
emits a report that the weekly Tech Debt review consumes.

Severity classification (per the policy):
* **CRITICAL** — flag exceeds ``retire_by`` by MORE than 180 days.
* **WARNING** — flag exceeds ``retire_by`` by 90-180 days.
* **INFO** — flag exceeds ``retire_by`` by 0-90 days.
* (no row emitted) — flag is within its retirement window OR has no
  retire_by (DRAFT / CANARY / RETIRED stages).

Usage
-----
::

    python scripts/detect_stale_feature_flags.py

The script imports the registry directly — it does NOT need a running
Django app context (the registry is pure Python).

Exit code: ALWAYS 0. CI integration treats this as informational
output only.

Output formats
--------------
* Human-readable table on stdout (default).
* ``--json`` flag emits JSON for the Slack-digest cron job + Prometheus
  exporter.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


# Make ``hub.apps.tenants.feature_flag_registry`` importable without a
# full Django bootstrap. The registry is pure Python.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _load_registry():
    """Defer import so the script doesn't fail if Django settings are
    misconfigured — the registry module itself imports nothing from
    Django."""
    # Adjust imports to bypass the normal Django app loader.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "feature_flag_registry",
        _REPO_ROOT / "hub" / "apps" / "tenants" / "feature_flag_registry.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load feature_flag_registry module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["feature_flag_registry"] = module
    spec.loader.exec_module(module)
    return module.REGISTRY


def _classify(days_overdue: int) -> Literal["CRITICAL", "WARNING", "INFO"]:
    if days_overdue > 180:
        return "CRITICAL"
    if days_overdue > 90:
        return "WARNING"
    return "INFO"


def _scan(now: datetime) -> list[dict]:
    """Return one dict per stale flag, sorted by severity then days-overdue."""
    registry = _load_registry()
    rows: list[dict] = []
    for flag in registry:
        if flag.retire_by is None:
            continue
        if flag.retire_by >= now:
            continue
        days_overdue = (now - flag.retire_by).days
        rows.append({
            "name": flag.name,
            "stage": flag.stage,
            "owner_team": flag.owner_team,
            "owner_email": flag.owner_email,
            "retire_by": flag.retire_by.isoformat(),
            "days_overdue": days_overdue,
            "severity": _classify(days_overdue),
            "related_phase": flag.related_phase,
        })
    # Sort by severity (CRITICAL > WARNING > INFO), then days_overdue desc.
    severity_rank = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    rows.sort(key=lambda r: (severity_rank[r["severity"]], -r["days_overdue"]))
    return rows


def _format_human(rows: list[dict]) -> str:
    if not rows:
        return "✓ No stale feature flags. All flags within retirement window.\n"
    lines: list[str] = []
    lines.append(
        f"⚠ {len(rows)} stale feature flag(s) detected. "
        "Review at the weekly Tech Debt meeting per "
        "docs/runbooks/feature-flag-lifecycle.md."
    )
    lines.append("")
    lines.append(f"{'SEVERITY':<10}{'FLAG':<45}{'STAGE':<12}{'OWNER':<25}{'OVERDUE':>10}")
    lines.append("-" * 102)
    for r in rows:
        lines.append(
            f"{r['severity']:<10}"
            f"{r['name']:<45}"
            f"{r['stage']:<12}"
            f"{r['owner_team']:<25}"
            f"{r['days_overdue']:>7} d"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 250.0.15 — stale feature-flag detector."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable table.",
    )
    parser.add_argument(
        "--now",
        help="Override 'now' for testing (ISO 8601 timestamp).",
        default=None,
    )
    args = parser.parse_args()

    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(tz=timezone.utc)

    rows = _scan(now)

    if args.json:
        json.dump({"detected_at": now.isoformat(), "stale_flags": rows}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_human(rows))

    # Per policy: NEVER fail CI on stale flags. Always exit 0.
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
