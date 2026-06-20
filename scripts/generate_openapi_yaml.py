#!/usr/bin/env python3
"""
Generate the canonical OpenAPI YAML baseline at ``docs/api/openapi.yaml``.

Phase 277.B.062 — replaces the ad-hoc ``spectacular --file`` invocations
with a single, deterministic pipeline that always runs through the same
Django settings, enhancers, and validators as production.

Usage:
  python scripts/generate_openapi_yaml.py                    # Generate YAML to docs/api/openapi.yaml
  python scripts/generate_openapi_yaml.py --check            # Exit 1 if the committed YAML differs
  python scripts/generate_openapi_yaml.py --format json      # Generate JSON baseline instead
  python scripts/generate_openapi_yaml.py --format both      # Generate both YAML + JSON baselines

CI integration:
  The ``generate-openapi-yaml`` job in ``.github/workflows/ci.yml`` runs
  this script with ``--check``.  A non-zero exit means the committed YAML
  is stale — the PR author must run this script locally (or via the CI
  artifact) and commit the regenerated file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
YAML_BASELINE_PATH = PROJECT_ROOT / "docs" / "api" / "openapi.yaml"
JSON_BASELINE_PATH = PROJECT_ROOT / "docs" / "api" / "openapi-baseline.json"

sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")


def _setup_django():
    import django

    django.setup()


def _generate_current_schema() -> dict:
    """Generate current OpenAPI schema via the same pipeline as ``contract_test_openapi.py``."""
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory
    from drf_spectacular.generators import SchemaGenerator

    from hub.apps.api.openapi_enhancement import OpenAPISpecEnhancer
    from hub.apps.api.openapi_validation import OpenAPISpecValidator

    factory = RequestFactory()
    request = factory.get("/api/v1/")
    request.user = AnonymousUser()
    request.auth = None

    generator = SchemaGenerator(urlconf="hub.urls")
    schema = generator.get_schema(request=request, public=True)
    schema = OpenAPISpecValidator.enhance_spec(schema)
    schema = OpenAPISpecEnhancer.enhance_spec(schema)
    return schema


def _write_yaml(schema: dict, path: Path) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _write_json(schema: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate canonical OpenAPI baselines from the Django schema."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the committed YAML differs from the generated schema.",
    )
    parser.add_argument(
        "--format",
        choices=("yaml", "json", "both"),
        default="yaml",
        help="Output format (default: yaml).",
    )
    args = parser.parse_args()

    try:
        _setup_django()
    except Exception as exc:
        print(f"ERROR: failed to initialise Django: {exc}", file=sys.stderr)
        print(
            "This script must be run with the Django settings module available "
            "(e.g. inside the api-service container or with a configured venv).",
            file=sys.stderr,
        )
        return 2

    schema = _generate_current_schema()

    if args.check:
        if not YAML_BASELINE_PATH.exists():
            print(
                f"ERROR: {YAML_BASELINE_PATH} does not exist. "
                "Run this script without --check first to generate it.",
                file=sys.stderr,
            )
            return 1

        # Write to a temp file and compare SHA-256
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            _write_yaml(schema, Path(tmp.name))
            tmp_path = Path(tmp.name)

        committed_hash = _sha256(YAML_BASELINE_PATH)
        generated_hash = _sha256(tmp_path)
        tmp_path.unlink()

        if committed_hash != generated_hash:
            print(
                f"ERROR: {YAML_BASELINE_PATH} is out of date.\n"
                f"  committed SHA-256: {committed_hash}\n"
                f"  generated SHA-256: {generated_hash}\n\n"
                "Regenerate with:\n"
                "  python scripts/generate_openapi_yaml.py",
                file=sys.stderr,
            )
            return 1

        print(f"OK: {YAML_BASELINE_PATH} matches generated schema.")
        return 0

    if args.format in ("yaml", "both"):
        _write_yaml(schema, YAML_BASELINE_PATH)
        print(f"Wrote {YAML_BASELINE_PATH} ({_sha256(YAML_BASELINE_PATH)[:16]}...)")

    if args.format in ("json", "both"):
        _write_json(schema, JSON_BASELINE_PATH)
        print(f"Wrote {JSON_BASELINE_PATH} ({_sha256(JSON_BASELINE_PATH)[:16]}...)")

    print("\nDone.  Commit these files if they changed:")
    if args.format in ("yaml", "both"):
        print(f"  git add {YAML_BASELINE_PATH}")
    if args.format in ("json", "both"):
        print(f"  git add {JSON_BASELINE_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
