#!/usr/bin/env python3
"""
281.A.1.3 — Dead Code Audit & Removal.  GATE-57 (oss-release-remediation W12.2).

Scans the codebase for:
  - ``_services_legacy.py`` / ``_legacy.py`` / ``_deprecated.py`` files
    (legacy service stubs — zero-tolerance class under the gate)
  - modules with no incoming reference (orphans) — imports are resolved
    including RELATIVE imports (``from .x import``) and dotted-path string
    wiring (settings ``MIDDLEWARE``, URL ``include(...)``, ``import_module``)
  - commented-out code blocks (``# ...`` spanning >3 consecutive lines)
  - ``TODO remove`` / ``FIXME remove`` markers
  - feature flags that are always-true or always-false

Audit modes (report-only):
  python scripts/audit_dead_code.py              # audit only
  python scripts/audit_dead_code.py --json       # JSON output

Gate modes (blocking):
  python scripts/audit_dead_code.py --check            # GATE-57 main gate
  python scripts/audit_dead_code.py --check-growth     # allowlist ratchet vs git HEAD
  python scripts/audit_dead_code.py --update           # record current orphans as baseline
  --root PATH       scan a different tree (planted pins / built public tree)
  --baseline PATH   allowlist location (default <root>/scripts/dead_code_allowlist.json)

GATE-57 contract (W12.2):
  * LEGACY CLASS (zero-tolerance): no file under ``hub/`` may be named
    ``_services_legacy.py`` / ``_legacy.py`` / ``_deprecated.py`` — the
    two ~200KB legacy pairs were deleted; a reintroduction fails the gate.
  * ORPHANS: every module with no static reference must be deleted or
    allowlisted WITH a reason citing its wiring site. Untriaged orphans
    fail the gate.
  * ALLOWLIST HONESTY: dead anchors (file gone), stale entries (module is
    referenced again — no longer an orphan), and empty/TODO reasons all fail.
  * RATCHET: ``--check-growth`` compares the allowlist against ``git HEAD``
    per module — it only ever shrinks.
"""

import argparse
import ast
import bisect
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LEGACY_FILE_NAMES: tuple[str, ...] = (
    "_services_legacy.py",
    "_legacy.py",
    "_deprecated.py",
)

# Files loaded by Django's app registry / celery / pytest conventions, not
# by explicit import statements — never dead code by import-orphan standards.
# ``models`` is imported by AppConfig.import_models for every INSTALLED app
# (that is how ``hub/apps/core/models.py`` registers with migrations without
# any code importing it); ``manage`` is the Django entry-point script.
DJANGO_AUTO_STEMS = {
    "apps",
    "admin",
    "urls",
    "signals",
    "receivers",
    "tasks",
    "forms",
    "__init__",
    "conftest",
    "settings",
    "factories",
    "models",
    "manage",
}

# Directory parts excluded from CANDIDATE collection. Files inside may
# still act as importers/wiring sources — tests legitimately import prod
# modules, and a test-only reference is a reference.
_CANDIDATE_SKIP_PARTS = {
    "tests",
    "migrations",
    "management",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    ".tox",
    "test-results",
}

# Directories never scanned AT ALL (importers, strings, or candidates):
# VCS, archived copies, and GENERATED ARTIFACTS (docs site builds, coverage
# reports, venvs, backups) — a stale generated snapshot is not a live
# reference, and skipping them keeps the scan fast (the first cut scanned
# 9,085 files / 96MB and took 130s). NOTE: tests/ and migrations/ are NOT
# here — they are scanned as importers and string sources.
_ARTIFACT_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    ".tox",
    "test-results",
    "docs",
    "openspec",
    "archive",
    "site",
    "coverage",
    "backups",
    "staticfiles",
    "storybook-static",
    "htmlcov",
    "build",
    "dist",
}

_WIRING_EXTS = {".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".sh"}

# Root-level GENERATED reports that enumerate hub module paths — a stale
# generated snapshot is not a live reference (same rule as the artifact
# dirs above; these live at repo root, not in a skippable dir).
_GENERATED_FILENAMES = {".bandit-ratchet-output.json", "reverse_lookup_analysis.json"}

# Only hub-module dotpaths can wire a candidate — the narrow pattern keeps
# the config scan linear in repo size instead of in match count. The groups
# are NON-capturing: re.findall returns group captures when capturing
# groups exist, so a capturing form silently yielded '' instead of the
# full match (found 2026-10-15 — the config-scan channel was blind).
_HUB_DOTTED_RE = re.compile(
    r"\bhub\.[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\b"
)

# Placeholder stamped into new allowlist entries by --update; the gate
# rejects it so an untriaged orphan can never ship with a hollow reason.
_TODO_REASON = "TODO: reason required — cite the wiring site"

# Feature flags confirmed as always-true (GA, unconditionally enabled)
ALWAYS_TRUE_FLAGS: list[str] = [
    # Add flags confirmed as permanently enabled after verification
]


def _repo_py_files(root: Path) -> list[Path]:
    """Every .py file in the repo — candidates live under hub/, but
    IMPORTERS and wiring strings live everywhere (root-level tests/,
    scripts/, cli/, sdk/). The pre-fix scan of hub/ alone made any
    module referenced only from tests/ or scripts/ look dead."""
    results = []
    for path in root.rglob("*.py"):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if any(_is_artifact_part(p) for p in parts):
            continue
        results.append(path)
    return sorted(results)


def _hub_py_files(root: Path) -> list[Path]:
    """Candidates + hub-local importers: every .py under root/hub."""
    hub = root / "hub"
    if not hub.is_dir():
        return []
    return sorted(
        p
        for p in hub.rglob("*.py")
        if p.is_file()
        and not any(_is_artifact_part(part) for part in p.relative_to(root).parts)
    )


def _rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _dotpath(rel: str) -> str:
    return rel[:-3].replace("/", ".") if rel.endswith(".py") else rel


def _resolve_imports_from(file_dotpath: str, node: ast.ImportFrom) -> list[str]:
    """Resolve every module an ImportFrom references, absolute or relative.

    level=1 → the file's own package; level=2 → its parent; and so on.
    ``from . import x`` sets module=None with the submodules in the
    ALIASES — Python's AST, not the ``module`` field, carries them.
    ``from pkg import a, b`` carries submodules a/b in the aliases too
    (``hub/apps/billing/urls.py`` imports its views that way) — both the
    package and every ``module.alias`` path are recorded; a nonexistent
    ``module.alias`` path (an imported MEMBER, not a submodule) matches no
    candidate and is harmless.
    """
    if node.level == 0:
        resolved: list[str] = []
        if node.module:
            resolved.append(node.module)
            resolved.extend(f"{node.module}.{alias.name}" for alias in node.names)
        return resolved
    package_parts = file_dotpath.split(".")
    if node.level > len(package_parts):
        return []
    base = ".".join(package_parts[: len(package_parts) - node.level])
    if node.module:
        target = f"{base}.{node.module}" if base else node.module
        return [target, *[f"{target}.{alias.name}" for alias in node.names]]
    if not base:
        return []
    return [f"{base}.{alias.name}" for alias in node.names]


def _collect_config_strings(root: Path) -> set[str]:
    """Hub-dotpath strings from NON-.py config files (compose/helm/k8s/
    terraform/dbt manifests, JSON registries). .py files are covered by
    the single-pass import+string scan; generated artifacts (site/,
    coverage/, venvs) are skipped — a stale generated snapshot is not a
    live reference. The allowlist file itself is excluded — its keys
    would wire every allowlisted module by construction."""
    strings: set[str] = set()
    for path in _iter_wiring_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        strings |= set(_HUB_DOTTED_RE.findall(text))
    return strings


def _is_artifact_part(part: str) -> bool:
    return (
        part in _ARTIFACT_PARTS or part.startswith("venv-") or "site-packages" in part
    )


def _iter_wiring_files(root: Path) -> list[Path]:
    results: list[Path] = []
    baseline = _resolve_baseline(root)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _WIRING_EXTS:
            continue
        if any(_is_artifact_part(p) for p in path.relative_to(root).parts):
            continue
        if path == baseline or path.name in _GENERATED_FILENAMES:
            continue
        results.append(path)
    return sorted(results)


def _candidate_relpaths(root: Path) -> list[str]:
    """Candidate modules — every .py under hub/ except Django auto-discovery."""
    candidates = []
    for path in _hub_py_files(root):
        rel = _rel(root, path)
        parts = rel.split("/")
        if any(part in _CANDIDATE_SKIP_PARTS for part in parts):
            continue
        if Path(rel).stem in DJANGO_AUTO_STEMS:
            continue
        candidates.append(rel)
    return candidates


def _collect_static_references(root: Path) -> tuple[set[str], set[str]]:
    """One pass over every repo .py file → (imported dotpaths, string
    literals).

    Importers are repo-wide (root-level tests/, scripts/, cli/ import
    hub modules too), while CANDIDATES stay hub-only. Imports are
    resolved absolute AND relative — the pre-fix finder recorded only
    level==0 imports, which is how ``contracts/views.py``'s nine
    ``from .views_x`` mixin imports and ``jobs/tasks.py``'s task imports
    became orphans. String literals are the dotted-string wiring channel
    (settings MIDDLEWARE, URL ``include()``, ``import_module()``).

    Imports and strings are collected in ONE ast.walk per file — a
    second walk doubled the cost of the repo-wide scan.
    """
    referenced: set[str] = set()
    py_strings: set[str] = set()
    for path in _repo_py_files(root):
        rel = _rel(root, path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        file_dotpath = _dotpath(rel)
        docstring = ast.get_docstring(tree, clean=False)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                referenced.update(_resolve_imports_from(file_dotpath, node))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    referenced.add(alias.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if docstring is not None and text == docstring:
                    continue
                py_strings.add(text)
            elif isinstance(node, ast.JoinedStr):
                for part in node.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        py_strings.add(part.value)
    return referenced, py_strings


def find_orphaned_modules(root: Path) -> list[str]:
    """Modules with no incoming reference (import or dotted-string wiring).

    Returns repo-relative paths, sorted, UNCAPPED — the pre-fix ``[:50]``
    cap is what produced the "50 orphan modules" ticket number; the real
    pre-triage inventory was 125.
    """
    referenced, py_strings = _collect_static_references(root)
    wired = _collect_config_strings(root) | py_strings
    ordered = sorted(wired)

    def is_wired(dotpath: str) -> bool:
        idx = bisect.bisect_left(ordered, dotpath)
        return (idx < len(ordered) and ordered[idx] == dotpath) or (
            idx < len(ordered) and ordered[idx].startswith(dotpath + ".")
        )

    orphans = []
    for rel in _candidate_relpaths(root):
        dotpath = _dotpath(rel)
        if dotpath in referenced or is_wired(dotpath):
            continue
        orphans.append(rel)
    return orphans


def find_legacy_files(root: Path) -> list[str]:
    """Files matching the legacy-class naming patterns under hub/."""
    hub = root / "hub"
    if not hub.is_dir():
        return []
    found = []
    for name in LEGACY_FILE_NAMES:
        for path in hub.rglob(name):
            found.append(_rel(root, path))
    return sorted(found)


def find_commented_out_blocks(root: Path) -> list[dict]:
    """Find commented-out Python code blocks (≥3 consecutive comment-only lines)."""
    blocks = []
    for py_file in _hub_py_files(root):
        if "__pycache__" in str(py_file) or "migrations" in str(py_file):
            continue
        try:
            lines = py_file.read_text().split("\n")
        except (OSError, ValueError):
            continue

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("#") and not stripped.startswith("##"):
                # Check if this is a comment-only line (not a docstring/inline comment)
                # Skip license headers and section dividers
                if stripped.startswith(("# Copyright", "# ~")):
                    i += 1
                    continue

                block_start = i + 1  # 1-indexed line number
                while i < len(lines) and (
                    lines[i].strip().startswith("#")
                    and not lines[i].strip().startswith("##")
                ):
                    i += 1
                block_len = i - block_start + 1
                if block_len >= 3:
                    blocks.append(
                        {
                            "file": _rel(root, py_file),
                            "line": block_start,
                            "lines": block_len,
                            "preview": lines[block_start - 1].strip()[:80],
                        }
                    )
            else:
                i += 1

    return blocks


def find_always_true_flags(root: Path) -> list[dict]:
    """Find feature flag checks that are always true."""
    results = []
    flag_pattern = re.compile(
        r'feature_flag.*\.(is_enabled|get)\s*\(\s*["\']([\w.]+)["\']',
    )

    for py_file in _hub_py_files(root):
        if "__pycache__" in str(py_file) or "test" in str(py_file):
            continue
        try:
            content = py_file.read_text()
        except (OSError, ValueError):
            continue

        for m in flag_pattern.finditer(content):
            flag_name = m.group(2)
            if flag_name in ALWAYS_TRUE_FLAGS:
                results.append(
                    {
                        "file": _rel(root, py_file),
                        "flag": flag_name,
                        "line": content[: m.start()].count("\n") + 1,
                    }
                )

    return results


def audit(root: Path | None = None) -> dict:
    """Run full dead code audit."""
    root = root or PROJECT_ROOT
    return {
        "legacy_files": find_legacy_files(root),
        "orphaned_modules": find_orphaned_modules(root),
        "commented_out_blocks": find_commented_out_blocks(root),
        "always_true_flags": find_always_true_flags(root),
    }


def print_report(results: dict) -> None:
    """Print human-readable dead code audit."""
    print("Dead Code Audit (281.A.1.3 / GATE-57 W12.2)\n")

    lf = results["legacy_files"]
    print(f"Legacy-class files: {len(lf)}")
    for f in lf:
        size = (PROJECT_ROOT / f).stat().st_size if (PROJECT_ROOT / f).exists() else 0
        print(f"  {f} ({size:,} bytes)")

    orphans = results["orphaned_modules"]
    print(f"\nOrphaned modules (no incoming reference): {len(orphans)}")
    for o in orphans:
        print(f"  {o}")

    blocks = results["commented_out_blocks"]
    print(f"\nCommented-out code blocks (≥3 lines): {len(blocks)}")
    for b in blocks[:10]:
        print(f"  {b['file']}:{b['line']} ({b['lines']} lines) — {b['preview']}")

    flags = results["always_true_flags"]
    print(f"\nAlways-true feature flag branches: {len(flags)}")
    for f in flags:
        print(f"  {f['file']}:{f['line']} — flag={f['flag']}")


# ── GATE-57: blocking check + shrink-only allowlist ratchet ────────────────


def _resolve_baseline(root: Path) -> Path:
    return root / "scripts" / "dead_code_allowlist.json"


def _load_allowlist(baseline: Path) -> dict[str, str]:
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise TypeError(f"{baseline}: expected an 'entries' object")
    for key, reason in entries.items():
        if not isinstance(key, str) or not isinstance(reason, str):
            raise TypeError(f"{baseline}: entries must map str path → str reason")
    return entries


def check_gate(root: Path, baseline: Path) -> int:
    """GATE-57 main gate. 0 = clean, 1 = violation."""
    if not baseline.is_file():
        print(
            f"dead-code gate: allowlist missing at {_rel(root, baseline)} — "
            "run `python scripts/audit_dead_code.py --update` to record the "
            "current orphan inventory, then give every entry a reason"
        )
        return 1

    try:
        entries = _load_allowlist(baseline)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"dead-code gate: allowlist unreadable — {exc}")
        return 1

    violations: list[str] = []

    legacy = find_legacy_files(root)
    for path in legacy:
        violations.append(
            f"legacy-class file {path} — W12.2 deleted this class; git history "
            "preserves it. Delete the file (or rename out of the legacy class)."
        )

    orphans = set(find_orphaned_modules(root))
    for path in sorted(orphans - set(entries)):
        violations.append(
            f"untriaged orphan {path} — delete it, or wire it, or record it in "
            "scripts/dead_code_allowlist.json WITH a reason citing its wiring site"
        )

    for path, reason in sorted(entries.items()):
        if not (root / path).is_file():
            violations.append(
                f"dead allowlist anchor {path} — the file no longer exists; "
                "delete the entry (the shrink path)"
            )
        elif path not in orphans:
            violations.append(
                f"stale allowlist entry {path} — the module is no longer an "
                "orphan (it has an incoming reference); delete the entry"
            )
        elif not reason or reason.strip().startswith("TODO"):
            violations.append(
                f"reasonless allowlist entry {path} — cite the wiring site "
                "that keeps the module alive"
            )

    if violations:
        print(f"dead-code gate: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"dead-code gate clean: 0 legacy-class files, {len(orphans)} orphan "
        f"module(s), {len(entries)} allowlisted with reasons"
    )
    return 0


def _head_revision_text(root: Path, tracked_file: Path) -> str | None:
    """``git show HEAD:<path>`` for *tracked_file*, resolved inside *root*.

    ``cwd=root`` matters: without it git resolves against the CALLER's
    working directory (same trap the boundary checker's ratchet hit).
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


def check_growth(root: Path, baseline: Path) -> int:
    """Shrink-only ratchet: the allowlist must not grow vs ``git HEAD``.

    Per-module accounting (mirrors GATE-29's allowlist ratchet): added keys
    fail, removed keys shrink, HEAD-missing (uncommitted new file) is
    nothing-to-ratchet.
    """
    head_text = _head_revision_text(root, baseline)
    if head_text is None:
        print(
            "dead-code allowlist ratchet: no HEAD revision — nothing to ratchet "
            "(the baseline commits with this change; CI enforces from there)"
        )
        return 0
    try:
        head = json.loads(head_text)["entries"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"dead-code allowlist ratchet: HEAD revision unreadable — {exc}")
        return 1
    working = _load_allowlist(baseline)

    added = sorted(set(working) - set(head))
    removed = sorted(set(head) - set(working))
    if added:
        print(
            f"dead-code allowlist ratchet violation — {len(added)} new "
            "entry(ies) vs HEAD (shrink-only):"
        )
        for path in added:
            print(f"  + {path}")
        print(
            "  (delete the dead module, or justify the new entry by removing "
            "an equal-or-greater number of entries)"
        )
        return 1
    print(f"dead-code allowlist ratchet clean vs HEAD " f"({len(removed)} removed)")
    return 0


def update_allowlist(root: Path, baseline: Path) -> int:
    """Record the current orphan inventory as the allowlist.

    Preserves reasons for surviving orphans, stamps the TODO placeholder
    for new ones (the gate rejects it until a human fills it in), and drops
    dead anchors + stale entries — printing the delta (the ratchet record).
    """
    try:
        old = _load_allowlist(baseline) if baseline.is_file() else {}
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"dead-code allowlist update: unreadable — {exc}")
        return 1

    orphans = set(find_orphaned_modules(root))
    kept = {p: r for p, r in old.items() if p in orphans and (root / p).is_file()}
    added = dict.fromkeys(sorted(orphans - set(kept)), _TODO_REASON)
    dropped_dead = sorted(p for p in old if not (root / p).is_file())
    dropped_stale = sorted(p for p in old if (root / p).is_file() and p not in orphans)

    entries = dict(sorted({**kept, **added}.items()))
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(json.dumps({"entries": entries}, indent=2) + "\n")

    print(
        f"dead-code allowlist updated: added {len(added)}, kept {len(kept)}, "
        f"dropped {len(dropped_dead) + len(dropped_stale)} "
        f"(dead {len(dropped_dead)}, stale {len(dropped_stale)})"
    )
    for path in sorted(added):
        print(f"  + {path}  ({_TODO_REASON})")
    for path in dropped_dead:
        print(f"  - {path}  (file deleted)")
    for path in dropped_stale:
        print(f"  - {path}  (now referenced — no longer an orphan)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dead code audit + GATE-57 gate")
    parser.add_argument("--check", action="store_true", help="GATE-57 blocking gate")
    parser.add_argument(
        "--check-growth",
        action="store_true",
        help="fail when the allowlist grows beyond git HEAD (shrink-only ratchet)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="record the current orphan inventory as the allowlist baseline",
    )
    parser.add_argument("--json", action="store_true", help="audit as JSON")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="tree to scan")
    parser.add_argument("--baseline", type=Path, help="allowlist path override")
    args = parser.parse_args()

    root = args.root
    baseline = args.baseline or _resolve_baseline(root)

    if args.check:
        return check_gate(root, baseline)
    if args.check_growth:
        return check_growth(root, baseline)
    if args.update:
        return update_allowlist(root, baseline)

    results = audit(root)
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
