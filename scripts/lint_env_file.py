#!/usr/bin/env python3
"""
Phase 276.B.003 — Pre-commit guard for .env file corruption.

Validates that .env files are RFC-2335-ish KEY=value format,
never JSON. Rejects the commit on a parse error.

Usage:
    python scripts/lint_env_file.py .env .env.test.example
"""
import sys
import os


def lint_env_file(path: str) -> list[str]:
    """Return a list of parse errors for the given .env file."""
    errors = []
    if not os.path.isfile(path):
        return errors

    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # JSON detection: if the line starts with { or [, it's JSON, not dotenv.
            if stripped[0] in ("{", "[", '"'):
                errors.append(
                    f"{path}:{lineno}: JSON syntax detected — "
                    f".env files must use KEY=value format, not JSON. "
                    f"VS Code settings belong in .vscode/settings.json, not .env."
                )
            # Missing = sign (but allow export FOO=bar)
            elif "=" not in stripped and not stripped.startswith("export "):
                # Could be a comment without #, warn softly
                pass

    return errors


def main():
    exit_code = 0
    for path in sys.argv[1:]:
        errors = lint_env_file(path)
        for err in errors:
            print(err, file=sys.stderr)
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
