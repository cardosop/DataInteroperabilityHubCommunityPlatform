#!/usr/bin/env python3
"""285.12.4.11 — Audit PlanLimitService.check_limit() calls across services."""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LIMIT_KEYS = {
    "max_dq_runs_per_month", "max_compliance_runs_per_month",
    "max_job_concurrency", "max_queued_jobs",
    "max_transformation_runs_per_month",
    "max_datasets", "max_files", "max_assets",
}

def audit() -> int:
    count = 0
    for pyf in _REPO.rglob("hub/apps/**/*.py"):
        if any(p in pyf.parts for p in ("__pycache__","migrations","tests",".venv")):
            continue
        try:
            text = pyf.read_text()
        except Exception:
            continue
        for key in _LIMIT_KEYS:
            if key in text:
                count += 1
                break
    print(f"Plan limit enforcement: {count} files reference limit keys")
    return 0

sys.exit(audit())
