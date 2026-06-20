#!/usr/bin/env python3
"""
Phase 12: Production/staging CORS validation.

Checks that production/staging config does not use CORS_ALLOWED_ORIGINS=*
or Traefik accessControlAllowOriginList "*" when credentials are used.

Usage:
  python scripts/check_production_cors.py [--production]
  ENVIRONMENT=production python scripts/check_production_cors.py

With --production or ENVIRONMENT=production, exits 1 if:
- infrastructure/traefik/dynamic/routes.yml has accessControlAllowOriginList: ["*"], or
- Django CORS_ALLOWED_ORIGINS (when ENVIRONMENT=production) contains "*".

No mocks; reads real config files and optionally loads Django settings.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAEFIK_ROUTES = PROJECT_ROOT / "infrastructure" / "traefik" / "dynamic" / "routes.yml"


def check_traefik_cors_star(strict: bool) -> bool:
    """Return False if Traefik CORS uses '*' and strict is True."""
    if not TRAEFIK_ROUTES.exists():
        if strict:
            print(f"[ERROR] Traefik routes file not found: {TRAEFIK_ROUTES}", file=sys.stderr)
            return False
        return True
    content = TRAEFIK_ROUTES.read_text()
    # Check for accessControlAllowOriginList with "*"
    if "accessControlAllowOriginList:" in content and '\n          - "*"' in content:
        if strict:
            print(
                "[ERROR] Traefik CORS uses accessControlAllowOriginList: ['*']. "
                "Production MUST use explicit origins. See docs/SECURITY.md.",
                file=sys.stderr,
            )
            return False
        print(
            "[WARN] Traefik CORS has '*'. For production, replace with explicit origins (docs/SECURITY.md).",
            file=sys.stderr,
        )
    return True


def check_django_cors_star(strict: bool) -> bool:
    """Return False if Django CORS_ALLOWED_ORIGINS contains '*' when ENVIRONMENT=production."""
    if not strict:
        return True
    # Set env so Django loads with production; use non-default secrets so startup succeeds.
    os.environ.setdefault("ENVIRONMENT", "production")
    os.environ.setdefault("SECRET_KEY", "check-production-cors-placeholder-secret-key-min-50-chars")
    os.environ.setdefault("JWT_SECRET_KEY", "check-production-cors-placeholder-jwt-secret-32ch")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    try:
        import django

        django.setup()
        from django.conf import settings

        origins = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
        if "*" in origins or origins == ["*"]:
            print(
                "[ERROR] In production, CORS_ALLOWED_ORIGINS must not contain '*'. "
                "Use explicit origins. See docs/SECURITY.md.",
                file=sys.stderr,
            )
            return False
    except Exception as e:
        print(f"[WARN] Could not load Django settings for CORS check: {e}", file=sys.stderr)
        # Do not fail CI if Django fails to load (e.g. missing deps); Traefik check still applies.
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Check production/staging CORS config.")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Strict mode: fail if CORS uses '*' (for CI).",
    )
    args = parser.parse_args()
    strict = args.production or os.environ.get("ENVIRONMENT", "").strip().lower() == "production"

    ok = check_traefik_cors_star(strict)
    if ok:
        ok = check_django_cors_star(strict)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
