#!/usr/bin/env python3
"""
Phase 260 acceptance #3 — lint-no-client-tenant-id.

Forbids endpoints from reading `tenant_id` out of `request.data` /
`request.query_params` **for tenant scoping**, because that pattern is
the root cause of the cross-tenant leaks closed in 260.A. Tenant scope
must come from `get_request_tenant_id(request)` (request context,
authenticated identity) — never from a client-supplied value.

A few legitimate sites still need to read the client-supplied value, but
**only** to detect and reject cross-tenant mismatch (defence-in-depth)
or in flows where the user is explicitly choosing a tenant
(e.g. `switch_tenant`). Those sites live in the allowlist at
`lint/no-client-tenant-id-allowlist.yml`.

The lint reports one violation per match outside the allowlist and
exits 1 if any are found.

Pattern detection
-----------------
We grep for these regexes (each line, anywhere in `hub/apps/`):

  * `request\\.data\\.get\\(['\"]tenant_id['\"]`
  * `request\\.query_params\\.get\\(['\"]tenant_id['\"]`
  * `self\\.request\\.data\\.get\\(['\"]tenant_id['\"]`
  * `self\\.request\\.query_params\\.get\\(['\"]tenant_id['\"]`

Files matching `**/test_*.py` are skipped (tests legitimately exercise
the rejected-pattern path); generated migrations are skipped; backup
files (`*.backup`) are skipped.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - resolved by `pip install pyyaml`
    raise SystemExit("lint_no_client_tenant_id.py requires PyYAML — `pip install pyyaml`") from exc


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_ROOT = REPO_ROOT / "hub" / "apps"
DEFAULT_ALLOWLIST = REPO_ROOT / "lint" / "no-client-tenant-id-allowlist.yml"

# Each pattern matches a python source line that reads tenant_id out of
# the HTTP request envelope. The set is deliberately small — broaden
# only if a new attack-surface variant appears.
_PATTERN_RE = re.compile(
    r"""
    (?:self\.)?request          # request or self.request
    \.
    (?:data|query_params)       # the HTTP envelope
    \.get\(\s*
    ['"]tenant_id['"]           # the field we forbid clients from setting
    """,
    re.VERBOSE,
)

# File patterns that are skipped from scanning. Tests exercise the
# rejected-pattern path explicitly; migrations don't read HTTP requests;
# backup files are stale by definition.
_SKIP_GLOBS = (
    "**/tests/**",
    "**/test_*.py",
    "**/migrations/**",
    "**/__pycache__/**",
    "**/*.backup",
)


def _iter_python_files(search_root: Path) -> Iterable[Path]:
    for path in search_root.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        skip = False
        for glob in _SKIP_GLOBS:
            if rel.match(glob):
                skip = True
                break
        if skip:
            continue
        yield path


def _load_allowlist(path: Path) -> set[tuple[str, int]]:
    """Return a set of (relpath, line) tuples that are explicitly allowed.

    Allowlist YAML schema:

        version: 1
        entries:
          - file: hub/apps/auth/views.py
            line: 1665
            reason: switch_tenant — user explicitly chooses target tenant
          - file: ...
    """
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SystemExit(f"{path}: top-level YAML must be a mapping")
    entries = raw.get("entries", []) or []
    allowed: set[tuple[str, int]] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SystemExit(f"{path}: entry {i} must be a mapping")
        file_str = entry.get("file")
        line = entry.get("line")
        reason = entry.get("reason", "")
        if not file_str or not isinstance(line, int) or not reason:
            raise SystemExit(
                f"{path}: entry {i} requires non-empty 'file', integer 'line', "
                f"and non-empty 'reason' fields (got {entry!r})"
            )
        allowed.add((file_str, int(line)))
    return allowed


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line_text) tuples that match the pattern."""
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return hits
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _PATTERN_RE.search(line):
            hits.append((line_no, line.rstrip()))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SEARCH_ROOT,
        help="Search root (default: hub/apps).",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help=f"Allowlist YAML path (default: {DEFAULT_ALLOWLIST.relative_to(REPO_ROOT)}).",
    )
    args = parser.parse_args()

    allowed = _load_allowlist(args.allowlist)
    violations: list[str] = []

    for path in _iter_python_files(args.root):
        hits = _scan_file(path)
        if not hits:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        for line_no, line_text in hits:
            if (rel, line_no) in allowed:
                continue
            violations.append(f"{rel}:{line_no}: {line_text.strip()}")

    if violations:
        print(
            "::error::lint-no-client-tenant-id detected client-supplied "
            "tenant_id reads outside the allowlist. Tenant scope MUST come "
            "from `get_request_tenant_id(request)`, NOT from "
            "`request.data` / `request.query_params`. If a site is a "
            "legitimate cross-tenant rejection guard (defence-in-depth) "
            "or an explicit tenant switch flow, add it to "
            f"{args.allowlist.relative_to(REPO_ROOT)} with a written "
            "reason. Otherwise remove the read.",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"lint-no-client-tenant-id: scanned {args.root.relative_to(REPO_ROOT)}; "
        f"no violations outside the allowlist ({len(allowed)} allowed entries)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
