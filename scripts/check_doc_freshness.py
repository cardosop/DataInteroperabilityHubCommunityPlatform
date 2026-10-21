#!/usr/bin/env python3
"""Check doc-vs-code freshness (Phase 217.5.9).

Compares modification times of auto-generated reference pages under
docs/mvpdocs/{cli-reference,sdk-reference,api-reference}/ to their
source files.  Fails CI with "regenerate docs" if any source file is
newer than its corresponding generated page.

Sources:
  - CLI reference: cli/datahub_cli/commands/*.py
  - SDK reference: sdk/python/datahub_interoperability/*.py
  - API reference: hub/apps/*/urls.py (proxy for API changes)

Phase 217.5.9
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mtime(p: Path) -> float:
    """Return mtime or 0 if file does not exist."""
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def _check_cli_freshness() -> list[str]:
    """Check CLI reference pages vs source commands."""
    errors: list[str] = []
    src_dir = REPO_ROOT / "cli" / "datahub_cli" / "commands"
    doc_dir = REPO_ROOT / "docs" / "mvpdocs" / "cli-reference"
    if not src_dir.exists() or not doc_dir.exists():
        return errors
    for src in sorted(src_dir.glob("*.py")):
        if src.name.startswith("_"):
            continue
        doc = doc_dir / f"{src.stem}.md"
        if doc.exists() and _mtime(src) > _mtime(doc):
            errors.append(
                f"cli-reference/{doc.name} is stale (source: {src.relative_to(REPO_ROOT)})"
            )
    return errors


def _check_sdk_freshness() -> list[str]:
    """Check SDK reference pages vs source modules."""
    errors: list[str] = []
    src_dir = REPO_ROOT / "sdk" / "python" / "datahub_interoperability"
    doc_dir = REPO_ROOT / "docs" / "mvpdocs" / "sdk-reference" / "python"
    if not src_dir.exists() or not doc_dir.exists():
        return errors
    for src in sorted(src_dir.glob("*.py")):
        if src.name.startswith("_"):
            continue
        stem = src.stem.replace("_", "-")
        doc = doc_dir / f"{stem}-api.md"
        if not doc.exists():
            doc = doc_dir / f"{stem}.md"
        if doc.exists() and _mtime(src) > _mtime(doc):
            errors.append(
                f"sdk-reference/python/{doc.name} is stale (source: {src.relative_to(REPO_ROOT)})"
            )
    return errors


def _check_api_freshness() -> list[str]:
    """Check API reference pages vs source url modules."""
    errors: list[str] = []
    hub_apps = REPO_ROOT / "hub" / "apps"
    doc_dir = REPO_ROOT / "docs" / "mvpdocs" / "api-reference"
    if not hub_apps.exists() or not doc_dir.exists():
        return errors
    for urls_file in sorted(hub_apps.rglob("urls.py")):
        app_name = urls_file.parent.name
        if app_name in ("api", "tests", "__pycache__"):
            continue
        doc = doc_dir / f"{app_name}.md"
        if doc.exists() and _mtime(urls_file) > _mtime(doc):
            errors.append(
                f"api-reference/{doc.name} is stale (source: {urls_file.relative_to(REPO_ROOT)})"
            )
    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(_check_cli_freshness())
    all_errors.extend(_check_sdk_freshness())
    all_errors.extend(_check_api_freshness())

    if all_errors:
        print(f"FAIL: {len(all_errors)} stale doc page(s). Regenerate with the appropriate script.")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("PASS: all generated doc pages are fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
