#!/usr/bin/env python3
"""
P2-5 (close-oss-release-conditions, G13) — the public re-sync acceptance
diff checker.

Before the re-sync replaces the public tree, EVERY file in the OLD public
tree must be accounted for: present in the NEW built tree (kept), or
classified in the drift allowlist (path + reason — the P-1 structural
drift: checkout litter that the old ``git add -A`` swept into sync
commits). Anything else is an unclassified public-only file and the sync
must NOT drop it silently — exit 1.

The overlay direction is pinned too: every file under the publish
overlay (LICENSE, SECURITY.md, CODE_OF_CONDUCT.md, .github workflows,
the examples, ...) MUST be present in the new tree — public-only
additions can never be silently dropped (G13).

Usage:
    check_public_resync_diff.py OLD_TREE NEW_TREE --drift-file F [--overlay-dir D]

Drift allowlist format (one entry per line, TAB-separated):
    path<TAB>reason
``path`` is a file path or a trailing-slash directory prefix (the same
semantics as publish_paths_exclude.txt); ``#`` starts a comment.

Exit codes: 0 = every old file accounted for + overlay preserved ·
1 = unclassified files or missing overlay files · 2 = usage/tooling
failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_FAILURE = 2


def parse_drift_entries(drift_file: Path) -> list[tuple[str, str]]:
    """[(path-or-dir-prefix, reason)] — comments and blanks skipped."""
    entries: list[tuple[str, str]] = []
    for line in drift_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path, sep, reason = line.partition("\t")
        if not sep:
            raise ValueError(f"drift entry lacks a TAB-separated reason: {line!r}")
        entries.append((path.strip(), reason.strip()))
    return entries


def drift_allows(entries: list[tuple[str, str]], rel: str) -> tuple[bool, str]:
    """Exact-path or directory-prefix match (trailing-slash entries)."""
    for path, reason in entries:
        if path.endswith("/") and rel.startswith(path):
            return True, reason
        if rel == path:
            return True, reason
    return False, ""


def _walk_files(root: Path) -> list[str]:
    if not root.is_dir():
        raise ValueError(f"tree does not exist: {root}")
    return sorted(
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
    )


def diff_trees(old_root: Path, new_root: Path, drift_file: Path) -> dict:
    """The G13 classification: every old file is kept / removed-with-
    reason / unclassified."""
    entries = parse_drift_entries(drift_file)
    new_files = set(_walk_files(new_root))
    kept: list[str] = []
    removed: list[str] = []
    unclassified: list[str] = []
    for rel in _walk_files(old_root):
        if rel in new_files:
            kept.append(rel)
        else:
            allowed, _reason = drift_allows(entries, rel)
            if allowed:
                removed.append(rel)
            else:
                unclassified.append(rel)
    added = sorted(new_files - set(_walk_files(old_root)))
    return {
        "kept": kept,
        "removed": removed,
        "added": added,
        "unclassified": unclassified,
    }


def overlay_missing_files(new_root: Path, overlay_dir: Path) -> list[str]:
    """Every overlay file must be present in the new tree."""
    return [rel for rel in _walk_files(overlay_dir) if not (new_root / rel).is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_tree", type=Path, help="the OLD public tree (pre-re-sync)")
    parser.add_argument("new_tree", type=Path, help="the NEW built publish tree")
    parser.add_argument("--drift-file", type=Path, required=True, help="drift allowlist")
    parser.add_argument(
        "--overlay-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "publish_public_overlay",
        help="the publish overlay (default: scripts/publish_public_overlay)",
    )
    args = parser.parse_args(argv)

    try:
        report = diff_trees(args.old_tree, args.new_tree, args.drift_file)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    missing = overlay_missing_files(args.new_tree, args.overlay_dir)

    print(f"kept: {len(report['kept'])}")
    print(f"removed (drift-classified): {len(report['removed'])}")
    print(f"added: {len(report['added'])}")
    if report["unclassified"]:
        print("UNCLASSIFIED public-only files (would be silently dropped):")
        for rel in report["unclassified"]:
            print(f"  {rel}")
    if missing:
        print("MISSING overlay files (public-only additions dropped):")
        for rel in missing:
            print(f"  {rel}")
    if report["unclassified"] or missing:
        return EXIT_VIOLATION
    print("G13 OK: every old public file accounted for; overlay preserved")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
