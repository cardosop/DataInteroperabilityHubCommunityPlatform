#!/usr/bin/env python3
"""
URL Pattern Validation Script for CI/CD

Validates Django URL patterns against API naming standards.
Can be used as a standalone script or integrated into CI/CD pipelines.

Usage:
    python scripts/validate_url_patterns.py [--strict] [--check-files FILES...]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

    import django

    django.setup()

    from hub.apps.api.utils.url_pattern_validator import (
        URLPatternValidationResult,
        URLPatternValidator,
    )
except ImportError as e:
    print(f"Error: Could not import Django modules: {e}", file=sys.stderr)
    print(
        "Make sure Django is properly configured and dependencies are installed.", file=sys.stderr
    )
    sys.exit(1)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Validate Django URL patterns against API naming standards"
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument(
        "--check-files",
        nargs="*",
        help="Specific files to check (if not provided, checks all URL patterns)",
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Always exit with code 0 (useful for CI that should not fail on warnings)",
    )

    args = parser.parse_args()

    # Initialize validator
    validator = URLPatternValidator()

    # Run validation
    result = validator.validate_all(strict=args.strict)

    # Print formatted results
    output = validator.format_errors(result)
    print(output)

    # Exit with appropriate code
    if result.passed:
        print("\n✅ URL pattern validation passed!")
        return 0
    elif args.exit_zero:
        print("\n⚠️  URL pattern validation found issues (exiting with code 0)")
        return 0
    else:
        print("\n❌ URL pattern validation failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
