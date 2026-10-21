#!/usr/bin/env python3
"""
Phase 277.B.055 — Backfill maintenance metadata on undated runbooks.

Adds a ``## Maintenance`` footer with ``Owner`` and ``Last reviewed``
fields to every runbook under ``docs/runbooks/`` that doesn't already
have them.  Existing metadata is preserved.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

RUNBOOKS_DIR = Path(__file__).resolve().parent.parent / "docs" / "runbooks"

OWNER_MAP = {
    "data-quality": "Data Engineering",
    "marketplace": "Marketplace Team",
    "kms": "Platform Engineering",
    "webhook": "Platform Engineering",
    "audit": "Platform Engineering",
    "backup": "Platform Engineering",
    "restore": "Platform Engineering",
    "backup-restore": "Platform Engineering",
    "credential": "Platform Engineering",
    "semantic": "Semantic Team",
    "fuseki": "Semantic Team",
    "lineage": "Data Engineering",
    "compliance": "Compliance Team",
    "gdpr": "Compliance Team",
    "dsar": "Compliance Team",
    "erasure": "Compliance Team",
    "governance": "Governance Team",
    "scheduled": "Data Engineering",
    "ingestion": "Data Engineering",
    "export": "Data Engineering",
    "stripe": "Billing Team",
    "billing": "Billing Team",
    "connect": "Billing Team",
    "migration": "Platform Engineering",
    "deploy": "Platform Engineering",
    "staging": "Platform Engineering",
    "rollback": "Platform Engineering",
    "tenant": "Platform Engineering",
    "admin": "Platform Engineering",
    "destroy": "Platform Engineering",
    "openspec": "Platform Engineering",
    "idempotency": "Platform Engineering",
    "circuit": "Platform Engineering",
    "security": "Security Team",
    "auth": "Security Team",
    "bug": "Security Team",
    "vulnerability": "Security Team",
    "cve": "Security Team",
    "container": "Platform Engineering",
    "docker": "Platform Engineering",
    "kubernetes": "Platform Engineering",
    "helm": "Platform Engineering",
    "terraform": "Platform Engineering",
    "aws": "Platform Engineering",
    "s3": "Platform Engineering",
    "redis": "Platform Engineering",
    "postgres": "Platform Engineering",
    "prometheus": "Platform Engineering",
    "grafana": "Platform Engineering",
    "alert": "Platform Engineering",
    "monitor": "Platform Engineering",
    "log": "Platform Engineering",
    "trace": "Platform Engineering",
    "otel": "Platform Engineering",
    "frontend": "Frontend Team",
    "e2e": "Frontend Team",
    "a11y": "Frontend Team",
    "playwright": "Frontend Team",
    "vitest": "Frontend Team",
    "storybook": "Frontend Team",
    "sdk": "Developer Experience",
    "cli": "Developer Experience",
    "api": "Developer Experience",
    "docs": "Developer Experience",
    "changelog": "Developer Experience",
    "release": "Developer Experience",
    "seo": "Frontend Team",
    "virus": "Security Team",
    "scan": "Security Team",
    "malware": "Security Team",
}

DEFAULT_OWNER = "Platform Engineering"
TODAY = date.today().isoformat()

FOOTER = """
## Maintenance

- **Owner**: {owner}
- **Last reviewed**: {date}
- **Next review**: {next_date}
"""


def _guess_owner(filepath: Path) -> str:
    stem = filepath.stem.lower()
    for keyword, team in OWNER_MAP.items():
        if keyword in stem:
            return team
    # Check parent directory name
    return DEFAULT_OWNER


def _has_metadata(content: str) -> bool:
    return bool(re.search(r"(?i)^(last.reviewed|maintainer|owner)\s*:", content, re.MULTILINE))


def _next_review_date() -> str:
    """Quarterly review: 3 months from today."""
    from datetime import timedelta

    return (date.today() + timedelta(days=90)).isoformat()


def main() -> int:
    updated = 0
    skipped = 0

    for md_file in sorted(RUNBOOKS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        if _has_metadata(content):
            skipped += 1
            continue

        owner = _guess_owner(md_file)
        next_date = _next_review_date()
        footer = FOOTER.format(owner=owner, date=TODAY, next_date=next_date)

        # Append footer before any existing "## References" or at end
        if "## References" in content:
            content = content.replace("## References", footer + "\n## References")
        else:
            content = content.rstrip() + "\n" + footer

        md_file.write_text(content, encoding="utf-8")
        updated += 1
        print(f"  Updated: {md_file.name} → owner={owner}")

    print(f"\nDone. Updated: {updated}, Skipped (already have metadata): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
