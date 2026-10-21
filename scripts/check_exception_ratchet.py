#!/usr/bin/env python3
"""
GATE-58 — Exception-handling ratchet (oss-release-remediation W12.3).

Three instruments:

1. BROAD-EXCEPT RATCHET — every ``except Exception`` / ``except
   BaseException`` handler (sole or inside a catch tuple) in NON-TEST
   hub code must be either:
     * in the committed debt baseline (``scripts/exception_baseline.json``,
       per-file site line numbers), or
     * allowlisted as a boundary catch (``scripts/exception_allowlist.json``,
       per-file accepted count + a reason citing the boundary — telemetry
       emitters, audit emitters, degradation fallbacks).
   The baseline and the allowlist only ever shrink vs ``git HEAD``.

2. BARE-EXCEPT ZERO-TOLERANCE — ``except:`` (no type at all) fails
   outright, unratcheted. The register's "2 bare except" sites were
   already fixed; a reintroduction is a regression, not debt.

3. ``# noqa`` RATCHET — every ``# noqa`` comment in repo .py files is
   in ``scripts/noqa_baseline.json`` (per-file counts). A new one must
   be reviewed: the gate names the file, and growth vs ``git HEAD``
   fails, so recording a new noqa is a deliberate, reviewed commit.

Accounting mirrors GATE-29's allowlist ratchet: per-file counts with
line-churn tolerance — a site moving lines within a file whose count is
unchanged is churn, not growth (the same documented limitation: swapping
one site for another in the same file reads as churn; the review happens
at ``--update`` time). ``ruff`` BLE001 (Phase T.1) is the global
backstop for the same debt under GATE-35; this gate adds per-file
ownership, the boundary-catch allowlist, and the noqa instrument.

Usage:
  python scripts/check_exception_ratchet.py --check
  python scripts/check_exception_ratchet.py --check-growth
  python scripts/check_exception_ratchet.py --check-noqa
  python scripts/check_exception_ratchet.py --check-noqa-growth
  python scripts/check_exception_ratchet.py --update
  --root PATH       scan a different tree (planted pins / built tree)
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_EXC_BASELINE = PROJECT_ROOT / "scripts" / "exception_baseline.json"
DEFAULT_EXC_ALLOWLIST = PROJECT_ROOT / "scripts" / "exception_allowlist.json"
DEFAULT_NOQA_BASELINE = PROJECT_ROOT / "scripts" / "noqa_baseline.json"

# A catch counts as a site when its type set contains one of these.
_BLIND_TYPES = ("Exception", "BaseException")

# Directories never scanned (artifacts + the noqa scan's node_modules).
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

_NOQA_RE = re.compile(r"#\s*noqa\b")


def _is_artifact_part(part: str) -> bool:
    return (
        part in _ARTIFACT_PARTS or part.startswith("venv-") or "site-packages" in part
    )


def _is_non_test_module(rel: str) -> bool:
    """Non-test scope for the exception instrument: hub code minus test
    trees, migrations, conftest files, and the testing support apps
    (hub/testing/, hub/apps/testing/) — those are test infrastructure,
    not production runtime."""
    parts = rel.split("/")
    if "tests" in parts or "migrations" in parts or "testing" in parts:
        return False
    if rel.startswith("hub/conftest") or "/conftest" in rel:
        return False
    name = parts[-1]
    return not (name.startswith("test_") or name.endswith("_test.py"))


def _catch_type_names(node: ast.ExceptHandler) -> list[str]:
    if node.type is None:
        return []
    if isinstance(node.type, ast.Name):
        return [node.type.id]
    if isinstance(node.type, ast.Tuple):
        return [elt.id for elt in node.type.elts if isinstance(elt, ast.Name)]
    return []


def find_exception_sites(
    root: Path,
) -> tuple[dict[str, list[int]], list[tuple[str, int]]]:
    """(broad-except sites per file, bare-except sites) in non-test hub code."""
    broad: dict[str, list[int]] = {}
    bare: list[tuple[str, int]] = []
    hub = root / "hub"
    if not hub.is_dir():
        return broad, bare
    for path in sorted(hub.rglob("*.py")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if any(_is_artifact_part(p) for p in rel.split("/")):
            continue
        if not _is_non_test_module(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                bare.append((rel, node.lineno))
                continue
            if any(name in _BLIND_TYPES for name in _catch_type_names(node)):
                broad.setdefault(rel, []).append(node.lineno)
    return broad, bare


def find_noqa_sites(root: Path) -> dict[str, int]:
    """Per-file ``# noqa`` counts across every repo .py file (the register's
    "341 noqa comments" counted the whole tree, tests included)."""
    counts: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if any(_is_artifact_part(p) for p in rel.split("/")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        n = len(_NOQA_RE.findall(text))
        if n:
            counts[rel] = n
    return counts


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("files"), dict):
        raise TypeError(f"{path}: expected a 'files' object")
    return payload["files"]


def _head_revision_text(root: Path, tracked_file: Path) -> str | None:
    """``git show HEAD:<path>`` resolved inside *root* (cwd=root matters —
    the same trap GATE-29's ratchet hit)."""
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


def _per_file_ratchet(
    root: Path,
    tracked_file: Path,
    subject: str,
) -> int:
    """Shrink-only per-file ratchet of *tracked_file* vs git HEAD.

    Counts are per file; a removed file or a shrunk count passes, any
    grown or NEW file fails. No HEAD revision (uncommitted new baseline)
    is nothing-to-ratchet.
    """
    head_text = _head_revision_text(root, tracked_file)
    if head_text is None:
        print(
            f"{subject}: no HEAD revision — nothing to ratchet "
            "(the baseline commits with this change; CI enforces from there)"
        )
        return 0
    try:
        head = json.loads(head_text)["files"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"{subject}: HEAD revision unreadable — {exc}")
        return 1
    working = _load_json(tracked_file)

    def entry_count(entry) -> int:
        # Exception baselines hold site-line LISTS; the allowlist holds
        # {allowed, reason} DICTS; the noqa baseline holds plain INTS —
        # one counting rule for all three shapes.
        if isinstance(entry, dict):
            return int(entry.get("allowed", 0))
        if isinstance(entry, list):
            return len(entry)
        return int(entry)

    grown = []
    for path in sorted(set(working) | set(head)):
        delta = entry_count(working.get(path, [])) - entry_count(head.get(path, []))
        if delta > 0:
            grown.append((path, delta))
    if grown:
        print(f"{subject} ratchet violation — growth vs HEAD (shrink-only):")
        for path, delta in grown:
            print(f"  + {path}: {delta} new")
        print(
            "  (fix the new site instead, or justify the swap by removing "
            "an equal-or-greater number of entries)"
        )
        return 1
    removed = sum(
        1
        for path in head
        if entry_count(working.get(path, [])) < entry_count(head[path])
    )
    print(f"{subject} ratchet clean vs HEAD ({removed} file(s) shrank)")
    return 0


# ── Exception instrument ────────────────────────────────────────────────────


def check_exceptions(root: Path, baseline: Path, allowlist: Path) -> int:
    """Main exception gate: inventory consistency + bare-except
    zero-tolerance. 0 = clean, 1 = violation."""
    if not baseline.is_file() or not allowlist.is_file():
        print(
            "exception ratchet: baseline or allowlist missing — run "
            "`python scripts/check_exception_ratchet.py --update` to record "
            "the current inventory"
        )
        return 1
    try:
        base = _load_json(baseline)
        allowed_files = _load_json(allowlist)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"exception ratchet: baseline/allowlist unreadable — {exc}")
        return 1

    sites, bare = find_exception_sites(root)
    violations: list[str] = []

    for path, lineno in bare:
        violations.append(
            f"bare except {path}:{lineno} — zero-tolerance class (E722): "
            "catch a specific exception type; this is a regression, not debt"
        )

    allowed_by_file: dict[str, int] = {}
    for path, entry in allowed_files.items():
        if not (root / path).is_file():
            violations.append(
                f"dead allowlist anchor {path} — the file no longer exists; "
                "delete the entry"
            )
            continue
        if not isinstance(entry, dict):
            violations.append(f"malformed allowlist entry {path}")
            continue
        reason = str(entry.get("reason", ""))
        if not reason or reason.startswith("TODO"):
            violations.append(
                f"reasonless allowlist entry {path} — cite the boundary "
                "(telemetry emitter / audit emitter / degradation fallback)"
            )
        allowed = entry.get("allowed", 0)
        if not isinstance(allowed, int) or allowed < 0:
            violations.append(f"malformed allowlist entry {path}: bad count")
            continue
        if allowed > len(sites.get(path, [])):
            violations.append(
                f"over-broad allowlist entry {path} — accepts {allowed} "
                f"site(s) but the file has {len(sites.get(path, []))}; "
                "shrink the entry"
            )
        allowed_by_file[path] = allowed

    debt_total = 0
    allowed_total = 0
    shrunk = 0
    for path, lines in sorted(sites.items()):
        allowed = allowed_by_file.get(path, 0)
        debt = len(lines) - allowed
        allowed_total += min(allowed, len(lines))
        if debt <= 0:
            continue
        debt_total += debt
        if path not in base:
            violations.append(
                f"untriaged broad except site {path}:{lines[0]} — fix it "
                "(catch the specific exception), or record it via --update, "
                "or allowlist it as a boundary catch with a reason"
            )
        elif len(base[path]) < debt:
            violations.append(
                f"new broad except site(s) in {path} ({debt} vs baseline "
                f"{len(base[path])}) — the inventory grew; fix the new site "
                "or review+record it"
            )
        elif len(base[path]) > debt:
            shrunk += len(base[path]) - debt

    for path in sorted(base):
        if path not in sites or len(sites[path]) - allowed_by_file.get(path, 0) <= 0:
            violations.append(
                f"stale baseline entry {path} — the file is clean or fully "
                "allowlisted now; remove the entry (the shrink path)"
            )

    if violations:
        print(f"exception ratchet: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"exception ratchet clean: {sum(len(v) for v in sites.values())} "
        f"broad-except site(s) — {debt_total} debt baselined, "
        f"{allowed_total} allowlisted as boundary catches, 0 bare except(s)"
    )
    if shrunk:
        print(f"  (shrink: {shrunk} baselined site(s) removed — run --update)")
    return 0


def update_exceptions(root: Path, baseline: Path, allowlist: Path) -> int:
    """Record the current debt inventory; touch the allowlist if missing."""
    sites, _bare = find_exception_sites(root)
    try:
        allowed_files = _load_json(allowlist) if allowlist.is_file() else {}
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"exception ratchet update: allowlist unreadable — {exc}")
        return 1
    files: dict[str, list[int]] = {}
    for path, lines in sorted(sites.items()):
        entry = allowed_files.get(path)
        allowed = entry.get("allowed", 0) if isinstance(entry, dict) else 0
        debt = len(lines) - allowed
        if debt > 0:
            # The baseline holds the DEBT portion only (first `debt`
            # sites) so its per-file count equals the debt the checker
            # compares — allowlisted sites are not debt.
            files[path] = sorted(lines)[:debt]
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(json.dumps({"files": files}, indent=2) + "\n")
    if not allowlist.is_file():
        allowlist.parent.mkdir(parents=True, exist_ok=True)
        allowlist.write_text(json.dumps({"files": {}}, indent=2) + "\n")
    print(
        f"exception baseline updated: {sum(len(v) for v in files.values())} "
        f"debt site(s) across {len(files)} file(s); {len(sites) - len(files)} "
        "file(s) fully allowlisted or clean"
    )
    return 0


# ── noqa instrument ─────────────────────────────────────────────────────────


def check_noqa(root: Path, baseline: Path) -> int:
    """Main noqa gate: the baseline must cover the working inventory,
    anchors must be live, and every new noqa is named for review.
    0 = clean, 1 = violation."""
    if not baseline.is_file():
        print(
            "noqa ratchet: baseline missing — run "
            "`python scripts/check_exception_ratchet.py --update` "
            "(records the noqa baseline too)"
        )
        return 1
    try:
        base = _load_json(baseline)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        print(f"noqa ratchet: baseline unreadable — {exc}")
        return 1

    counts = find_noqa_sites(root)
    violations: list[str] = []
    total = 0
    for path, count in sorted(counts.items()):
        total += count
        recorded = base.get(path)
        if path not in base:
            violations.append(
                f"untriaged # noqa in {path} ({count}) — review it: remove "
                "the noqa or record it via --update and justify it in the "
                "commit"
            )
        elif recorded < count:
            violations.append(
                f"new # noqa in {path} ({count} vs baseline {recorded}) — "
                "review it: remove it, or record it via --update and "
                "justify it in the commit"
            )
    for path in sorted(base):
        if path not in counts:
            violations.append(
                f"dead noqa baseline anchor {path} — the file no longer "
                "exists; delete the entry"
            )
        elif base[path] > counts[path]:
            pass  # shrink — fine

    if violations:
        print(f"noqa ratchet: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    shrunk = sum(
        base[path] - counts[path]
        for path in base
        if path in counts and base[path] > counts[path]
    )
    print(
        f"noqa ratchet clean: {total} # noqa comment(s) across "
        f"{len(counts)} file(s)"
    )
    if shrunk:
        print(f"  (shrink: {shrunk} noqa(s) removed — run --update)")
    return 0


def update_noqa(root: Path, baseline: Path) -> int:
    counts = find_noqa_sites(root)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(json.dumps({"files": counts}, indent=2) + "\n")
    print(
        f"noqa baseline updated: {sum(counts.values())} # noqa comment(s) "
        f"across {len(counts)} file(s)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GATE-58 exception ratchet")
    parser.add_argument("--check", action="store_true", help="exception gate")
    parser.add_argument(
        "--check-growth", action="store_true", help="exception ratchet vs HEAD"
    )
    parser.add_argument("--check-noqa", action="store_true", help="noqa gate")
    parser.add_argument(
        "--check-noqa-growth",
        action="store_true",
        help="noqa ratchet vs HEAD",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="record current exception + noqa inventories",
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    root = args.root
    exc_baseline = root / "scripts" / "exception_baseline.json"
    exc_allowlist = root / "scripts" / "exception_allowlist.json"
    noqa_baseline = root / "scripts" / "noqa_baseline.json"

    if args.check:
        return check_exceptions(root, exc_baseline, exc_allowlist)
    if args.check_growth:
        rc1 = _per_file_ratchet(root, exc_baseline, "exception baseline")
        rc2 = _per_file_ratchet(root, exc_allowlist, "exception allowlist")
        return 1 if (rc1 or rc2) else 0
    if args.check_noqa:
        return check_noqa(root, noqa_baseline)
    if args.check_noqa_growth:
        return _per_file_ratchet(root, noqa_baseline, "noqa baseline")
    if args.update:
        rc1 = update_exceptions(root, exc_baseline, exc_allowlist)
        rc2 = update_noqa(root, noqa_baseline)
        return 1 if (rc1 or rc2) else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
