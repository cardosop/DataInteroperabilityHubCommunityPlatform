#!/usr/bin/env python3
"""GATE-38 — paid ``AppConfig.ready()`` registration ratchet (Phase P.2b).

The runtime seam test (``hub/apps/core/tests/test_hook_provider_coverage.py``)
proves every contract slot is POPULATED in full mode — but it only runs in
the paid suite. A deleted ``set_*`` call in a paid ``apps.py`` must also
fail in the public/core CI, where the paid test files do not exist.

This checker does that without importing Django or any paid module:

1. Reads ``_PAID_MODULES`` from ``hub/apps/manifest.py`` via AST (reuses
   ``_read_paid_modules`` from ``check_core_boundary.py`` — one manifest
   reader for both gates, so the two can never diverge).
2. Reads ``HOOK_API_CONTRACT`` from ``hub.apps.core.commercial_hooks``
   (a pure module: contextlib/typing only — safe for a standalone script).
3. AST-parses each paid ``apps.py`` and collects every commercial-hook
   NAME that module actually invokes as a call (from-hooks imports +
   ``Call`` nodes whose func is one of those names, at any nesting depth —
   covers ``ready()`` bodies, nested closures, and helper functions).

Violations (exit 1):

- **orphaned contract setter** — a contract row declares a setter
  (``setter_pair is None``, ``registry_key`` set) that NO paid ``apps.py``
  invokes. The exact dropped-registration class P.2 exists to catch.
- **unlisted hooks call** — a paid ``apps.py`` calls a commercial-hooks
  setter that has no contract row (renamed/dead setter, drift from the
  other direction). Utilities (``reset_hooks``/``hooks_snapshot``) and the
  runtime-keyed ``register_service_client_factory``/``get_*`` rows are
  excluded by their contract shape (registry_key is None).
- **missing apps.py** — a ``_PAID_MODULES`` entry has no ``apps.py``.

Exit 0 clean, 1 on violations. No mocks: synthetic trees for the TDD suite
run through the real checker.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Sibling-import precedent: scripts/tests/test_check_core_boundary_guards.py:31.
from check_core_boundary import _read_paid_modules

CONTRACT_MODULE = "hub.apps.core.commercial_hooks"
#: The contract table is the source of truth for the PAID↔CORE seam. Read it
#: from THIS repository's tree (the script's own checkout), never from a
#: --root synthetic tree, so TDD fixtures cannot accidentally redefine the
#: contract they are testing against.
CONTRACT_FILE = (
    Path(__file__).resolve().parent.parent / "hub" / "apps" / "core" / "commercial_hooks.py"
)
_UTILITY_FUNCTIONS = {"reset_hooks", "hooks_snapshot"}


def _contract_rows() -> list[tuple[str, str, str | None, str | None]]:
    """Parse HOOK_API_CONTRACT via AST — no imports, no Django.

    The table is a module-level tuple literal annotated ``tuple[tuple[str,
    str, str | None, str | None], ...]``; parsing it keeps this gate runnable
    in the public CI where ``hub/apps`` is scrubbed.
    """
    tree = ast.parse(CONTRACT_FILE.read_text(), filename=str(CONTRACT_FILE))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = (
                node.targets[0]
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                else node.target
            )
            if isinstance(target, ast.Name) and target.id == "HOOK_API_CONTRACT":
                value = node.value
                return ast.literal_eval(value)
    raise SystemExit(f"contract parse failed: HOOK_API_CONTRACT not found in {CONTRACT_FILE}")


def _contract_setters() -> dict[str, str]:
    """Contract setter rows: {setter_name: registry_key}."""
    return {row[0]: row[3] for row in _contract_rows() if row[2] is None and row[3] is not None}


def _contract_function_names() -> set[str]:
    """Every function the contract names (setters, callers, utilities)."""
    return {row[0] for row in _contract_rows()}


def _invoked_hook_names(apps_py: Path) -> set[str]:
    """Names imported from the hooks module AND called anywhere in the file."""
    tree = ast.parse(apps_py.read_text(), filename=str(apps_py))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == CONTRACT_MODULE and node.level == 0:
            imported.update(alias.name for alias in node.names)
    invoked: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # from hub.apps.core.commercial_hooks import set_x → call is Name.
        if isinstance(func, ast.Name) and func.id in imported:
            invoked.add(func.id)
        # import hub.apps.core.commercial_hooks → call is Attribute.
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "commercial_hooks"
        ):
            invoked.add(func.attr)
    return invoked


def collect_violations(root: Path) -> list[str]:
    violations: list[str] = []
    manifest_path = root / "hub" / "apps" / "manifest.py"
    if not manifest_path.exists():
        return [f"manifest not found: {manifest_path}"]
    paid_modules, _all = _read_paid_modules(manifest_path)

    # Contract setter name → the paid module that invokes it ('' if none).
    setters = _contract_setters()
    known_names = _contract_function_names()
    invoker: dict[str, str] = {}
    for module in paid_modules:
        apps_py = root / module.replace(".", "/") / "apps.py"
        if not apps_py.exists():
            violations.append(f"paid module {module} has no apps.py")
            continue
        invoked = _invoked_hook_names(apps_py)
        for name in invoked:
            invoker.setdefault(name, module)
            if name not in known_names and name not in _UTILITY_FUNCTIONS:
                violations.append(
                    f"{module}: calls commercial-hooks '{name}' but no "
                    "HOOK_API_CONTRACT row covers it"
                )

    for setter, registry_key in sorted(setters.items()):
        if setter not in invoker:
            violations.append(
                f"contract setter '{setter}' (slot '{registry_key}') is invoked "
                "by no paid apps.py — a dropped registration silently "
                "degrades full mode to the core fallback"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GATE-38 — paid ready() registration ratchet")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    violations = collect_violations(args.root)
    for violation in violations:
        print(f"GATE-38: {violation}")
    if violations:
        return 1
    print("GATE-38: all contract setters registered by paid apps.py files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
