#!/usr/bin/env python3
"""Compare a k6 summary-export against the committed performance baseline.

Extracted from the k6-load-test-gate workflow's inline python (pilot-
readiness 4.4): the regression math lived inside a `python3 -c` heredoc in
YAML — untestable, and unavailable to any local rehearsal run. The CI gate
and ``scripts/run_week1_load_test.py`` now share this single comparator.

Input: a k6 ``--summary-export`` JSON (metrics → values → p(95)/rate/count).
Baseline: tests/load/performance_baseline.json (thresholds.budget_ms /
budget_rate / budget_count).

Usage:
    python3 scripts/compare_k6_baseline.py k6-summary.json --mode blocking
    python3 scripts/compare_k6_baseline.py k6-summary.json --mode advisory \\
        --report-dir docs/operations/load-test-reports --label "week1"

Exit codes: 0 no regression (or advisory mode); 1 regression in blocking
mode; 2 usage/parse failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "tests" / "load" / "performance_baseline.json"
DEFAULT_SCALE = REPO_ROOT / "tests" / "load" / "week1_scale.json"

# k6 metric name → baseline threshold key (same mapping the CI gate used).
METRIC_TO_BASELINE = {
    "journey_login_latency_ms": "journey_login_latency_ms_p95",
    "journey_asset_crud_latency_ms": "journey_asset_crud_latency_ms_p95",
    "journey_contract_workflow_latency_ms": "journey_contract_workflow_latency_ms_p95",
    "journey_marketplace_latency_ms": "journey_marketplace_latency_ms_p95",
    "journey_search_latency_ms": "journey_search_latency_ms_p95",
    "journey_sparql_latency_ms": "journey_sparql_latency_ms_p95",
    "journey_file_upload_latency_ms": "journey_file_upload_latency_ms_p95",
    "journey_compliance_scan_latency_ms": "journey_compliance_scan_latency_ms_p95",
    "journey_governance_latency_ms": "journey_governance_latency_ms_p95",
    "journey_webhook_latency_ms": "journey_webhook_latency_ms_p95",
    "http_req_duration": "http_req_duration_p95",
}


def load_summary(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read k6 summary {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def load_baseline(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read baseline {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def compare(
    summary: dict, baseline: dict
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """Return (within, regressions, missing, extra_regressions).

    `extra_regressions` carries the HTTP-level checks (failure rate,
    success rate, error count) as human-readable strings.
    """
    metrics = summary.get("metrics", {})
    thresholds = baseline.get("thresholds", {})
    within: list[dict] = []
    regressions: list[dict] = []
    missing: list[dict] = []
    extra: list[str] = []

    def _metric_value(metric: dict, key: str) -> float | None:
        """k6 summary-export shapes differ by version: 0.51 nests under
        ``values`` (the CI gate's format), 0.55+ puts p(95)/rate/count at
        the TOP level of each metric. Accept both."""
        nested = metric.get("values", {})
        if key in nested:
            return nested[key]
        return metric.get(key)

    for metric_name, baseline_key in METRIC_TO_BASELINE.items():
        metric = metrics.get(metric_name, {})
        p95 = _metric_value(metric, "p(95)")
        budget = thresholds.get(baseline_key, {}).get("budget_ms")
        desc = thresholds.get(baseline_key, {}).get("description", baseline_key)
        if p95 is None:
            missing.append({"metric": metric_name, "baseline_key": baseline_key})
            continue
        if budget is None:
            missing.append({"metric": metric_name, "baseline_key": baseline_key})
            continue
        row = {
            "metric": metric_name,
            "baseline_key": baseline_key,
            "description": desc,
            "p95_ms": p95,
            "budget_ms": budget,
        }
        if p95 > budget:
            regressions.append(row)
        else:
            within.append(row)

    failed_rate = _metric_value(metrics.get("http_req_failed", {}), "rate") or 0
    failed_budget = thresholds.get("http_req_failed_rate", {}).get("budget_rate", 0.02)
    if failed_rate > failed_budget:
        extra.append(
            f"HTTP failure rate: {failed_rate:.3f} > {failed_budget:.3f}"
        )

    success_rate = _metric_value(metrics.get("journey_success_rate", {}), "rate")
    if success_rate is None:
        success_rate = 1
    success_budget = thresholds.get("journey_success_rate", {}).get(
        "budget_rate", 0.99
    )
    if success_rate < success_budget:
        extra.append(
            f"Journey success rate: {success_rate:.3f} < {success_budget:.3f}"
        )

    error_count = _metric_value(
        metrics.get("journey_api_errors_total", {}), "count"
    ) or 0
    error_budget = thresholds.get("journey_api_errors_total", {}).get(
        "budget_count", 1000
    )
    if error_count > error_budget:
        extra.append(f"API error count: {error_count} > {error_budget}")

    return within, regressions, missing, extra


def write_report(
    report_dir: Path,
    label: str,
    mode: str,
    within: list[dict],
    regressions: list[dict],
    missing: list[dict],
    extra: list[str],
    scale: dict | None,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    month = datetime.now(UTC).strftime("%Y-%m")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    json_path = report_dir / month / f"load-test-{stamp}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "advisory":
        status = "ADVISORY"
    elif regressions or extra:
        status = "FAILED"
    else:
        status = "PASSED"

    report = {
        "comparison": "k6-critical-journeys-vs-baseline",
        "label": label,
        "mode": mode,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "within": within,
        "regressions": regressions,
        "missing": missing,
        "http_level": extra,
        "scale": scale,
    }
    json_path.write_text(json.dumps(report, indent=2))

    md = f"""# Load Test — {label or "run"} — {stamp[:10]}

| Field | Value |
|---|---|
| Mode | `{mode}` |
| Status | **{status}** |
| Within budget | {len(within)} |
| Regressions | {len(regressions)} |
| Missing metrics | {len(missing)} |

"""
    if regressions:
        md += "## Regressions\n\n| Metric | p95 | Budget |\n|---|---|---|\n"
        for row in regressions:
            md += (
                f"| `{row['metric']}` | {row['p95_ms']:.0f}ms | "
                f"{row['budget_ms']}ms |\n"
            )
    if extra:
        md += "\n## HTTP-level findings\n\n"
        for line in extra:
            md += f"- {line}\n"
    if not regressions and not extra:
        md += "No regressions against the committed baseline.\n"
    (json_path.with_suffix(".md")).write_text(md)
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--scale", type=Path, default=DEFAULT_SCALE)
    parser.add_argument(
        "--mode",
        choices=["blocking", "advisory"],
        default="blocking",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "operations" / "load-test-reports",
    )
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="append regression_count/within_budget_count to $GITHUB_OUTPUT "
        "(CI step-output contract, replaces the retired inline python)",
    )
    args = parser.parse_args()

    summary = load_summary(args.summary_json)
    baseline = load_baseline(args.baseline)
    try:
        scale = json.loads(args.scale.read_text()) if args.scale.exists() else None
    except (OSError, json.JSONDecodeError):
        scale = None

    within, regressions, missing, extra = compare(summary, baseline)

    print(f"k6 vs baseline ({args.mode} mode):")
    for row in within:
        print(
            f"  within budget  {row['metric']}: p95={row['p95_ms']:.0f}ms "
            f"<= {row['budget_ms']}ms"
        )
    for row in missing:
        print(f"  missing        {row['metric']} (no p(95) or no budget)")
    for row in regressions:
        pct = (
            ((row["p95_ms"] - row["budget_ms"]) / row["budget_ms"]) * 100
            if row["budget_ms"]
            else 0
        )
        print(
            f"  REGRESSION     {row['metric']} ({row['description']}): "
            f"p95={row['p95_ms']:.0f}ms > budget={row['budget_ms']}ms (+{pct:.0f}%)"
        )
    for line in extra:
        print(f"  REGRESSION     {line}")

    report_path = write_report(
        args.report_dir, args.label, args.mode, within, regressions, missing, extra, scale
    )
    print(f"report: {report_path}")

    if args.github_output:
        outputs = os.environ.get("GITHUB_OUTPUT", "")
        if outputs:
            with open(outputs, "a") as out:
                out.write(f"regression_count={len(regressions) + len(extra)}\n")
                out.write(f"within_budget_count={len(within)}\n")

    if args.mode == "advisory":
        print("advisory mode — regressions recorded but not blocking")
        return 0
    if regressions or extra:
        print("BLOCKING: regressions detected")
        return 1
    print("PASSED: all metrics within budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
