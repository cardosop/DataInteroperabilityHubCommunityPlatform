#!/usr/bin/env python3
"""GATE-29 — core/paid boundary checker (Phase 313.1).

Enforces the invariant "core apps MUST NOT import paid apps":

1. AST scan of the core tree for ``from hub.apps.<paid> ...`` / ``import
   hub.apps.<paid>`` at ANY nesting level (module, function, class).
2. String-literal scan of ``hub/settings.py`` for paid module paths (covers
   MIDDLEWARE / DATABASE_ROUTERS entries that bypass the import scanner).
3. Migration scan of core apps for FK references to paid models
   (``to='marketplace.Listing'``-style) — schema isolation invariant.

Membership comes from ``hub/apps/manifest.py`` (AST-parsed — no Django
imports, so this script runs without a configured environment).

Allowlist ratchet: ``scripts/core_boundary_allowlist.txt`` holds exact
``relpath:lineno:reason`` triples for audited transitional entries.
``--check-allowlist-growth`` fails when the working allowlist grows beyond
``git HEAD`` — the ratchet only ever shrinks.

Usage:
    python scripts/check_core_boundary.py            # fail on violations
    python scripts/check_core_boundary.py --list     # print all violations
    python scripts/check_core_boundary.py --root DIR --allowlist FILE  # tests
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
from pathlib import Path

DEFAULT_SCAN_DIRS = ("hub/apps", "hub/tests", "tests", "scripts", "cli", "sdk")
DEFAULT_EXTRA_FILES = ("hub/settings.py", "hub/urls.py", "hub/manage.py")

# Paid model FK reference pattern (label.Model in migrations): schema
# isolation — core migrations must never point at paid tables.
_PAID_LABELS = (
    "marketplace",
    "semantic",
    "billing",
    "baas",
    "rate_limiting",
    "ai",
    "ml",
    "social",
    "graphql",
    "graphql_ld",
    "graphql_graphene",
)
_MIGRATION_FK_RE = re.compile(
    r"\bto\s*=\s*['\"](?:" + "|".join(_PAID_LABELS) + r")\."
)


def _eval_container(node: ast.AST) -> list | None:
    """Evaluate a literal container expression (tuple/list/set/frozenset(...))."""
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return list(ast.literal_eval(node))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("frozenset", "set", "tuple", "list")
        and len(node.args) == 1
        and len(node.keywords) == 0
    ):
        return list(ast.literal_eval(node.args[0]))
    return None


def _read_paid_modules(manifest_path: Path) -> tuple[list[str], list[str]]:
    """AST-parse the manifest membership (no imports — no side effects)."""
    tree = ast.parse(manifest_path.read_text(), filename=str(manifest_path))
    paid: list[str] = []
    all_apps: list[str] = []
    for node in tree.body:
        target_name: str | None = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target_name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        if target_name == "_PAID_MODULES" and value is not None:
            paid = _eval_container(value) or []
        elif target_name == "ALL_HUB_APPS" and value is not None:
            all_apps = _eval_container(value) or []
    if not paid:
        raise SystemExit("manifest parse failed: _PAID_MODULES not found")
    return paid, all_apps


_APPS_CONFIG_SUFFIX_RE = re.compile(
    r"^(hub\.apps\.[A-Za-z_][A-Za-z0-9_]*)\.apps\.[A-Za-z_][A-Za-z0-9_]*$"
)


def _normalise(entry: str) -> str:
    """Strip a trailing '.apps.XConfig' suffix only for AppConfig-class
    entries ('hub.apps.compliance.apps.ComplianceConfig' →
    'hub.apps.compliance'). Plain module paths like 'hub.apps.semantic'
    — which contain '.apps.' INSIDE the path — are returned unchanged."""
    m = _APPS_CONFIG_SUFFIX_RE.match(entry)
    return m.group(1) if m else entry


class Violation:
    def __init__(self, relpath: str, lineno: int, detail: str):
        self.relpath = relpath
        self.lineno = lineno
        self.detail = detail

    def key(self) -> str:
        return f"{self.relpath}:{self.lineno}"

    def __str__(self) -> str:
        return f"{self.key()}: {self.detail}"


def _scan_python_file(path: Path, root: Path, paid_modules: list[str], violations: list[Violation]) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return

    paid_set = set(paid_modules)
    rel = path.relative_to(root).as_posix()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(node.module == m or node.module.startswith(m + ".") for m in paid_set):
                violations.append(
                    Violation(rel, node.lineno, f"imports paid module: {node.module}")
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == m or alias.name.startswith(m + ".") for m in paid_set):
                    violations.append(
                        Violation(rel, node.lineno, f"imports paid module: {alias.name}")
                    )

    # Migration schema-isolation check (core migrations only — paid app
    # migrations are not scanned at all).
    if "/migrations/" in rel or rel.endswith("/migrations"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _MIGRATION_FK_RE.search(line):
                violations.append(
                    Violation(rel, lineno, f"migration FK references paid model: {line.strip()[:90]}")
                )


def _scan_settings_strings(path: Path, root: Path, paid_modules: list[str], violations: list[Violation]) -> None:
    """String-literal scan for paid module paths (MIDDLEWARE/ROUTERS etc.)."""
    rel = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    paid_names = {_normalise(m) for m in paid_modules}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name in paid_names:
                if node.value == name or node.value.startswith(name + "."):
                    violations.append(
                        Violation(rel, node.lineno, f"string references paid module: {node.value}")
                    )


def _load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#"):
            out.add(stripped.split(":", 2)[0] + ":" + stripped.split(":", 2)[1])
    return out


def collect_violations(root: Path, paid_modules: list[str]) -> list[Violation]:
    violations: list[Violation] = []
    paid_dirs = {
        str(root / m.replace(".", "/"))
        for m in paid_modules
    }
    for scan_dir in DEFAULT_SCAN_DIRS:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            # Never scan paid app subtrees (their internal paid imports are legal).
            if any(str(path).startswith(pd) for pd in paid_dirs):
                continue
            _scan_python_file(path, root, paid_modules, violations)
    for extra in DEFAULT_EXTRA_FILES:
        path = root / extra
        if not path.exists():
            continue
        _scan_python_file(path, root, paid_modules, violations)
        if extra == "hub/settings.py":
            _scan_settings_strings(path, root, paid_modules, violations)

    # Dedupe by (path, lineno) — keep the import-level detail first.
    seen: dict[str, Violation] = {}
    for v in violations:
        seen.setdefault(v.key(), v)
    return list(seen.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GATE-29 — core boundary checker")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path(__file__).resolve().parent / "core_boundary_allowlist.txt",
    )
    parser.add_argument("--list", action="store_true", help="print violations instead of failing")
    parser.add_argument(
        "--check-allowlist-growth",
        action="store_true",
        help="fail when the allowlist grows beyond git HEAD (ratchet)",
    )
    args = parser.parse_args(argv)

    paid, _all = _read_paid_modules(args.root / "hub" / "apps" / "manifest.py")
    violations = collect_violations(args.root, [_normalise(m) for m in paid])
    allowlist = _load_allowlist(args.allowlist)
    unallowed = [v for v in violations if v.key() not in allowlist]

    if args.list:
        for v in violations:
            print(str(v))
        return 0

    if args.check_allowlist_growth and args.allowlist.exists():
        head = subprocess.run(
            ["git", "show", f"HEAD:{args.allowlist.relative_to(args.root)}"],
            check=False, capture_output=True, text=True,
        )
        if head.returncode == 0:
            head_keys = {
                ln.split(":", 2)[0] + ":" + ln.split(":", 2)[1]
                for ln in head.stdout.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            }
            added = sorted(allowlist - head_keys)
            if added:
                print("GATE-29: allowlist ratchet violation — new entries vs HEAD:")
                for entry in added:
                    print(f"  + {entry}")
                return 1

    if unallowed:
        print(f"GATE-29: {len(unallowed)} boundary violation(s) in core code:")
        for v in sorted(unallowed, key=str):
            print(f"  {v}")
        print("Fix the import direction (registries/hooks/event bus) or add an")
        print("audited allowlist entry (path:line:reason) — the allowlist never grows.")
        return 1

    print("GATE-29: core boundary clean "
          f"({len(violations)} violation(s), {len(violations) - len(unallowed)} allowlisted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
