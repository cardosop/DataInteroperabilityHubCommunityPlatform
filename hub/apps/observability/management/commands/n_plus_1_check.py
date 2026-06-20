"""
305.1 — N+1 query detection smoke test (Django management command).

Usage:
    python manage.py n_plus_1_check
    python manage.py n_plus_1_check --view asset_list
    python manage.py n_plus_1_check --threshold-multiplier 1.5
    python manage.py n_plus_1_check --json
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections
from django.test.client import Client
from django.test.utils import CaptureQueriesContext


@dataclass(frozen=True)
class ViewThreshold:
    url: str
    name: str
    max_queries: int
    method: str = "GET"
    data: dict | None = None


_DEFAULT_THRESHOLDS: list[ViewThreshold] = [
    ViewThreshold("/api/v1/assets/", "asset_list", max_queries=8),
    ViewThreshold("/api/v1/contracts/", "contract_list", max_queries=8),
    ViewThreshold("/api/v1/marketplace/listings/", "marketplace_list", max_queries=10),
    ViewThreshold("/api/v1/search/?q=test", "search", max_queries=6),
    ViewThreshold(
        "/api/v1/semantic/sparql?query=SELECT%20*%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D%20LIMIT%201",
        "sparql",
        max_queries=5,
    ),
]


def _get_test_client() -> Client:
    from django.contrib.auth import get_user_model

    client = Client()
    test_user = get_user_model().objects.filter(status="ACTIVE").first()
    if test_user:
        client.force_login(test_user)
    return client


def _check_view(
    client: Client,
    threshold: ViewThreshold,
    multiplier: float = 1.0,
) -> tuple[bool, int, str]:
    connection = connections[DEFAULT_DB_ALIAS]
    effective_max = int(threshold.max_queries * multiplier)

    try:
        with CaptureQueriesContext(connection) as ctx:
            if threshold.method == "GET":
                response = client.get(threshold.url)
            elif threshold.method == "POST":
                response = client.post(
                    threshold.url,
                    data=threshold.data,
                    content_type="application/json",
                )
            else:
                return False, 0, f"Unsupported method: {threshold.method}"

        query_count = len(ctx.captured_queries)
        passed = query_count <= effective_max
        detail = (
            f"{'PASS' if passed else 'FAIL'}: {threshold.name} — "
            f"{query_count} queries (threshold: {effective_max}, "
            f"status: {response.status_code})"
        )
        return passed, query_count, detail
    except Exception as exc:
        return False, 0, f"ERROR: {threshold.name} — {exc}"


def run_n_plus_1_checks(
    views: list[str] | None = None,
    threshold_multiplier: float = 1.0,
    json_output: bool = False,
) -> int:
    client = _get_test_client()
    targets = _DEFAULT_THRESHOLDS
    if views:
        targets = [t for t in _DEFAULT_THRESHOLDS if t.name in views]

    results: list[dict] = []
    failures = 0

    for threshold in targets:
        passed, count, detail = _check_view(
            client,
            threshold,
            threshold_multiplier,
        )
        if not passed:
            failures += 1
        results.append(
            {
                "view": threshold.name,
                "url": threshold.url,
                "queries": count,
                "threshold": int(threshold.max_queries * threshold_multiplier),
                "passed": passed,
                "detail": detail,
            }
        )

    if json_output:
        print(
            json.dumps(
                {
                    "total": len(results),
                    "passed": len(results) - failures,
                    "failed": failures,
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        for r in results:
            print(f"  {'✓' if r['passed'] else '✗'} {r['detail']}")
        if failures:
            print(f"\n{failures}/{len(results)} view(s) exceeded query thresholds.")
        else:
            print(f"\nAll {len(results)} views within query limits.")

    return 1 if failures else 0


class Command(BaseCommand):
    help = "305.1 — N+1 query detection smoke test for key views."

    def add_arguments(self, parser):
        parser.add_argument(
            "--view",
            action="append",
            dest="views",
            help="Test a specific view by name (repeatable).",
        )
        parser.add_argument(
            "--threshold-multiplier",
            type=float,
            default=1.0,
            help="Multiply all thresholds (default 1.0).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Output results as JSON.",
        )

    def handle(self, *args, **options):
        exit_code = run_n_plus_1_checks(
            views=options.get("views"),
            threshold_multiplier=options["threshold_multiplier"],
            json_output=options["json"],
        )
        if exit_code != 0:
            raise SystemExit(exit_code)
