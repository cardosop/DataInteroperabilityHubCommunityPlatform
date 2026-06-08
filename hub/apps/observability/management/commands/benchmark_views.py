"""
305.4 — View benchmark command using EXPLAIN ANALYZE (Django management command).

Usage:
    python manage.py benchmark_views
    python manage.py benchmark_views --baseline
    python manage.py benchmark_views --json
    python manage.py benchmark_views --view asset_list
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import connection

BASELINE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "scripts", "perf", "view_benchmark_baseline.json",
)
BASELINE_PATH = os.path.abspath(BASELINE_PATH)

VIEW_QUERIES: dict[str, str] = {
    "asset_list": (
        "SELECT * FROM assets ORDER BY created_at DESC LIMIT 20"
    ),
    "contract_list": (
        "SELECT * FROM contracts ORDER BY created_at DESC LIMIT 20"
    ),
    "marketplace_list": (
        "SELECT * FROM listings WHERE status = 'PUBLISHED' "
        "ORDER BY created_at DESC LIMIT 20"
    ),
    "search_fts": (
        "SELECT * FROM search_index "
        "WHERE search_vector @@ plainto_tsquery('english', 'test') "
        "ORDER BY ts_rank(search_vector, plainto_tsquery('english', 'test')) DESC "
        "LIMIT 20"
    ),
    "sparql_basic": (
        "SELECT * FROM sparql_queries ORDER BY created_at DESC LIMIT 1"
    ),
}


@dataclass
class BenchmarkResult:
    view_name: str
    planning_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    total_time_ms: float = 0.0
    plan_rows: int = 0
    error: Optional[str] = None


def _parse_explain_output(explain_json: list) -> tuple:
    if not explain_json or not isinstance(explain_json, list):
        return 0.0, 0.0, 0
    plan = explain_json[0].get("Plan", {})
    planning_time = explain_json[0].get("Planning Time", 0)
    execution_time = explain_json[0].get("Execution Time", 0)
    plan_rows = plan.get("Plan Rows", 0)
    return planning_time, execution_time, plan_rows


def run_benchmark(view_name: str, query: str) -> BenchmarkResult:
    result = BenchmarkResult(view_name=view_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"EXPLAIN (ANALYZE, FORMAT JSON) {query}"
            )
            explain_json = cursor.fetchone()[0]
        pt, et, pr = _parse_explain_output(explain_json)
        result.planning_time_ms = pt
        result.execution_time_ms = et
        result.total_time_ms = pt + et
        result.plan_rows = pr
    except Exception as exc:
        result.error = str(exc)
    return result


def load_baseline() -> dict:
    if not os.path.exists(BASELINE_PATH):
        return {}
    with open(BASELINE_PATH) as f:
        return json.load(f)


def save_baseline(results: list[BenchmarkResult]) -> None:
    baseline = {
        r.view_name: {
            "planning_time_ms": r.planning_time_ms,
            "execution_time_ms": r.execution_time_ms,
            "total_time_ms": r.total_time_ms,
            "plan_rows": r.plan_rows,
        }
        for r in results
    }
    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    with open(BASELINE_PATH, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"Baseline saved to {BASELINE_PATH}")


def compare_results(
    results: list[BenchmarkResult], baseline: dict,
) -> tuple[list[dict], bool]:
    report = []
    has_regression = False
    for r in results:
        entry = {
            "view": r.view_name, "total_time_ms": r.total_time_ms,
            "planning_time_ms": r.planning_time_ms,
            "execution_time_ms": r.execution_time_ms,
            "plan_rows": r.plan_rows, "regression_pct": 0.0,
            "regression": False, "error": r.error,
        }
        if r.error:
            entry["regression"] = True
            report.append(entry)
            continue
        if r.view_name in baseline:
            baseline_total = baseline[r.view_name]["total_time_ms"]
            if baseline_total > 0:
                delta_pct = (
                    (r.total_time_ms - baseline_total) / baseline_total * 100
                )
                entry["regression_pct"] = round(delta_pct, 1)
                if delta_pct > 20:
                    entry["regression"] = True
                    has_regression = True
        report.append(entry)
    return report, has_regression


def run_benchmarks(
    views: Optional[list[str]] = None,
    save_as_baseline: bool = False,
    json_output: bool = False,
) -> int:
    targets = VIEW_QUERIES
    if views:
        targets = {k: v for k, v in VIEW_QUERIES.items() if k in views}

    results: list[BenchmarkResult] = []
    for view_name, query in targets.items():
        result = run_benchmark(view_name, query)
        results.append(result)
        if not json_output:
            status = "✓" if not result.error else "✗"
            print(
                f"  {status} {view_name}: "
                f"planning={result.planning_time_ms:.2f}ms "
                f"execution={result.execution_time_ms:.2f}ms "
                f"rows={result.plan_rows}"
                + (f" ERROR: {result.error}" if result.error else "")
            )

    if save_as_baseline:
        save_baseline(results)
        return 0

    baseline = load_baseline()
    if not baseline:
        if json_output:
            print(json.dumps({"status": "no_baseline", "results": [
                {"view": r.view_name, "total_time_ms": r.total_time_ms}
                for r in results
            ]}, indent=2))
        else:
            print("No baseline found. Run with --baseline first.")
        return 0

    report, has_regression = compare_results(results, baseline)

    if json_output:
        print(json.dumps({
            "status": "regression" if has_regression else "ok",
            "results": report,
        }, indent=2))
    else:
        print("\nComparison against baseline:")
        for entry in report:
            flag = "⚠ REGRESSION" if entry["regression"] else "  OK"
            pct = (
                f"+{entry['regression_pct']}%"
                if entry['regression_pct'] > 0
                else f"{entry['regression_pct']}%"
            )
            print(
                f"  {flag} {entry['view']}: "
                f"{entry['total_time_ms']:.2f}ms ({pct})"
            )
        if has_regression:
            print("\n⚠ One or more views regressed >20% from baseline.")
        else:
            print("\nAll views within 20% of baseline.")

    return 1 if has_regression else 0


class Command(BaseCommand):
    help = "305.4 — Benchmark key views with EXPLAIN ANALYZE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--view", action="append", dest="views",
            help="Benchmark a specific view (repeatable).",
        )
        parser.add_argument(
            "--baseline", action="store_true", default=False,
            help="Save current results as the new baseline.",
        )
        parser.add_argument(
            "--json", action="store_true", default=False,
            help="Output results as JSON.",
        )

    def handle(self, *args, **options):
        exit_code = run_benchmarks(
            views=options.get("views"),
            save_as_baseline=options["baseline"],
            json_output=options["json"],
        )
        if exit_code != 0:
            raise SystemExit(exit_code)
