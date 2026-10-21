#!/usr/bin/env python3
"""P0-17 (W105-SIGNAL-TENANT-CONTEXT-LINT) — signal receivers must wrap
their bodies in ``tenant_context``.

Every signal receiver registered under ``hub/apps`` — via the
``@receiver(...)`` decorator or a ``<signal>.connect(...)`` call — must
run inside ``tenant_context``. The RLS request-path contract makes a
signal callback that touches tenant-scoped models the same leak class
as an unwrapped worker task; receivers that are enqueue-only today are
still wrapped, because handlers accrete DB work (the 2026-10-05
maturity-audit finding: "currently enqueue-only — fragile as handlers
accrete DB work; no lint").

Wrapping evidence (any call in the receiver body):
  * ``tenant_context(...)`` (the canonical ``with tenant_context(...)``)
  * ``_run_with_tenant_context(...)`` / ``run_with_tenant_context(...)``
    (the tenants/signals.py helper that re-enters context around a
    deferred/on_commit callback)

Escapes: ``lint/signal-tenant-context-allowlist.yml`` —
``path: line: reason`` triples, ratcheted like the no-client-tenant-id
allowlist. A NEW unwrapped receiver flips the gate RED (exit 1).

Usage:
    python scripts/lint_signal_tenant_context.py                 # hub/apps
    python scripts/lint_signal_tenant_context.py --path DIR --allowlist FILE
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("lint_signal_tenant_context.py requires PyYAML") from exc

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_ROOT = REPO_ROOT / "hub" / "apps"
DEFAULT_ALLOWLIST = REPO_ROOT / "lint" / "signal-tenant-context-allowlist.yml"

_WRAP_EVIDENCE = frozenset(
    {"tenant_context", "_run_with_tenant_context", "run_with_tenant_context"}
)


def _has_wrap_evidence(func: ast.AST) -> bool:
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _WRAP_EVIDENCE
        ):
            return True
    return False


def _receiver_candidates(tree: ast.AST) -> list[tuple[str, int, ast.AST | None]]:
    """(label, line, resolved-body) for every receiver registration.

    ``body=None`` marks an unresolvable registration (lambda, external
    import, attribute target) — reported so nothing slips silently.
    """
    defs = {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # module imports: name → module path (for the imported-target rule)
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports[alias.asname or alias.name] = node.module
    candidates: list[tuple[str, int, ast.AST | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "receiver":
            for dname, d in defs.items():
                if node in d.decorator_list:
                    # report the DEF line — that is the line the wrap
                    # lands on and what the allowlist anchors
                    candidates.append((dname, d.lineno, d))
                    break
            else:
                candidates.append(("(receiver decorator)", node.lineno, None))
            continue
        if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
            continue
        if not node.args:
            candidates.append(("(connect without target)", node.lineno, None))
            continue
        target = node.args[0]
        if isinstance(target, ast.Name):
            if target.id in defs:
                candidates.append((target.id, node.lineno, defs[target.id]))
            elif target.id in imports:
                module = imports[target.id]
                if module.startswith("hub.apps"):
                    # Receiver defined in another scanned hub module — its
                    # definition site carries the wrap evidence.
                    continue
                candidates.append(
                    (f"{target.id} (imported from {module})", node.lineno, None)
                )
            else:
                candidates.append((target.id, node.lineno, None))
        elif isinstance(target, ast.Lambda):
            candidates.append(("(lambda receiver)", node.lineno, target))
        elif isinstance(target, ast.Attribute):
            # obj.method — resolve the method def in this file
            found = None
            for dname, d in defs.items():
                if dname == target.attr:
                    found = d
                    break
            candidates.append((f"{target.attr} (method)", node.lineno, found))
        else:
            candidates.append(("(unresolvable receiver)", node.lineno, None))
    return candidates


def scan_paths(paths: list[Path]) -> list[tuple[str, int, str]]:
    """Return [(path, line, label)] for unwrapped receivers."""
    violations: list[tuple[str, int, str]] = []
    for base in paths:
        for p in sorted(base.rglob("*.py")):
            if any(seg in p.parts for seg in ("tests", "migrations")):
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            candidates = _receiver_candidates(tree)
            if not candidates:
                continue
            for label, line, body in candidates:
                if body is None:
                    violations.append((str(p), line, f"{label} — unresolvable"))
                elif not _has_wrap_evidence(body):
                    violations.append((str(p), line, f"{label} — unwrapped"))
    return violations


def _repo_relative(path: Path) -> str:
    """Checkout-portable paths (see check_mgmt_command_audit.py)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_allowlist(path: Path) -> set[tuple[str, int]]:
    if not path.is_file():
        return set()
    try:
        entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError):
        return set()
    result = set()
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path"):
            result.add((str(entry["path"]), int(entry.get("line", 0))))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Signal receivers must wrap in tenant_context."
    )
    parser.add_argument("--path", nargs="+", type=Path, default=[DEFAULT_SEARCH_ROOT])
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    args = parser.parse_args(argv)

    violations = scan_paths(args.path)
    allow = _load_allowlist(args.allowlist)
    active = [v for v in violations if (_repo_relative(Path(v[0])), v[1]) not in allow]
    if active:
        print(
            f"signal-tenant-context lint FAILED — {len(active)} unwrapped "
            "receiver(s):"
        )
        for path, line, label in active:
            print(f"  {path}:{line} — {label}")
        print(
            "Wrap the receiver body in tenant_context (or add a ratcheted "
            "allowlist entry with a reason)."
        )
        return 1
    print(
        f"signal-tenant-context lint clean: {len(violations)} receiver "
        f"registration(s) scanned, {len(violations) - len(active)} "
        "allowlisted, 0 unwrapped"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
