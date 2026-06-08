#!/usr/bin/env python3
"""
281.A.10.4 — Internal documentation link checker.

Scans all Markdown files under ``docs/`` and root ``*.md`` for internal
links (``[text](./path.md)`` or ``[text](../path.md#anchor)``) and
reports broken references.

Usage:
  python scripts/check_doc_links.py                    # all links
  python scripts/check_doc_links.py --internal-only    # skip external URLs
  python scripts/check_doc_links.py --check           # exit 1 on broken links
"""
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

# Files to skip (auto-generated, third-party, etc.)
SKIP_FILES = {
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "site", "product-site",
}
SKIP_PATTERNS = ["CHANGELOG.md"]  # Changelog links are release artifacts


def _is_internal(url: str) -> bool:
    """Check if a URL is an internal document reference."""
    if url.startswith("http://") or url.startswith("https://"):
        return False
    if url.startswith("mailto:") or url.startswith("#"):
        return False
    return True


def _resolve_link(source_path: Path, target: str) -> Path | None:
    """Resolve a relative link target against the source file's directory."""
    # Strip anchor
    if "#" in target:
        target = target.split("#")[0]
    if not target:
        return None

    source_dir = source_path.parent
    resolved = (source_dir / target).resolve()

    # Check if it's within the project
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        return None  # Outside project — skip

    return resolved


def check_links(internal_only: bool = False) -> dict:
    """Check all doc links. Returns {status: ..., broken: [...], total: int}."""
    broken = []
    total = 0

    md_files = []
    for pattern in ["docs/**/*.md", "*.md"]:
        md_files.extend(PROJECT_ROOT.glob(pattern))

    for md_file in sorted(set(md_files)):
        rel = str(md_file.relative_to(PROJECT_ROOT))

        # Skip generated files
        if any(p in rel for p in SKIP_PATTERNS):
            continue
        if any(p in str(md_file).split(os.sep) for p in SKIP_FILES):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Find markdown links: [text](url)
        for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', content):
            url = m.group(2).strip()
            total += 1

            if not _is_internal(url):
                continue

            resolved = _resolve_link(md_file, url)
            if resolved is None:
                continue

            if not resolved.exists():
                broken.append({
                    "file": rel,
                    "line": content[:m.start()].count("\n") + 1,
                    "target": url,
                    "resolved": str(resolved.relative_to(PROJECT_ROOT)),
                })

    return {
        "total": total,
        "broken": len(broken),
        "details": broken,
    }


def print_report(results: dict) -> None:
    """Print human-readable link checker report."""
    print(f"Documentation Link Checker (281.A.10.4)\n")
    print(f"  Total links scanned: {results['total']}")
    print(f"  Broken internal links: {results['broken']}")

    if results["broken"] == 0:
        print("  ✅ All internal links resolve correctly.")
        return

    print(f"\n  Broken links:")
    for b in results["details"]:
        print(f"    {b['file']}:{b['line']} — {b['target']}")
        print(f"      → resolves to {b['resolved']} (MISSING)")


def main():
    parser = ArgumentParser(description="Check documentation links")
    parser.add_argument("--internal-only", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 on broken links")
    args = parser.parse_args()

    results = check_links(internal_only=args.internal_only)
    print_report(results)

    if args.check and results["broken"] > 0:
        print(f"\nError: {results['broken']} broken link(s) found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
