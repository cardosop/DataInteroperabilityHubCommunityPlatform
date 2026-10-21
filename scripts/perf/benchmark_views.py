#!/usr/bin/env python3
"""
305.4 — View benchmark script (standalone wrapper).

Delegates to the Django management command at
``hub.apps.observability.management.commands.benchmark_views``.

Usage:
    python scripts/perf/benchmark_views.py
    python scripts/perf/benchmark_views.py --baseline
    python scripts/perf/benchmark_views.py --json
    python scripts/perf/benchmark_views.py --view asset_list

Also available as: ``python manage.py benchmark_views``
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django

django.setup()

from hub.apps.observability.management.commands.benchmark_views import (
    run_benchmarks,
)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View benchmark using EXPLAIN ANALYZE")
    parser.add_argument("--view", action="append", dest="views")
    parser.add_argument("--baseline", action="store_true", default=False)
    parser.add_argument("--json", action="store_true", default=False)
    args = parser.parse_args()

    raise SystemExit(
        run_benchmarks(
            views=args.views,
            save_as_baseline=args.baseline,
            json_output=args.json,
        )
    )
