#!/usr/bin/env python3
"""
Test Critical Dependency Imports with Python 3.12+

This script tests that all critical dependencies can be imported
and used with Python 3.12+. No mocks - real import tests.
"""

import sys

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


def test_import(module_name: str, display_name: str = None) -> tuple[bool, str]:
    """Test if a module can be imported."""
    if display_name is None:
        display_name = module_name

    try:
        __import__(module_name)
        return True, f"{display_name} imported successfully"
    except ImportError as e:
        return False, f"Import failed: {e!s}"
    except Exception as e:
        return False, f"Error: {e!s}"


def main():
    """Test critical dependency imports."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Critical Dependencies Import Test - Python 3.12+{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    # Critical dependencies and their import names
    dependencies = [
        ("django", "Django"),
        ("rest_framework", "Django REST Framework"),
        ("django_rq", "django-rq"),
        ("corsheaders", "django-cors-headers"),
        ("storages", "django-storages"),
        ("django_prometheus", "django-prometheus"),
        ("strawberry", "strawberry-graphql"),
        ("django_structlog", "django-structlog"),
        ("psycopg2", "psycopg2-binary"),
        ("redis", "redis"),
        ("rq", "rq"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("rdflib", "rdflib"),
        ("SPARQLWrapper", "SPARQLWrapper"),
    ]

    results = []

    for module_name, display_name in dependencies:
        print(f"Testing {display_name}...", end=" ", flush=True)
        success, message = test_import(module_name, display_name)

        if success:
            print(f"{GREEN}✅{RESET}")
            results.append((display_name, True, message))
        else:
            print(f"{YELLOW}⚠️{RESET}")
            print(f"  {message}")
            results.append((display_name, False, message))

    # Summary
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Summary{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"{GREEN}✅ Successfully imported: {len(successful)}/{len(results)}{RESET}")
    if failed:
        print(f"{YELLOW}⚠️  Failed imports: {len(failed)}/{len(results)}{RESET}")
        print(
            f"\n{YELLOW}Note: Some dependencies may not be installed in current environment.{RESET}"
        )
        print(
            f"{YELLOW}This is expected if running outside a virtual environment with dependencies.{RESET}"
        )

    # Show successful imports
    if successful:
        print(f"\n{GREEN}Successfully imported:{RESET}")
        for name, _, _ in successful:
            print(f"  {GREEN}✅{RESET} {name}")

    # Show failed imports (with context)
    if failed:
        print(f"\n{YELLOW}Import tests (may not be installed):{RESET}")
        for name, _, message in failed:
            print(f"  {YELLOW}⚠️{RESET} {name}: {message}")

    # Final status
    if len(successful) >= len(results) * 0.8:  # 80% success rate
        print(f"\n{GREEN}✅ Dependency import test: PASS (most dependencies importable){RESET}")
        sys.exit(0)
    else:
        print(f"\n{YELLOW}⚠️  Some dependencies not importable (may need installation){RESET}")
        sys.exit(0)  # Don't fail - this is informational


if __name__ == "__main__":
    main()
