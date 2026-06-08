#!/usr/bin/env python3
"""
Capture and compare pg_stat_statements snapshots for assets RLS rollout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import psycopg2


@dataclass
class QueryStat:
    queryid: str
    calls: int
    total_exec_time: float
    mean_exec_time: float
    rows: int
    query: str


def _normalize_query(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def _read_stats(database_url: str, limit: int) -> list[QueryStat]:
    sql = """
        SELECT
            queryid::text AS queryid,
            calls,
            total_exec_time,
            mean_exec_time,
            rows,
            query
        FROM pg_stat_statements
        WHERE lower(query) LIKE '%%assets%%'
        ORDER BY total_exec_time DESC
        LIMIT %s
    """
    with psycopg2.connect(database_url) as conn, conn.cursor() as cursor:
        cursor.execute(sql, [limit])
        rows = cursor.fetchall()

    return [
        QueryStat(
            queryid=str(row[0]),
            calls=int(row[1]),
            total_exec_time=float(row[2]),
            mean_exec_time=float(row[3]),
            rows=int(row[4]),
            query=_normalize_query(str(row[5])),
        )
        for row in rows
    ]


def snapshot(database_url: str, output_path: Path, limit: int) -> int:
    stats = _read_stats(database_url, limit=limit)
    payload = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_url_hint": (
            database_url.split("@")[-1] if "@" in database_url else "local"
        ),
        "top_n": limit,
        "query_count": len(stats),
        "queries": [asdict(item) for item in stats],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote snapshot: {output_path} ({len(stats)} queries)")
    return 0


def _load_snapshot(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def compare(baseline_path: Path, current_path: Path, threshold_pct: float) -> int:
    baseline = _load_snapshot(baseline_path)
    current = _load_snapshot(current_path)

    baseline_by_id = {
        str(item["queryid"]): item for item in baseline.get("queries", [])
    }
    regressions: list[dict[str, Any]] = []

    for row in current.get("queries", []):
        queryid = str(row["queryid"])
        previous = baseline_by_id.get(queryid)
        if not previous:
            continue
        prev_mean = float(previous["mean_exec_time"])
        curr_mean = float(row["mean_exec_time"])
        if prev_mean <= 0:
            continue
        delta_pct = ((curr_mean - prev_mean) / prev_mean) * 100.0
        if delta_pct > threshold_pct:
            regressions.append(
                {
                    "queryid": queryid,
                    "delta_pct": round(delta_pct, 2),
                    "previous_mean_ms": round(prev_mean, 3),
                    "current_mean_ms": round(curr_mean, 3),
                    "query": row["query"],
                }
            )

    print(
        json.dumps(
            {
                "baseline": str(baseline_path),
                "current": str(current_path),
                "threshold_pct": threshold_pct,
                "regression_count": len(regressions),
                "regressions": regressions,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if regressions else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="assets RLS pg_stat_statements helper"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snapshot", help="capture top assets query stats")
    snap.add_argument(
        "--database-url",
        default=(
            os.getenv("DATABASE_URL_ADMIN")
            or os.getenv("DATABASE_URL")
        ),
    )
    snap.add_argument("--output", required=True)
    snap.add_argument("--limit", type=int, default=20)

    cmp_parser = sub.add_parser("compare", help="compare two snapshots")
    cmp_parser.add_argument("--baseline", required=True)
    cmp_parser.add_argument("--current", required=True)
    cmp_parser.add_argument("--threshold-pct", type=float, default=20.0)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "snapshot":
        if not args.database_url:
            parser.error(
                "snapshot requires --database-url or "
                "DATABASE_URL_ADMIN/DATABASE_URL env var"
            )
        return snapshot(args.database_url, Path(args.output), args.limit)

    if args.cmd == "compare":
        return compare(Path(args.baseline), Path(args.current), args.threshold_pct)

    parser.error(f"unknown command: {args.cmd}")
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    sys.exit(main())
