#!/usr/bin/env python3
"""
Phase 277.B.081 — OpenAPI completeness gate.

Generates the current OpenAPI schema from Django's URL conf and verifies
that every registered API endpoint has a corresponding entry in the
``paths`` section.  Reports undocumented endpoints and exits 1 when
any are found.

Usage:
    python scripts/lint_openapi_completeness.py          # Check against generated schema
    python scripts/lint_openapi_completeness.py --json   # Machine-readable output

CI integration:
    The ``lint-openapi-completeness`` job in ci.yml runs this script.
    Exit 0 = all endpoints documented.  Exit 1 = gaps found.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")


def _setup_django():
    import django

    django.setup()


def _generate_openapi_paths() -> set[str]:
    """Generate the current OpenAPI schema and return the set of documented paths."""
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory
    from drf_spectacular.generators import SchemaGenerator

    factory = RequestFactory()
    request = factory.get("/api/v1/")
    request.user = AnonymousUser()
    request.auth = None

    generator = SchemaGenerator(urlconf="hub.urls")
    schema = generator.get_schema(request=request, public=True)
    return set(schema.get("paths", {}).keys())


def _enumerate_registered_urls() -> set[str]:
    """Walk Django's URL resolver and return the set of registered URL patterns.

    Skips admin URLs, static/media paths, and non-API patterns.
    """
    from django.urls import get_resolver

    patterns: set[str] = set()
    _walk_resolver(get_resolver(), "", patterns)
    return patterns


def _walk_resolver(resolver, prefix: str, acc: set[str]):
    """Recursively walk a URL resolver, collecting path templates."""
    from django.urls.resolvers import URLPattern, URLResolver

    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            new_prefix = f"{prefix}{pattern.pattern.regex.pattern.lstrip('^')}"
            # Clean regex chars
            new_prefix = new_prefix.replace("\\", "")
            _walk_resolver(pattern, new_prefix, acc)
        elif isinstance(pattern, URLPattern):
            # Build the full path
            route = f"{prefix}{pattern.pattern}"
            # Normalize: strip regex syntax, trailing slash
            route = route.replace("^", "").replace("$", "")
            route = route.replace("(?P<", "{").replace(">", "}")
            # Remove regex quantifiers and lookaheads
            import re as _re

            route = _re.sub(r"\[.*?\]", "{param}", route)
            route = _re.sub(r"\{[^}]*\}[+?]", "{param}", route)
            # Only report API paths
            if "/api/" in route or "/auth/" in route:
                # Ensure leading slash
                if not route.startswith("/"):
                    route = "/" + route
                # Strip trailing slash for comparison consistency
                route = route.rstrip("/")
                acc.add(route)


def _classify_endpoint(path: str, documented_paths: set[str]) -> str:
    """Classify an endpoint as documented, undocumented, or parameterized-match."""
    if path in documented_paths:
        return "documented"

    # Try parameterized matching: replace {param} placeholders with wildcards
    # and check if any documented path matches the pattern
    import re

    # Normalize path for regex matching
    pattern = re.escape(path)
    # Replace placeholder patterns with regex
    pattern = pattern.replace(r"\\{param\\}", r"[^/]+")
    pattern = pattern.replace(r"\\{pk\\}", r"[^/]+")
    pattern = pattern.replace(r"\\{id\\}", r"[^/]+")
    pattern = pattern.replace(r"\\{slug\\}", r"[^/]+")
    pattern = pattern.replace(r"\\{uuid\\}", r"[^/]+")
    pattern = pattern.replace(r"\\{version\\}", r"[^/]+")

    try:
        compiled = re.compile(f"^{pattern}$")
        for doc_path in documented_paths:
            if compiled.match(doc_path):
                return "documented"
    except re.error:
        pass

    return "undocumented"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check OpenAPI completeness: every registered URL must have a schema entry."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    try:
        _setup_django()
    except Exception as exc:
        print(f"ERROR: failed to initialise Django: {exc}", file=sys.stderr)
        return 2

    documented = _generate_openapi_paths()
    registered = _enumerate_registered_urls()

    # Normalise documented paths
    documented_normalised = {p.rstrip("/") for p in documented}

    # Classify each registered endpoint
    results: list[dict] = []
    undocumented: list[str] = []

    for path in sorted(registered):
        classification = _classify_endpoint(path, documented_normalised)
        results.append({"path": path, "status": classification})
        if classification == "undocumented":
            # Exclude known non-API paths
            exclude_prefixes = (
                "/admin/",
                "/__debug__/",
                "/static/",
                "/media/",
                "/api/v1/docs/",
                "/api/v1/openapi",
                "/api/v1/redoc/",
            )
            if any(path.startswith(p) for p in exclude_prefixes):
                continue
            # Exclude health/internal paths that don't need docs
            if "/health/" in path or "/internal/" in path:
                continue
            undocumented.append(path)

    if args.json:
        print(
            json.dumps(
                {
                    "total_registered": len(registered),
                    "total_documented": len(documented_normalised),
                    "undocumented_count": len(undocumented),
                    "undocumented": undocumented,
                },
                indent=2,
            )
        )
    else:
        print(f"Registered endpoints: {len(registered)}")
        print(f"OpenAPI documented paths: {len(documented_normalised)}")
        print(f"Undocumented endpoints: {len(undocumented)}")
        if undocumented:
            print("\nUndocumented endpoints:")
            for path in undocumented:
                print(f"  - {path}")

    if undocumented:
        return 1
    print("\nOK: all registered endpoints have OpenAPI documentation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
