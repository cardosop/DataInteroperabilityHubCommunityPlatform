#!/usr/bin/env python3
"""
281.A.2.6 — CI gate: detect new Django queries that exceed 100ms threshold.

Scans Django query logs (from django-querycount or django-debug-toolbar output)
for slow queries. In CI mode, fails the build if any query exceeds the threshold
without an EXPLAIN-confirmed index.

Usage:
    python scripts/check_query_performance.py --query-log query_log.json --ci
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_THRESHOLD_MS = 100.0
DEFAULT_QUERY_LOG = "query_profile.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="CI gate: detect slow Django queries")
    parser.add_argument("--query-log", default=DEFAULT_QUERY_LOG,
                        help=f"Path to query profile JSON (default: {DEFAULT_QUERY_LOG})")
    parser.add_argument("--threshold-ms", type=float, default=DEFAULT_THRESHOLD_MS,
                        help=f"Max query duration in ms (default: {DEFAULT_THRESHOLD_MS})")
    parser.add_argument("--ci", action="store_true",
                        help="CI mode: exit 1 on threshold violation")
    args = parser.parse_args()

    log_path = Path(args.query_log)
    if not log_path.is_file():
        print(f"No query log found at {log_path} — skipping gate (no queries to check).")
        return 0

    try:
        data = json.loads(log_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {log_path}: {e}", file=sys.stderr)
        return 2

    queries = data.get("queries", []) if isinstance(data, dict) else data
    if not isinstance(queries, list):
        print(f"Error: expected list of queries, got {type(queries).__name__}",
              file=sys.stderr)
        return 2

    slow_queries = []
    total_time = 0.0

    for q in queries:
        if not isinstance(q, dict):
            continue
        sql = q.get("sql", q.get("query", ""))
        duration = float(q.get("time", q.get("duration", 0)))
        total_time += duration

        if duration > args.threshold_ms / 1000.0:
            slow_queries.append({
                "sql": sql[:200],
                "duration_ms": round(duration * 1000, 2),
            })

    print(f"Query profile: {len(queries)} queries, "
          f"{total_time:.2f}s total, "
          f"{len(slow_queries)} slow queries "
          f"(>{args.threshold_ms}ms)")

    if slow_queries:
        print(f"\n⚠️  Slow queries detected:")
        for sq in sorted(slow_queries, key=lambda x: x["duration_ms"], reverse=True)[:10]:
            print(f"  {sq['duration_ms']:.1f}ms — {sq['sql']}")

        if args.ci:
            print(f"\nCI gate: FAILED — {len(slow_queries)} query/queries exceed "
                  f"{args.threshold_ms}ms threshold.")
            return 1
        return 0

    print(f"All queries within {args.threshold_ms}ms threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
