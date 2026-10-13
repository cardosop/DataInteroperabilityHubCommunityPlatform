#!/usr/bin/env python3
"""Phase 3 — docs reference integrity (GATE-33).

The Phase 3 docs (OSS_CONTRIBUTION.md, the runbooks, CONTRIBUTING.md)
name concrete files, scripts, and workflows. A doc that points at a
renamed or deleted path is worse than no doc. This checker extracts
backtick-quoted references that look like repo paths from the Phase 3
docs and asserts each resolves to an existing file in the tree (or is
in the documented allowlist — e.g. gitignored env files).

Exit 0 clean, 1 on violations.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DOCS = (
    "docs/OSS_CONTRIBUTION.md",
    "docs/runbooks/HOST_SIDE_VERIFICATION.md",
    "docs/runbooks/PUBLISH_AND_OPERATIONS.md",
    "CONTRIBUTING.md",
    "README.md",
)

# Gitignored / runtime-only references the docs legitimately name.
ALLOWLIST = {
    ".env.test",
    ".env",
    "mirror/public-core",
    "venv/bin/python",
    "p313-redis",
}

_PATH_RE = re.compile(r"`([^`\n]+)`")


def _looks_like_path(ref: str) -> bool:
    lowered = ref.lower()
    if lowered in {r.lower() for r in ALLOWLIST}:
        return False
    if lowered.startswith(("scripts/", "hub/", "frontend/", "docs/", "tests/", "sdk/")):
        return True
    if lowered in {
        "makefile",
        "makefile.core",
        "docker-compose.yml",
        "docker-compose.test.yml",
        "docker-compose.test.core.yml",
        "docker-compose.core.yml",
        "pyproject.toml",
    }:
        return True
    return bool(re.match(r"^[\w./-]+\.(py|ts|tsx|sh|md|yml|yaml|json|txt)$", lowered))


def collect_violations(root: Path, docs: tuple[str, ...] = DOCS) -> list[str]:
    violations: list[str] = []
    for rel in docs:
        doc = root / rel
        if not doc.exists():
            violations.append(f"{rel}: doc file itself missing")
            continue
        text = doc.read_text()
        for match in _PATH_RE.finditer(text):
            ref = match.group(1).strip()
            # Strip shell fragments like ``<paths>`` or ``<minio ...>``.
            if any(c in ref for c in "<>"):
                continue
            if not _looks_like_path(ref):
                continue
            # ``script.py --flag value`` → the script path is the first token.
            normalized = ref.split()[0]
            if normalized.startswith("./"):
                normalized = normalized[2:]
            target = root / normalized
            if not target.exists():
                violations.append(f"{rel}: reference {ref!r} does not resolve")
    return sorted(set(violations))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 docs reference integrity")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    violations = collect_violations(args.root)
    if violations:
        print(f"DOCS-REFS: {len(violations)} broken reference(s):")
        for entry in violations:
            print(f"  {entry}")
        return 1
    print("DOCS-REFS: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
