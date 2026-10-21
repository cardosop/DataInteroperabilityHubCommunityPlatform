#!/usr/bin/env python3
"""P0-17 (W105-MGMT-COMMAND-AUDIT) — management-command audit coverage gate.

Every management command under ``hub`` is cross-tenant by default (the
CLAUDE.md contract: admin-DB + per-tenant ``tenant_context`` loops) and
must therefore emit audit evidence. The gate classifies each command
module statically:

  AUDITED — the ``Command`` class inherits ``AuditedCommand`` (the
    ``hub/apps/audit/command_audit.py`` chokepoint), or the module calls
    ``emit_command_audit`` / ``create_audit_event`` directly;
  READ-ONLY ALLOWLISTED — ``lint/mgmt-command-audit-allowlist.yml``
    carries a path + reason (readiness probes, dump/inspect commands,
    pure-read commands). Ratcheted: a NEW unwired command flips the
    gate RED.

Usage:
    python scripts/check_mgmt_command_audit.py                 # hub tree
    python scripts/check_mgmt_command_audit.py --path DIR --allowlist FILE
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("check_mgmt_command_audit.py requires PyYAML") from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_ROOTS = [
    REPO_ROOT / "hub" / "management",
    REPO_ROOT / "hub" / "apps",
]
DEFAULT_ALLOWLIST = REPO_ROOT / "lint" / "mgmt-command-audit-allowlist.yml"

_AUDIT_EVIDENCE_NAMES = frozenset(
    {"emit_command_audit", "create_audit_event"}
)


def _command_is_audited(tree: ast.AST) -> bool:
    """True when the Command class uses the chokepoint or emits directly."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Command":
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "AuditedCommand":
                return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _AUDIT_EVIDENCE_NAMES:
                return True
            if (
                isinstance(func, ast.Attribute)
                and func.attr in _AUDIT_EVIDENCE_NAMES
            ):
                return True
    return False


def scan(roots: list[Path]) -> list[str]:
    """Return the list of command modules that are neither audited nor
    (here) allowlisted."""
    uncovered: list[str] = []
    for base in roots:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("management/commands/*.py")):
            if p.name == "__init__.py":
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            # Helper modules (no Command class) are exercised by the
            # command that imports them — not independently classified.
            has_command = any(
                isinstance(n, ast.ClassDef) and n.name == "Command"
                for n in ast.walk(tree)
            )
            if not has_command:
                continue
            if not _command_is_audited(tree):
                uncovered.append(_repo_relative(p))
    return uncovered


def _repo_relative(path: Path) -> str:
    """Checkout-portable paths: repo-relative when under REPO_ROOT.

    The allowlist must match in CI's checkout root, not the operator's
    absolute path (the P0-17 agent wave found the absolute-only bug).
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_allowlist(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError):
        return set()
    return {
        str(entry.get("path"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("path")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Management-command audit coverage gate."
    )
    parser.add_argument("--path", nargs="+", type=Path, default=DEFAULT_SEARCH_ROOTS)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    args = parser.parse_args(argv)

    uncovered = scan(args.path)
    allow = _load_allowlist(args.allowlist)
    active = [p for p in uncovered if _repo_relative(Path(p)) not in allow]
    if active:
        print(
            f"mgmt-command-audit gate FAILED — {len(active)} command(s) with "
            "no audit evidence and no read-only allowlist entry:"
        )
        for p in sorted(active):
            print(f"  {p}")
        print(
            "Inherit AuditedCommand (hub/apps/audit/command_audit.py), emit "
            "create_audit_event directly, or add a ratcheted read-only "
            "allowlist entry with a reason."
        )
        return 1
    print(
        f"mgmt-command-audit gate clean: {len(uncovered)} uncovered of which "
        f"{len(uncovered) - len(active)} allowlisted; 0 active violations"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
