#!/usr/bin/env python3
"""
Contract test: compare current OpenAPI schema to baseline and fail on breaking changes.

Usage:
  python scripts/contract_test_openapi.py              # Compare current vs baseline; exit 1 if breaking
  python scripts/contract_test_openapi.py --update-baseline   # Overwrite baseline with current schema

Breaking: removed endpoints, removed/renamed required fields, type changes.
Allowed: new endpoints, new optional fields.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BASELINE_PATH = PROJECT_ROOT / "docs" / "api" / "openapi-baseline.json"

# Django setup
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import django
django.setup()


def _generate_current_schema() -> dict:
    """Generate current OpenAPI schema (same pipeline as runtime and regenerate-openapi-spec)."""
    from django.test import RequestFactory

    from drf_spectacular.generators import SchemaGenerator
    from hub.apps.api.openapi_enhancement import OpenAPISpecEnhancer
    from hub.apps.api.openapi_validation import OpenAPISpecValidator

    factory = RequestFactory()
    request = factory.get("/api/v1/")
    generator = SchemaGenerator(urlconf="hub.urls")
    schema = generator.get_schema(request=request, public=True)
    schema = OpenAPISpecValidator.enhance_spec(schema)
    schema = OpenAPISpecEnhancer.enhance_spec(schema)
    return schema


def _resolve_ref(spec: dict, ref: str) -> dict | None:
    """Resolve $ref to a schema object. ref is e.g. '#/components/schemas/Foo'."""
    if not ref.startswith("#/"):
        return None
    parts = ref.split("/")[1:]
    obj = spec
    for p in parts:
        obj = obj.get(p) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj if isinstance(obj, dict) else None


def _get_schema_for_media(spec: dict, content: dict) -> dict | None:
    """Get schema from content (application/json or first key). Resolve one level of $ref."""
    if not content:
        return None
    # Prefer application/json
    media = content.get("application/json") or content.get("application/yaml") or next(iter(content.values()), None)
    if not media or not isinstance(media, dict):
        return None
    schema = media.get("schema")
    if not schema or not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if ref:
        resolved = _resolve_ref(spec, ref)
        return resolved if isinstance(resolved, dict) else schema
    return schema


def _get_required_and_properties(spec: dict, schema: dict | None) -> tuple[list[str], dict]:
    """Return (required list, properties dict) for a schema, resolving one $ref level."""
    if not schema:
        return [], {}
    ref = schema.get("$ref")
    if ref:
        schema = _resolve_ref(spec, ref) or schema
    required = list(schema.get("required") or [])
    props = dict(schema.get("properties") or {})
    return required, props


def _schema_type(schema: dict) -> str | None:
    """Return type string for a schema (type, or first allOf item type)."""
    if not schema:
        return None
    t = schema.get("type")
    if t:
        return t
    all_of = schema.get("allOf")
    if all_of and isinstance(all_of, list) and len(all_of) > 0:
        first = all_of[0]
        if isinstance(first, dict):
            return first.get("type")
    return None


def _collect_operation_schemas(spec: dict, path_item: dict, method: str) -> list[tuple[str, dict]]:
    """Collect request and main response schemas for an operation. Returns list of (role, schema) with role 'request' or 'response'."""
    op = path_item.get(method.lower())
    if not op or not isinstance(op, dict):
        return []
    out: list[tuple[str, dict]] = []
    # Request body
    req_body = op.get("requestBody")
    if isinstance(req_body, dict):
        schema = _get_schema_for_media(spec, req_body.get("content") or {})
        if schema:
            out.append(("request", schema))
    # Response 200/201
    responses = op.get("responses") or {}
    for code in ("200", "201"):
        resp = responses.get(code)
        if isinstance(resp, dict):
            schema = _get_schema_for_media(spec, resp.get("content") or {})
            if schema:
                out.append(("response", schema))
                break  # one response schema per operation
    return out


def _normalize_path(path: str) -> str:
    """Normalize path for comparison (e.g. consistent trailing slash)."""
    if not path:
        return path
    return path.rstrip("/") or "/"


def _paths_methods(spec: dict) -> list[tuple[str, str]]:
    """List (path, method) for all operations in spec."""
    paths = spec.get("paths") or {}
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    out = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        p = _normalize_path(path)
        for method, op in path_item.items():
            if method.lower() in http_methods and isinstance(op, dict):
                out.append((p, method.lower()))
    return out


def _breaking_removed_endpoints(baseline: dict, current: dict) -> list[str]:
    """Return list of (path, method) that exist in baseline but not in current."""
    baseline_pm = set(_paths_methods(baseline))
    current_pm = set(_paths_methods(current))
    removed = sorted(baseline_pm - current_pm)
    return [f"{p} {m.upper()}" for p, m in removed]


def _breaking_required_and_types(
    baseline: dict, current: dict
) -> list[str]:
    """Check required fields and types for operations present in both. Returns list of violation messages."""
    violations = []
    b_paths = baseline.get("paths") or {}
    c_paths = current.get("paths") or {}
    for path, b_path_item in b_paths.items():
        if not isinstance(b_path_item, dict):
            continue
        p = _normalize_path(path)
        c_path_item = c_paths.get(path) or c_paths.get(path + "/") or c_paths.get(p) or c_paths.get(p + "/")
        if not c_path_item or not isinstance(c_path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            b_op = (b_path_item.get(method) or {}) if isinstance(b_path_item.get(method), dict) else None
            c_op = (c_path_item.get(method) or {}) if isinstance(c_path_item.get(method), dict) else None
            if not b_op:
                continue
            if not c_op:
                continue  # already reported as removed endpoint
            for role, b_schema in _collect_operation_schemas(baseline, b_path_item, method):
                if role == "request":
                    c_content = (c_op.get("requestBody") or {}).get("content") or {}
                else:
                    r = (c_op.get("responses") or {}).get("200") or (c_op.get("responses") or {}).get("201") or {}
                    c_content = (r.get("content") or {}) if isinstance(r, dict) else {}
                c_schema = _get_schema_for_media(current, c_content)
                b_req, b_props = _get_required_and_properties(baseline, b_schema)
                c_req, c_props = _get_required_and_properties(current, c_schema)
                for r in b_req:
                    if r not in c_req and r not in c_props:
                        violations.append(f"{p} {method.upper()} {role}: required field removed or renamed: {r!r}")
                    elif r in c_props and r in b_props:
                        b_type = _schema_type(b_props[r]) if isinstance(b_props.get(r), dict) else None
                        c_type = _schema_type(c_props[r]) if isinstance(c_props.get(r), dict) else None
                        if b_type and c_type and b_type != c_type:
                            violations.append(f"{p} {method.upper()} {role}: type change for {r!r}: {b_type!r} -> {c_type!r}")
    return violations


def _validate_baseline_structure(baseline: dict) -> list[str]:
    """Validate baseline has required OpenAPI structure. Return list of errors (empty if valid)."""
    errs = []
    if not isinstance(baseline.get("openapi"), str):
        errs.append("Baseline must have 'openapi' (string).")
    if "paths" not in baseline:
        errs.append("Baseline must have 'paths'.")
    elif not isinstance(baseline["paths"], dict):
        errs.append("Baseline 'paths' must be an object.")
    return errs


def run_contract_test(baseline_path: Path) -> tuple[bool, list[str], dict | None]:
    """
    Generate current schema, load baseline, compare.
    Return (success, list of violation messages, current_schema for optional artifact).
    """
    try:
        current = _generate_current_schema()
    except Exception as e:
        return False, [f"Failed to generate current schema: {e}"], None

    resolved_path = baseline_path.resolve() if not baseline_path.is_absolute() else baseline_path
    if not resolved_path.is_file():
        return False, [f"Baseline not found: {resolved_path}. Run with --update-baseline to create it."], None

    try:
        with open(resolved_path, "r") as f:
            baseline = json.load(f)
    except Exception as e:
        return False, [f"Failed to load baseline: {e}"], None

    structure_errs = _validate_baseline_structure(baseline)
    if structure_errs:
        return False, [f"Invalid baseline: {e}" for e in structure_errs], None

    violations = []

    # 1. Removed endpoints
    removed = _breaking_removed_endpoints(baseline, current)
    if removed:
        violations.extend([f"Removed endpoint: {x}" for x in removed])

    # 2. Required fields and type changes (for operations that still exist)
    req_type_violations = _breaking_required_and_types(baseline, current)
    violations.extend(req_type_violations)

    return len(violations) == 0, violations, current


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Contract test: compare current OpenAPI schema to baseline; fail on breaking changes."
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite docs/api/openapi-baseline.json with current schema (use when intentionally changing API).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help=f"Path to baseline JSON (default: {BASELINE_PATH}).",
    )
    parser.add_argument(
        "--write-current",
        type=Path,
        default=None,
        metavar="PATH",
        help="On failure, write current schema to PATH (e.g. for CI artifact).",
    )
    args = parser.parse_args()

    if args.update_baseline:
        baseline_path = args.baseline.resolve()
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            schema = _generate_current_schema()
            with open(baseline_path, "w") as f:
                json.dump(schema, f, indent=2, sort_keys=False)
            print(f"Updated baseline: {baseline_path}")
            return 0
        except Exception as e:
            print(f"Error generating or writing baseline: {e}", file=sys.stderr)
            return 1

    ok, violations, current_schema = run_contract_test(args.baseline)
    if ok:
        print("Contract test passed: no breaking changes.")
        return 0
    if args.write_current is not None and current_schema is not None:
        try:
            args.write_current.parent.mkdir(parents=True, exist_ok=True)
            with open(args.write_current, "w") as f:
                json.dump(current_schema, f, indent=2, sort_keys=False)
            print(f"Current schema written to {args.write_current} for debugging.", file=sys.stderr)
        except Exception as e:
            print(f"Could not write current schema: {e}", file=sys.stderr)
    print("Contract test failed: breaking changes detected.", file=sys.stderr)
    for v in violations:
        print(f"  - {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
