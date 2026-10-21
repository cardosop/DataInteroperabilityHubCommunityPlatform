#!/usr/bin/env python3
"""Raw error-dict lint (W12.5) — one error envelope, no inline dicts.

Every API error MUST be built through the canonical flat envelope helper
(``hub.apps.core.responses.api_error_response`` /
``hub.apps.api.standards.response_formats.format_error_response``) so
the wire shape ``{"detail", "code", "details"}`` has ONE construction
site. This checker AST-flags views/services that construct error
responses with an inline dict literal (``Response({"detail": ...})``)
instead of the helper — the pre-fix pattern that let the three envelope
shapes drift (design row 3).

Ratchet: the current 169 sites are grandfathered in
``scripts/raw_error_dicts_allowlist.txt`` (``path:line:reason``).
- a raw site NOT in the allowlist fails (new inline error dicts block
  the PR);
- a dead allowlist anchor fails (converting a site to the helper MUST
  prune its entry — the allowlist only shrinks).

Exit 0 clean, 1 violations. ``--update`` re-derives the allowlist from
the tree (post-conversion fix waves only).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = REPO_ROOT / "scripts" / "raw_error_dicts_allowlist.txt"
SCAN_ROOT = REPO_ROOT / "hub"

RESPONSE_CALLS = {"Response", "JsonResponse"}


def _raw_error_sites() -> dict[str, set[str]]:
    """Return {path: {lines}} for inline error-dict Response calls in
    non-test hub code."""
    sites: dict[str, set[str]] = {}
    for path in SCAN_ROOT.rglob("*.py"):
        rel = str(path.relative_to(REPO_ROOT))
        if "/tests/" in rel or "__pycache__" in rel or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name not in RESPONSE_CALLS:
                continue
            if not node.args or not isinstance(node.args[0], ast.Dict):
                continue
            keys = {
                str(k.value)
                for k in node.args[0].keys
                if isinstance(k, ast.Constant)
            }
            if "detail" in keys:
                sites.setdefault(rel, set()).add(node.lineno)
    return sites


def _load_allowlist() -> dict[str, set[str]]:
    entries: dict[str, set[str]] = {}
    if not ALLOWLIST.exists():
        return entries
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        path, lineno, _reason = line.split(":", 2)
        entries.setdefault(path, set()).add(lineno)
    return entries


def _write_allowlist(sites: dict[str, set[str]]) -> None:
    lines = [
        "# Raw inline error-dict sites grandfathered by W12.5. Every API error must",
        "# be built via hub.apps.core.responses.api_error_response (the one flat",
        "# envelope). Converting a site REQUIRES pruning its entry — dead anchors fail.",
    ]
    for path in sorted(sites):
        for lineno in sorted(int(n) for n in sites[path]):
            lines.append(f"{path}:{lineno}:grandfathered raw error dict (W12.5) — convert to api_error_response/format_error_response")
    ALLOWLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="re-derive the allowlist")
    args = parser.parse_args(argv)

    sites = _raw_error_sites()
    if args.update:
        _write_allowlist(sites)
        print(f"raw_error_dicts: allowlist written ({sum(len(v) for v in sites.values())} sites)")
        return 0

    allowed = _load_allowlist()
    violations: list[str] = []
    for path, lines in sorted(sites.items()):
        for lineno in sorted(int(n) for n in lines):
            if str(lineno) not in allowed.get(path, set()):
                violations.append(f"{path}:{lineno}: new raw error dict — use api_error_response/format_error_response")

    dead: list[str] = []
    for path, lines in sorted(allowed.items()):
        live = {str(n) for n in sites.get(path, set())}
        for lineno in sorted(lines):
            if lineno not in live:
                dead.append(f"{path}:{lineno}: dead allowlist anchor — prune it")

    if violations or dead:
        for line in violations:
            print(f"RAW-ERROR-DICT: {line}")
        for line in dead:
            print(f"RAW-ERROR-DICT: {line}")
        print(
            f"raw error dicts: {len(violations)} unsanctioned + {len(dead)} dead anchors "
            f"({sum(len(v) for v in sites.values())} total sites, {sum(len(v) for v in allowed.values())} allowlisted)"
        )
        return 1
    print(
        f"raw_error_dicts: clean ({sum(len(v) for v in sites.values())} sites, all allowlisted)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
