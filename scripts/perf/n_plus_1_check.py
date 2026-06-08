#!/usr/bin/env python3
"""
305.1 — N+1 query detection smoke test (standalone wrapper).

Delegates to the Django management command at
``hub.apps.observability.management.commands.n_plus_1_check``.

Usage:
    python scripts/perf/n_plus_1_check.py
    python scripts/perf/n_plus_1_check.py --view asset_list
    python scripts/perf/n_plus_1_check.py --threshold-multiplier 1.5
    python scripts/perf/n_plus_1_check.py --json

Also available as: ``python manage.py n_plus_1_check``
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django
django.setup()

from hub.apps.observability.management.commands.n_plus_1_check import (
    run_n_plus_1_checks,
)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="N+1 query detection smoke test")
    parser.add_argument("--view", action="append", dest="views")
    parser.add_argument("--threshold-multiplier", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", default=False)
    args = parser.parse_args()

    raise SystemExit(run_n_plus_1_checks(
        views=args.views,
        threshold_multiplier=args.threshold_multiplier,
        json_output=args.json,
    ))
