#!/usr/bin/env python
"""
Standalone verification that rollback scripts exist and are readable (5.1.3).
No Django or database required. Use when full Django test suite cannot run
(e.g. Postgres not yet ready).
"""

import os
import sys

# Resolve project root: script lives in <project_root>/scripts/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

REQUIRED_SCRIPTS = [
    "rollback_workflow_validation_global.sh",
    "rollback_workflow_validation_workflow.sh",
    "rollback_workflow_validation_gradual.sh",
    "verify_workflow_validation_rollback.sh",
]


def main():
    errors = []
    for name in REQUIRED_SCRIPTS:
        path = os.path.join(SCRIPTS_DIR, name)
        if not os.path.exists(path):
            errors.append(f"Rollback script {name} does not exist at {path}")
            continue
        if not os.access(path, os.R_OK):
            errors.append(f"Rollback script {name} is not readable: {path}")
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("All rollback scripts exist and are readable.")
    sys.exit(0)


if __name__ == "__main__":
    main()
