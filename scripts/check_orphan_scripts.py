#!/usr/bin/env python3
"""
GATE-59 — Orphan-script gate (oss-release-remediation W12.4).

CI invariant: ZERO unwired quality scripts. Every ``scripts/check_*``,
``lint_*``, ``audit_*``, ``verify_*`` file (.py/.sh/.cjs/.mjs) must be
either:

  * WIRED — referenced from a seed surface (CI workflows, Makefiles,
    pre-commit, package.json, pyproject, docker-compose, or the CI
    pytest list) or transitively from a wired script through a STRICT
    reference (``scripts/<name>`` full path, ``import <stem>``, or
    ``source``/``bash``/``sh <name>`` — a bare name in a comment is
    documentation, not wiring), or
  * DELETED — absent from the tree, with the disposition recorded in
    ``scripts/script_wiring_ledger.json`` (``deleted``: {name: reason}).

A NEW script must be wired in the SAME PR: an untriaged script (no
ledger row) fails the gate, and a ``wired`` row must cite a surface
that really references the script — the ledger is honest by
construction, not prose.

The gate skips itself (its wiring is this very contract), and .json
files are data, not scripts (``lint_debt_baseline.json`` is not a
quality script).

Usage:
  python scripts/check_orphan_scripts.py --check
  python scripts/check_orphan_scripts.py --update   # bootstrap the ledger
  --root PATH   scan a different tree (planted pins / built public tree)
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GATE_NAME = Path(__file__).name

CLASS_RE = re.compile(r"^(check|lint|audit|verify)_")
SCRIPT_EXTS = {".py", ".sh", ".cjs", ".mjs"}

# Seed surfaces: files whose TEXT references a script by bare name (that
# is how Makefiles and workflows invoke them). docker-compose counts —
# an ops script in a compose command is wired, not orphaned.
_SEED_GLOBS = (
    ".github/workflows/*.yml",
    # Nested overlay workflows are real CI too — the public-tree overlay
    # wires check_dco.sh (scripts/publish_public_overlay/.github/workflows).
    "**/.github/workflows/*.yml",
    "Makefile",
    "Makefile.core",
    ".pre-commit-config.yaml",
    "package.json",
    "frontend/package.json",
    "pyproject.toml",
    "docker-compose*.yml",
    "compose*.yml",
)

_PYTEST_SEED_RE = re.compile(r"scripts/tests/(test_[a-z0-9_]+\.py)")


def _strict_edge(name: str, stem: str) -> re.Pattern:
    """A REAL script-to-script reference: the full ``scripts/<name>``
    path, an ``import <stem>``, or a shell ``source``/``bash``/``sh``
    invocation. A bare name in a comment is documentation, not wiring."""
    return re.compile(
        rf"(?:scripts/{re.escape(name)}\b|import\s+{re.escape(stem)}\b|"
        rf"source\s+{re.escape(name)}\b|\bbash\s+{re.escape(name)}\b|"
        rf"\bsh\s+{re.escape(name)}\b)"
    )


def _iter_scripts(root: Path) -> list[str]:
    """The gate's inventory class, sorted."""
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in scripts_dir.iterdir()
        if p.is_file()
        and CLASS_RE.match(p.name)
        and p.suffix in SCRIPT_EXTS
        and p.name != _GATE_NAME
    )


def _iter_seed_files(root: Path) -> list[Path]:
    files = []
    for glob in _SEED_GLOBS:
        for path in sorted(root.glob(glob)):
            if path.is_file() and path not in files:
                files.append(path)
    return files


def _pytest_seed_files(root: Path) -> list[Path]:
    """The CI pytest-list test files: a script referenced by a test that
    runs in CI is exercised in CI — that is wiring."""
    results = []
    seen: set[str] = set()
    for path in _iter_seed_files(root):
        if path.suffix != ".yml":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in sorted(set(_PYTEST_SEED_RE.findall(text))):
            if name in seen:
                continue
            seen.add(name)
            test_path = root / "scripts" / "tests" / name
            if test_path.is_file():
                results.append(test_path)
    return results


def compute_wiring(
    root: Path,
) -> tuple[set[str], dict[str, str]]:
    """(wired script names, name → referencing surface) via seed surfaces
    + strict-reference closure over wired scripts."""
    inventory = set(_iter_scripts(root))
    seeds: dict[str, str] = {}
    for path in _iter_seed_files(root) + _pytest_seed_files(root):
        try:
            seeds[str(path.relative_to(root))] = path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue

    wired: set[str] = set()
    surface_of: dict[str, str] = {}
    for name in inventory:
        for surface, text in seeds.items():
            if name in text:
                wired.add(name)
                surface_of[name] = surface
                break

    script_texts = {
        p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in (root / "scripts").iterdir()
        if p.is_file() and p.suffix in SCRIPT_EXTS
    }
    changed = True
    while changed:
        changed = False
        for name in inventory - wired:
            stem = name.rsplit(".", 1)[0]
            edge = _strict_edge(name, stem)
            for wname, wtext in script_texts.items():
                if wname in wired and re.search(edge, wtext):
                    wired.add(name)
                    surface_of[name] = f"scripts/{wname}"
                    changed = True
                    break
    return wired, surface_of


def _load_ledger(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("wired"), dict) or not isinstance(
        payload.get("deleted"), dict
    ):
        raise TypeError(f"{path}: expected 'wired' and 'deleted' objects")
    return payload


def check(root: Path, ledger_path: Path) -> int:
    """GATE-59 main gate. 0 = clean, 1 = violation."""
    if not ledger_path.is_file():
        print(
            "orphan-script gate: ledger missing at "
            f"{ledger_path.relative_to(root)} — run --update to bootstrap "
            "the wired rows, then record every deleted script with a reason"
        )
        return 1
    try:
        ledger = _load_ledger(ledger_path)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"orphan-script gate: ledger unreadable — {exc}")
        return 1

    inventory = set(_iter_scripts(root))
    wired, _surface_of = compute_wiring(root)

    violations: list[str] = []

    # Every script must have a ledger row; wired rows must cite a REAL
    # referencing surface; deleted rows must name absent files.
    for name in sorted(inventory):
        if name in ledger["wired"] and name not in ledger["deleted"]:
            surface = ledger["wired"][name]
            surface_path = root / surface
            if not surface_path.is_file():
                violations.append(
                    f"ledger 'wired' row for {name} cites missing surface " f"{surface}"
                )
            elif name not in surface_path.read_text(encoding="utf-8", errors="replace"):
                violations.append(
                    f"ledger 'wired' row for {name} cites {surface}, which "
                    "does not reference it — the ledger must be honest"
                )
            elif name not in wired:
                violations.append(
                    f"ledger says {name} is wired via {surface}, but no "
                    "reference chain reaches it"
                )
        elif name in ledger["deleted"] and name not in ledger["wired"]:
            violations.append(
                f"ledger says {name} is deleted but the script still "
                "exists — delete it or wire it and move the row"
            )
        elif name not in ledger["wired"] and name not in ledger["deleted"]:
            violations.append(
                f"untriaged script {name} — wire it in the same PR or "
                "delete it, then record the disposition in "
                "scripts/script_wiring_ledger.json"
            )
        elif name in ledger["wired"] and name in ledger["deleted"]:
            violations.append(f"{name} appears in BOTH ledger sections — pick one")

    # Every unwired script fails regardless of the ledger (the ledger's
    # wired rows are verified above; a deleted row for a file that still
    # exists was already reported).
    for name in sorted(inventory - wired):
        if name in ledger["deleted"]:
            continue
        violations.append(
            f"unwired script {name} — reference it from CI/Makefile/"
            "pre-commit (or a wired script) in the same PR, or delete it"
        )

    if violations:
        print(f"orphan-script gate: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"orphan-script gate clean: {len(wired)} script(s) wired, "
        f"{len(ledger['deleted'])} deleted with recorded reasons"
    )
    return 0


def update(root: Path, ledger_path: Path) -> int:
    """Bootstrap the ledger: wired rows from the computed wiring graph;
    preserves existing deleted rows."""
    old_deleted: dict[str, str] = {}
    if ledger_path.is_file():
        try:
            old_deleted = _load_ledger(ledger_path)["deleted"]
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            print(f"orphan-script ledger update: unreadable — {exc}")
            return 1
    wired, surface_of = compute_wiring(root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(
            {
                "wired": {name: surface_of[name] for name in sorted(wired)},
                "deleted": old_deleted,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"orphan-script ledger updated: {len(wired)} wired, "
        f"{len(old_deleted)} deleted"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GATE-59 orphan-script gate")
    parser.add_argument("--check", action="store_true", help="blocking gate")
    parser.add_argument(
        "--update", action="store_true", help="bootstrap the wiring ledger"
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    root = args.root
    ledger_path = root / "scripts" / "script_wiring_ledger.json"

    if args.check:
        return check(root, ledger_path)
    if args.update:
        return update(root, ledger_path)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
