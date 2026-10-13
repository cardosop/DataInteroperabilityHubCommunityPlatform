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

Guard gate (313.H.1): ``--check-guards`` verifies every allowlisted import
survives BOTH core failure modes (RuntimeError private / ModuleNotFoundError
public) — try handlers, HUB_CORE_ONLY/is_core_only branches, or a
``# core-guard: full-mode-only`` annotation (see
docs/test-infrastructure/guard-contract.md). ``--guard-exceptions`` holds
the shrinking baseline; ``--check-guard-growth`` ratchets it with NET
accounting; ``--prefer-explicit`` reports broad except handlers.

Usage:
    python scripts/check_core_boundary.py            # fail on violations
    python scripts/check_core_boundary.py --list     # print all violations
    python scripts/check_core_boundary.py --check-guards [--prefer-explicit]
    python scripts/check_core_boundary.py --root DIR --allowlist FILE  # tests
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

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
_MIGRATION_FK_RE = re.compile(r"\bto\s*=\s*['\"](?:" + "|".join(_PAID_LABELS) + r")\.")


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


class ImportSite:
    """A paid-import node with its AST context, for guard classification."""

    def __init__(
        self, relpath: str, lineno: int, tree: ast.AST, node: ast.AST, source_lines: list[str]
    ):
        self.relpath = relpath
        self.lineno = lineno
        self.tree = tree
        self.node = node
        self.source_lines = source_lines

    def key(self) -> str:
        return f"{self.relpath}:{self.lineno}"


def _scan_python_file(
    path: Path,
    root: Path,
    paid_modules: list[str],
    violations: list[Violation],
    import_sites: list[ImportSite] | None = None,
) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return

    paid_set = set(paid_modules)
    rel = path.relative_to(root).as_posix()
    source_lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(node.module == m or node.module.startswith(m + ".") for m in paid_set):
                violations.append(
                    Violation(rel, node.lineno, f"imports paid module: {node.module}")
                )
                if import_sites is not None:
                    import_sites.append(ImportSite(rel, node.lineno, tree, node, source_lines))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == m or alias.name.startswith(m + ".") for m in paid_set):
                    violations.append(
                        Violation(rel, node.lineno, f"imports paid module: {alias.name}")
                    )
                    if import_sites is not None:
                        import_sites.append(ImportSite(rel, node.lineno, tree, node, source_lines))

    # Migration schema-isolation check (core migrations only — paid app
    # migrations are not scanned at all).
    if "/migrations/" in rel or rel.endswith("/migrations"):
        for lineno, line in enumerate(source_lines, 1):
            if _MIGRATION_FK_RE.search(line):
                violations.append(
                    Violation(
                        rel, lineno, f"migration FK references paid model: {line.strip()[:90]}"
                    )
                )


def _scan_settings_strings(
    path: Path, root: Path, paid_modules: list[str], violations: list[Violation]
) -> None:
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


# ── Guard classification (313.H.1) ────────────────────────────────────────────
#
# Every allowlisted core-site paid import must survive BOTH core failure
# modes: RuntimeError (private repo, app uninstalled) and
# ModuleNotFoundError (public tree, module absent). Sanctioned patterns,
# in preference order (docs/test-infrastructure/guard-contract.md):
#   1. hooks inversion (commercial_hooks) — not statically verifiable,
#      so not part of this classifier;
#   2. an is_core_only()/HUB_CORE_ONLY branch that runs only in FULL mode;
#   3. try/except covering BOTH exceptions (incl. except Exception);
#   4. `# core-guard: full-mode-only — <proof>` with a non-empty proof.
# Anything else must sit in the shrinking core_guard_exceptions.txt baseline.

_GUARD_ANNOTATION_RE = re.compile(r"#\s*core-guard:\s*full-mode-only\s*(?:—|-|:)?\s*(.*)$")
# Mirrors the root conftest's test-module gate (test_*.py / *_tests.py).
_TEST_MODULE_NAME_RE = re.compile(r"^(test_.*|.*_tests)\.py$")


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _test_true_when_core(node: ast.AST) -> bool | None:
    """Best-effort boolean evaluation of a branch test when core mode is ON.
    None = cannot determine (fail-safe callers treat it as unguarded)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _test_true_when_core(node.operand)
        return None if inner is None else not inner
    if isinstance(node, ast.Name) and node.id == "HUB_CORE_ONLY":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "HUB_CORE_ONLY":
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "is_core_only"
    ):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and any(isinstance(a, ast.Constant) and a.value == "HUB_CORE_ONLY" for a in node.args)
    ):
        # os.environ.get("HUB_CORE_ONLY") — the root conftest's own pattern.
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Compare):
        inner = _test_true_when_core(node.left)
        for op, comp in zip(node.ops, node.comparators, strict=False):
            if isinstance(comp, ast.Constant):
                # Falsy comparators invert the flag; truthy ones affirm it.
                if comp.value in (False, None, 0, "", "0", "false", "False"):
                    if isinstance(op, (ast.Eq, ast.Is)):
                        return None if inner is None else not inner
                    if isinstance(op, (ast.NotEq, ast.IsNot)):
                        return inner
                if comp.value in (True, 1, "1", "true", "True"):
                    if isinstance(op, (ast.Eq, ast.Is)):
                        return inner
                    if isinstance(op, (ast.NotEq, ast.IsNot)):
                        return None if inner is None else not inner
        return None
    if isinstance(node, ast.BoolOp):
        parts = [_test_true_when_core(v) for v in node.values]
        if any(p is None for p in parts):
            return None
        return all(parts) if isinstance(node.op, ast.And) else any(parts)
    return None


def _classify_handlers(try_node: ast.Try) -> tuple[str, bool]:
    """(classification, broad) for the handlers of an enclosing try."""
    if not try_node.handlers:
        return "try-no-except", False
    for handler in try_node.handlers:
        if handler.type is None:
            return "try-covered-BROKEN", True  # bare except
        names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        covered: set[str] = set()
        broad = False
        for n in names:
            name = n.id if isinstance(n, ast.Name) else None
            if name in ("Exception", "BaseException"):
                broad = True
                covered.update({"RuntimeError", "ModuleNotFoundError"})
            elif name == "ImportError":
                # ModuleNotFoundError IS an ImportError — one of the two
                # failure modes is covered by the parent class.
                covered.add("ModuleNotFoundError")
            elif name in ("RuntimeError", "ModuleNotFoundError"):
                covered.add(name)
        if "RuntimeError" in covered and "ModuleNotFoundError" in covered:
            return "try-covered-BROKEN", broad
    return "try-not-covered", False


def classify_import_guard(tree: ast.AST, node: ast.AST, source_lines: list[str]) -> str:
    """Classify a paid-import site (see module docstring)."""
    return classify_import_guard_detail(tree, node, source_lines)[0]


def classify_import_guard_detail(
    tree: ast.AST, node: ast.AST, source_lines: list[str]
) -> tuple[str, bool]:
    """(classification, broad-handler) — broad marks try-covered sites that
    rely on except Exception/bare handlers (the --prefer-explicit target)."""
    parents = _build_parent_map(tree)

    # Walk outward: ANY enclosing Try whose handlers cover both failure
    # modes guards the site (an inner business-logic try must not mask an
    # outer covering one). Every flag-referencing If ancestor must run
    # only in FULL mode.
    saw_try_classification: str | None = None
    decided_branch = False
    branch_ok = True
    child: ast.AST = node
    p = parents.get(node)
    while p is not None:
        if isinstance(p, ast.Try):
            classification, broad = _classify_handlers(p)
            if classification == "try-covered-BROKEN":
                return "try-covered-BROKEN", broad
            if saw_try_classification is None:
                saw_try_classification = classification
        if isinstance(p, ast.If):
            truth = _test_true_when_core(p.test)
            if truth is not None:
                in_body = any(c is child for c in p.body)
                in_orelse = any(c is child for c in p.orelse)
                if in_body or in_orelse:
                    runs_in_core = (not truth) if in_orelse else truth
                    decided_branch = True
                    if runs_in_core is not False:
                        branch_ok = False
        child = p
        p = parents.get(p)

    if decided_branch:
        if branch_ok:
            return "branch-guarded", False
        # A flagged branch runs in CORE mode — no annotation can save the
        # site; fail safe.
        return "unguarded", False

    if saw_try_classification is not None:
        return saw_try_classification, False

    # Annotation fallback: the import line or the line above it.
    for line_no in (node.lineno, node.lineno - 1):
        if 1 <= line_no <= len(source_lines):
            m = _GUARD_ANNOTATION_RE.search(source_lines[line_no - 1])
            if m and m.group(1).strip():
                return "annotated", False
    return "unguarded", False


_GUARDED_CLASSIFICATIONS = {"try-covered-BROKEN", "branch-guarded", "annotated"}


def _publish_excluded(root: Path, relpath: str) -> bool:
    """True when ``relpath`` does not ship in the public tree.

    Mirrors the tree-builder filter (scripts/publish_tree.sh): exclusion
    entries are file paths or trailing-slash dir prefixes; ``!prefix``
    entries re-include paths (file = exact match, dir = startswith).
    Private-only tooling must not be governed by the guard gate — it never
    runs in core or public contexts (313.H.2.3).
    """
    exclude_file = root / "scripts" / "publish_paths_exclude.txt"
    if not exclude_file.exists():
        return False
    entries = [
        line.strip()
        for line in exclude_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    negations = [e[1:] for e in entries if e.startswith("!")]
    plain = [e for e in entries if not e.startswith("!")]
    excluded = (
        any(relpath == e or relpath.startswith(e) for e in plain if e.endswith("/"))
        or relpath in plain
    )
    if excluded and any(relpath == e or relpath.startswith(e) for e in negations):
        return False
    return excluded


def _collect_import_sites(
    root: Path,
    paid_modules: list[str],
    paths: list[str] | None = None,
) -> list[ImportSite]:
    """Collect every paid-import site; scoped to *paths* when given (1.6 hook)."""
    sites: list[ImportSite] = []
    paid_dirs = {str(root / m.replace(".", "/")) for m in paid_modules}

    if paths is not None:
        scan_targets: list[Path] = []
        for rel in paths:
            target = root / rel
            if target.exists() and target.suffix == ".py":
                scan_targets.append(target)
        settings = root / "hub" / "settings.py"
        if settings.exists() and settings not in scan_targets:
            scan_targets.append(settings)
        for path in scan_targets:
            if any(str(path).startswith(pd) for pd in paid_dirs):
                continue
            _scan_python_file(path, root, paid_modules, [], sites)
        return sites

    for scan_dir in DEFAULT_SCAN_DIRS:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(str(path).startswith(pd) for pd in paid_dirs):
                continue
            _scan_python_file(path, root, paid_modules, [], sites)
    # The extra root files participate in the boundary scan, so their
    # import sites must be guard-checked too.
    for extra in DEFAULT_EXTRA_FILES:
        path = root / extra
        if not path.exists():
            continue
        _scan_python_file(path, root, paid_modules, [], sites)
    return sites


def guard_check(
    root: Path,
    allowlist: set[str],
    baseline: set[str],
    prefer_explicit: bool = False,
    paths: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (guard_violations, implicit_broad_sites) for allowlisted imports.

    Test modules (test_*.py / *_tests.py) are exempt — the root conftest's
    collection gate already protects them; conftest.py is NOT exempt.

    ``paths`` scopes the site scan (the 1.6 pre-commit hook passes the
    staged files) — the guard gate stays commit-fast.
    """
    paid, _all = _read_paid_modules(root / "hub" / "apps" / "manifest.py")
    sites = _collect_import_sites(root, [_normalise(m) for m in paid], paths=paths)

    violations: list[str] = []
    implicit: list[str] = []
    for site in sites:
        if site.key() not in allowlist:
            continue
        if _TEST_MODULE_NAME_RE.match(Path(site.relpath).name):
            continue
        if _publish_excluded(root, site.relpath):
            # Private-only tooling never ships — outside the gate's scope.
            continue
        classification, broad = classify_import_guard_detail(
            site.tree, site.node, site.source_lines
        )
        if classification in _GUARDED_CLASSIFICATIONS:
            if prefer_explicit and broad:
                implicit.append(
                    f"{site.key()} — except Exception/bare handler (prefer the explicit pair)"
                )
            continue
        if site.key() in baseline:
            continue
        violations.append(f"{site.key()} — {classification}")
    return violations, implicit


def _load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#"):
            out.add(stripped.split(":", 2)[0] + ":" + stripped.split(":", 2)[1])
    return out


# ---------------------------------------------------------------------------
# Ratchet NET accounting (313-H task 1.2)
#
# Allowlist keys are ``relpath:lineno:reason``. Because ``lineno`` is part of
# the key, ANY edit that shifts lines in an allowlisted file rewrites its keys.
# The original ratchet ("fail if the working set holds a key absent from HEAD")
# read that mechanical churn as growth — Phase 0.1 hit exactly that, with 12
# keys churning on a commit that added no boundary violations.
#
# Identity is the FILE, and the measure is how many audited violations it
# carries. Line shifts inside a file leave the count untouched (churn, free);
# a new violation raises it (growth, blocked).
#
# Why per-file counting rather than global ``len(added) > len(removed)``:
# global accounting nets a brand-new violation in file B against an unrelated
# removal in file A and passes — delete one audited line anywhere, introduce
# one new violation anywhere. Per-file counting has no such offset. The reason
# TEXT is deliberately NOT part of identity: 417 entries spell it with "→" and
# 48 with "->", so keying on it would manufacture churn.
# ---------------------------------------------------------------------------
class AllowlistEntry(NamedTuple):
    relpath: str
    lineno: int
    reason: str


class RatchetReport(NamedTuple):
    # grown  — relpath -> count of NEW audited violations (the failing signal)
    # shrunk — relpath -> count of removed entries (always allowed)
    # moved  — relpath whose count held but whose line numbers shifted (churn)
    grown: dict[str, int]
    shrunk: dict[str, int]
    moved: list[str]

    @property
    def ok(self) -> bool:
        """Clean when nothing grew. Shrink and churn are always allowed."""
        return not self.grown


def parse_allowlist_entries(text: str) -> list[AllowlistEntry]:
    """Parse ``relpath:lineno:reason`` lines; comments and blanks ignored.

    Malformed lines raise instead of being skipped: a silently dropped entry
    would shrink the baseline the ratchet compares against, which is the one
    direction that must never happen by accident.
    """
    entries: dict[tuple[str, int], AllowlistEntry] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(":", 2)
        if len(parts) < 3:
            raise ValueError(f"malformed allowlist line (want relpath:lineno:reason): {stripped!r}")
        relpath, raw_lineno, reason = parts
        try:
            lineno = int(raw_lineno)
        except ValueError as exc:
            raise ValueError(
                f"malformed allowlist line (lineno is not an integer): {stripped!r}"
            ) from exc
        # Same (path, line) twice is one audited site, not two.
        entries.setdefault((relpath, lineno), AllowlistEntry(relpath, lineno, reason))
    return list(entries.values())


def allowlist_ratchet_report(head_text: str, working_text: str) -> RatchetReport:
    """Compare a working allowlist against its HEAD revision, per file."""
    head = parse_allowlist_entries(head_text)
    working = parse_allowlist_entries(working_text)

    head_counts: dict[str, int] = {}
    work_counts: dict[str, int] = {}
    head_lines: dict[str, set[int]] = {}
    work_lines: dict[str, set[int]] = {}
    for entry in head:
        head_counts[entry.relpath] = head_counts.get(entry.relpath, 0) + 1
        head_lines.setdefault(entry.relpath, set()).add(entry.lineno)
    for entry in working:
        work_counts[entry.relpath] = work_counts.get(entry.relpath, 0) + 1
        work_lines.setdefault(entry.relpath, set()).add(entry.lineno)

    grown: dict[str, int] = {}
    shrunk: dict[str, int] = {}
    moved: list[str] = []
    for relpath in set(head_counts) | set(work_counts):
        delta = work_counts.get(relpath, 0) - head_counts.get(relpath, 0)
        if delta > 0:
            grown[relpath] = delta
        elif delta < 0:
            shrunk[relpath] = -delta
        elif head_lines.get(relpath) != work_lines.get(relpath):
            moved.append(relpath)
    return RatchetReport(grown=grown, shrunk=shrunk, moved=sorted(moved))


def run_ratchet_gate(
    root: Path,
    tracked_file: Path,
    *,
    prefix: str,
    subject: str,
    item: str,
    hint: str = "",
    announce_clean: bool = True,
) -> int:
    """NET-ratchet *tracked_file* against its HEAD revision. 0 = clean, 1 = grew.

    Shared by the allowlist and the guard baseline so the two can never drift
    apart — they previously had different accounting, and the weaker of the two
    silently permitted a laundering swap.
    """
    head_text = _head_revision_text(root, tracked_file)
    if head_text is None:
        # No HEAD revision (new file, or outside the repo): nothing to ratchet.
        return 0

    report = allowlist_ratchet_report(head_text, tracked_file.read_text())
    if report.ok:
        if announce_clean:
            summary = f"{sum(report.shrunk.values())} removed"
            if report.moved:
                summary += f", {len(report.moved)} file(s) line-shift churn only"
            print(f"{prefix}: {subject} ratchet clean vs HEAD ({summary})")
        return 0

    total = sum(report.grown.values())
    print(f"{prefix}: {subject} ratchet violation — {total} NET new {item} vs HEAD:")
    for relpath, count in sorted(report.grown.items()):
        print(f"  + {relpath}: {count} new")
    if report.moved:
        print(
            f"  (ignored: {len(report.moved)} file(s) with line-shift churn only — "
            "moving an entry is free)"
        )
    if hint:
        print(hint)
    return 1


def _head_revision_text(root: Path, tracked_file: Path) -> str | None:
    """``git show HEAD:<path>`` for *tracked_file*, resolved inside *root*.

    ``cwd=root`` matters: without it git resolves against the CALLER's working
    directory, so a ``--root`` pointed at another tree silently compares
    against the wrong repository's baseline.
    """
    try:
        relative = tracked_file.relative_to(root)
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result.stdout if result.returncode == 0 else None


def _collect_scoped(
    paths: list[str],
    root: Path,
    paid_dirs: set[str],
    paid_modules: list[str],
    violations: list[Violation],
) -> None:
    """Scan only the pre-commit-staged files, plus hub/settings.py always.

    MIDDLEWARE / DATABASE_ROUTERS entries bypass the import scanner by
    design and live only in settings.py, so scoping it out would reopen the
    string-literal leak class on every settings edit.
    """
    scan_targets: list[Path] = []
    for rel in paths:
        target = root / rel
        if target.exists() and target.suffix == ".py":
            scan_targets.append(target)
    settings = root / "hub" / "settings.py"
    if settings.exists() and settings not in scan_targets:
        scan_targets.append(settings)
    for path in scan_targets:
        if any(str(path).startswith(pd) for pd in paid_dirs):
            continue
        _scan_python_file(path, root, paid_modules, violations)
        if str(path.relative_to(root)) == "hub/settings.py":
            _scan_settings_strings(path, root, paid_modules, violations)


def _collect_full_tree(
    root: Path,
    paid_dirs: set[str],
    paid_modules: list[str],
    violations: list[Violation],
) -> None:
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


def collect_violations(
    root: Path,
    paid_modules: list[str],
    paths: list[str] | None = None,
) -> list[Violation]:
    """Collect boundary violations; scoped to *paths* when given (1.6 hook).

    ``paths`` are repo-relative file paths as passed by pre-commit. When
    scoped, ``hub/settings.py`` is ALWAYS scanned too (see ``_collect_scoped``).
    """
    violations: list[Violation] = []
    paid_dirs = {str(root / m.replace(".", "/")) for m in paid_modules}

    if paths is not None:
        _collect_scoped(paths, root, paid_dirs, paid_modules, violations)
    else:
        _collect_full_tree(root, paid_dirs, paid_modules, violations)

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
    parser.add_argument(
        "--paths",
        nargs="*",
        metavar="FILE",
        help="scan ONLY these repo-relative files (+ hub/settings.py) — the "
        "pre-commit fast gate (1.6) passes the staged filenames here",
    )
    parser.add_argument("--list", action="store_true", help="print violations instead of failing")
    parser.add_argument(
        "--public",
        action="store_true",
        help="public-tree mode (W7.1 R2-M1, the DECIDED blocking option): "
        "plain gate + guard gate — every allowlisted non-test paid "
        "import in public-shipping core files must be guarded, or the "
        "public tree crashes at module load (the paid module is "
        "absent).  Test modules stay exempt — the shipped root "
        "conftest's collection gate ignores paid-importing test "
        "modules in core mode.  Allowlist entries for files that do "
        "not ship are inert — the allowlist travels synced.",
    )
    parser.add_argument(
        "--check-allowlist-growth",
        action="store_true",
        help="fail when the allowlist grows beyond git HEAD (ratchet)",
    )
    parser.add_argument(
        "--check-guards",
        action="store_true",
        help="fail when an allowlisted import lacks a guard (313.H.1)",
    )
    parser.add_argument(
        "--guard-exceptions",
        type=Path,
        default=Path(__file__).resolve().parent / "core_guard_exceptions.txt",
        help="shrinking baseline of unguarded allowlisted sites (313.H.1)",
    )
    parser.add_argument(
        "--check-guard-growth",
        action="store_true",
        help="fail when the guard exceptions baseline grows NET beyond git HEAD",
    )
    parser.add_argument(
        "--prefer-explicit",
        action="store_true",
        help="report except Exception/bare-handler sites (non-blocking tightening mode)",
    )
    args = parser.parse_args(argv)

    paid, _all = _read_paid_modules(args.root / "hub" / "apps" / "manifest.py")
    violations = collect_violations(args.root, [_normalise(m) for m in paid], paths=args.paths)
    allowlist = _load_allowlist(args.allowlist)
    unallowed = [v for v in violations if v.key() not in allowlist]

    if args.list:
        for v in violations:
            print(str(v))
        return 0

    rc = 0

    if args.check_allowlist_growth and args.allowlist.exists():
        rc |= run_ratchet_gate(
            args.root,
            args.allowlist,
            prefix="GATE-29",
            subject="allowlist",
            item="audited violation(s)",
            hint=(
                "Fix the import direction (registries/hooks/event bus). A removal "
                "elsewhere does NOT offset a new violation here — the ratchet is "
                "accounted per file."
            ),
        )

    if args.check_guards:
        baseline = _load_allowlist(args.guard_exceptions)
        guard_violations, implicit_sites = guard_check(
            args.root,
            allowlist,
            baseline,
            prefer_explicit=args.prefer_explicit,
            paths=args.paths,
        )
        if args.prefer_explicit:
            print(
                f"GUARD-313.H: {len(implicit_sites)} broad-handler site(s) (prefer the explicit pair):"
            )
            for entry in implicit_sites:
                print(f"  ~ {entry}")
        if guard_violations:
            print(f"GUARD-313.H: {len(guard_violations)} unguarded allowlisted import(s):")
            for entry in guard_violations:
                print(f"  ! {entry}")
            print("Guard with try/except (RuntimeError, ModuleNotFoundError), an")
            print("is_core_only() branch, a '# core-guard: full-mode-only — <proof>'")
            print("annotation, or a baseline entry — the baseline never grows (net).")
            rc = 1
        else:
            print(f"GUARD-313.H: all allowlisted imports are guarded ({len(baseline)} baselined)")
        if args.check_guard_growth and args.guard_exceptions.exists():
            # Same NET accounting as the allowlist ratchet (313-H task 1.2).
            # This previously compared len(added) > len(removed), which nets a
            # brand-new unguarded site against an unrelated removal elsewhere
            # and passes — the same laundering hole, one file over.
            rc |= run_ratchet_gate(
                args.root,
                args.guard_exceptions,
                prefix="GUARD-313.H",
                subject="baseline",
                item="unguarded site(s)",
                announce_clean=False,  # the guard gate itself already reports status
            )

    if args.public:
        # W7.1 (R2-M1) — the DECIDED public-tree mode: blocking, with the
        # synced allowlist (the same file ships).  The public gate is the
        # plain gate PLUS the guard gate: every allowlisted non-test site
        # in public-shipping files must be guarded (try-covered /
        # branch-guarded / annotated) or the public tree crashes at
        # module load (the paid module is absent).  Test modules stay
        # exempt by design — the shipped root conftest's collection gate
        # ignores paid-importing test modules in core mode (the same
        # protection the private core CI relies on).
        baseline = _load_allowlist(args.guard_exceptions)
        guard_violations, _implicit = guard_check(
            args.root,
            allowlist,
            baseline,
            prefer_explicit=args.prefer_explicit,
            paths=args.paths,
        )
        if guard_violations:
            print(
                f"GATE-29 --public: {len(guard_violations)} unguarded "
                "allowlisted import(s) in public-shipping core code "
                "(the paid module is absent in the public tree — the "
                "import would crash at module load):"
            )
            for entry in guard_violations:
                print(f"  ! {entry}")
            print(
                "Guard with try/except (RuntimeError, ModuleNotFoundError), "
                "an is_core_only() branch, or a '# core-guard: full-mode-only' "
                "annotation."
            )
            return 1

    if unallowed:
        print(f"GATE-29: {len(unallowed)} boundary violation(s) in core code:")
        for v in sorted(unallowed, key=str):
            print(f"  {v}")
        print("Fix the import direction (registries/hooks/event bus) or add an")
        print("audited allowlist entry (path:line:reason) — the allowlist never grows.")
        return 1

    if rc:
        return rc

    print(
        "GATE-29: core boundary clean "
        f"({len(violations)} violation(s), {len(violations) - len(unallowed)} allowlisted)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
