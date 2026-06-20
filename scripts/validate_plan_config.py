#!/usr/bin/env python3
"""
285.13.14.19 — Standalone validation script wrapper for plan config integrity.

Usage:
    python scripts/validate_plan_config.py          # standard check
    python scripts/validate_plan_config.py --strict  # strict mode

Exit 0 on pass, 1 on any violation. Delegates to the Django management
command ``validate_plan_config`` so it benefits from Django's ORM setup
and the CI workflow can invoke it identically.
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

    import django

    django.setup()

    from io import StringIO

    from django.core.management import call_command

    strict = "--strict" in sys.argv
    out = StringIO()
    err = StringIO()

    try:
        call_command("validate_plan_config", strict=strict, stdout=out, stderr=err)
        sys.stdout.write(out.getvalue())
        sys.exit(0)
    except SystemExit as exc:
        sys.stderr.write(err.getvalue())
        sys.exit(exc.code)
