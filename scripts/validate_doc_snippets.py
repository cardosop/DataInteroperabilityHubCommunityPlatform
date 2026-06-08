#!/usr/bin/env python3
"""
281.A.10.4 — Documentation code snippet validator.

Extracts code blocks from Markdown files under ``docs/`` and validates:
  - Python snippets: compile with ``ast.parse()``
  - Shell snippets: basic syntax check (balanced quotes, no dangerous commands)
  - JSON snippets: parse with ``json.loads()``

Usage:
  python scripts/validate_doc_snippets.py                    # all languages
  python scripts/validate_doc_snippets.py --language python  # Python only
  python scripts/validate_doc_snippets.py --check            # exit 1 on failures
"""
import ast
import json
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

FENCE_PATTERN = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)


def extract_snippets(content: str, language: str | None = None) -> list[dict]:
    """Extract code snippets of a given language from Markdown content."""
    snippets = []
    for m in FENCE_PATTERN.finditer(content):
        lang = (m.group(1) or "").lower()
        code = m.group(2).strip()
        if not code:
            continue
        if language and lang != language:
            continue
        snippets.append({
            "language": lang,
            "code": code,
            "line": content[:m.start()].count("\n") + 1,
        })
    return snippets


def validate_python(code: str) -> tuple[bool, str]:
    """Validate Python snippet compiles."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def validate_shell(code: str) -> tuple[bool, str]:
    """Basic shell snippet validation."""
    # Check for obviously dangerous patterns
    dangerous = ["rm -rf /", "dd if=/dev/zero", "mkfs.", ":(){ :|:& };:"]
    for d in dangerous:
        if d in code:
            return False, f"Potentially dangerous command: {d}"

    # Check balanced quotes
    for quote in ["'", '"']:
        if code.count(quote) % 2 != 0:
            return False, f"Unbalanced {quote} quotes"

    return True, ""


def validate_json(code: str) -> tuple[bool, str]:
    """Validate JSON snippet parses."""
    try:
        json.loads(code)
        return True, ""
    except json.JSONDecodeError as e:
        return False, str(e)


VALIDATORS = {
    "python": validate_python,
    "py": validate_python,
    "bash": validate_shell,
    "sh": validate_shell,
    "shell": validate_shell,
    "json": validate_json,
}


def validate_all(language: str | None = None) -> dict:
    """Validate all doc snippets. Returns structured results."""
    results = {"total": 0, "failed": 0, "details": []}

    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        rel = str(md_file.relative_to(PROJECT_ROOT))
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        snippets = extract_snippets(content, language)
        for snip in snippets:
            results["total"] += 1
            lang = snip["language"]
            validator = VALIDATORS.get(lang)
            if validator is None:
                continue  # Skip unsupported languages

            ok, error = validator(snip["code"])
            if not ok:
                results["failed"] += 1
                results["details"].append({
                    "file": rel,
                    "line": snip["line"],
                    "language": lang,
                    "error": error,
                    "preview": snip["code"][:100],
                })

    return results


def print_report(results: dict) -> None:
    """Print human-readable snippet validation report."""
    print(f"Documentation Snippet Validator (281.A.10.4)\n")
    print(f"  Total snippets: {results['total']}")
    print(f"  Failed: {results['failed']}")

    if results["failed"] == 0:
        print("  ✅ All code snippets valid.")
        return

    print(f"\n  Failed snippets:")
    for d in results["details"]:
        print(f"    {d['file']}:{d['line']} [{d['language']}]")
        print(f"      Error: {d['error']}")
        print(f"      Code:  {d['preview']}")


def main():
    parser = ArgumentParser(description="Validate documentation code snippets")
    parser.add_argument("--language", default=None, help="Language to validate (python, bash, json)")
    parser.add_argument("--check-syntax-only", action="store_true", help="Shell-only: syntax check")
    parser.add_argument("--check", action="store_true", help="Exit 1 on failures")
    args = parser.parse_args()

    results = validate_all(args.language)
    print_report(results)

    if args.check and results["failed"] > 0:
        print(f"\nError: {results['failed']} snippet(s) failed validation.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
