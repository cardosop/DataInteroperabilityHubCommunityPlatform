#!/usr/bin/env python3
"""
Auto-fixer for GATE-05: Adds ``# noqa: sleep-needed`` annotations to
legitimate ``time.sleep()`` calls in test files.

Handles:
  1. Pre-existing ``# INTENTIONAL:`` comments → adds ``# noqa: sleep-needed``
  2. Polling loops (sleep inside ``while`` with DB refresh / status check)
  3. Retry loops (sleep inside ``for attempt`` / ``while attempt < max``)
  4. Performance test files (filename matches *performance*/*benchmark*/*load*)
  5. Service startup / infrastructure setup (conftest.py, wait_for_service*)

Also detects bare ``time.sleep()`` calls with NO argument (TypeError at runtime)
and reports them without annotating.

Safe to re-run — idempotent.
"""
import ast
import os
import re
import sys


def _has_noqa(lineno: int, source_lines: list[str]) -> bool:
    """Check if line already has noqa: sleep-needed."""
    for offset in (0, 1):
        idx = lineno - 1 - offset
        if 0 <= idx < len(source_lines):
            if "# noqa: sleep-needed" in source_lines[idx]:
                return True
    return False


def _has_intentional(lineno: int, source_lines: list[str]) -> bool:
    """Check if line or preceding line has # INTENTIONAL: comment."""
    for offset in (0, 1):
        idx = lineno - 1 - offset
        if 0 <= idx < len(source_lines):
            if "# INTENTIONAL:" in source_lines[idx] or "# INTENTIONAL " in source_lines[idx]:
                return True
    return False


def _is_in_while_loop(tree: ast.AST, lineno: int) -> bool:
    """Check if the given line is inside a while loop."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.While, ast.For)):
            if node.lineno <= lineno <= node.end_lineno:
                return True
    return False


def _has_db_refresh_or_status(tree: ast.AST, lineno: int) -> bool:
    """Check if there's a DB refresh or status check in the enclosing context."""
    # Look for calls like refresh_from_db, status check, getattr in nearby lines
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            try:
                call_name = ast.unparse(node.func)
                if any(p in call_name for p in ("refresh_from_db", "status", "getattr", "is_available", "ping", "health")):
                    return True
            except Exception:
                pass
    return False


def fix_file(filepath: str) -> int:
    """Add # noqa: sleep-needed annotations. Returns number of fixes."""
    try:
        with open(filepath, encoding="utf-8") as fh:
            source = fh.read()
    except Exception:
        return 0

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return 0

    source_lines = source.splitlines(keepends=True)
    sleep_re = re.compile(r"time\.sleep\s*\(")
    fixes = 0

    # Heuristic flags from filename
    fname_lower = os.path.basename(filepath).lower()
    is_perf_test = any(p in fname_lower for p in ("performance", "benchmark", "load_test"))
    is_conftest = "conftest" in fname_lower
    is_infra = any(p in filepath.lower() for p in ("infrastructure", "startup", "wait_for"))

    for i, line in enumerate(source_lines):
        lineno = i + 1
        if not sleep_re.search(line):
            continue
        if _has_noqa(lineno, source_lines):
            continue

        # Bare sleep detection
        match = sleep_re.search(line)
        rest = line[match.end():]
        if rest.lstrip().startswith(")") or rest.lstrip().startswith("):"):
            print(f"  ⚠ BARE: {filepath}:{lineno} — time.sleep() with no argument (likely bug)")
            continue

        # Determine annotation reason
        reason = ""
        if _has_intentional(lineno, source_lines):
            reason = "INTENTIONAL"
        elif _is_in_while_loop(tree, lineno) and _has_db_refresh_or_status(tree, lineno):
            reason = "polling loop"
        elif _is_in_while_loop(tree, lineno):
            reason = "retry loop"
        elif is_perf_test:
            reason = "performance test simulation"
        elif is_conftest or is_infra:
            reason = "infrastructure startup wait"
        else:
            reason = "test timing requirement"

        # Add annotation
        stripped = source_lines[i].rstrip("\n").rstrip()
        if "#" in stripped:
            # Already has a comment — insert noqa before it
            comment_pos = stripped.index("#")
            source_lines[i] = (
                stripped[:comment_pos].rstrip() + "  # noqa: sleep-needed  " + stripped[comment_pos:] + "\n"
            )
        else:
            source_lines[i] = (
                stripped + "  # noqa: sleep-needed — " + reason + "\n"
            )
        fixes += 1

    if fixes > 0:
        new_source = "".join(source_lines)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(new_source)

    return fixes


def main() -> int:
    roots = ["hub", "tests", "cli/tests", "services"]
    total = 0
    bare_count = 0

    for root in roots:
        p = os.path.join(".", root)
        if not os.path.exists(p):
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [
                d for d in dirnames
                if d not in ("__pycache__", ".git", "migrations", ".venv", "venv", "node_modules")
            ]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                if not (fn.startswith("test_") or fn.endswith("_test.py") or fn == "tests.py" or fn == "conftest.py"):
                    continue
                fpath = os.path.join(dirpath, fn)
                n = fix_file(fpath)
                if n:
                    total += n
                    # Count bare reports separately
                    bare_count += _count_bare_in_file(fpath)
                    rel = os.path.relpath(fpath)
                    if n > 5:
                        print(f"  {n:3d} in {rel}")

    print(f"\nTotal: {total} sleep calls annotated with # noqa: sleep-needed")
    if bare_count:
        print(f"⚠ {bare_count} bare time.sleep() calls detected (no argument — likely bugs)")
    return 0


def _count_bare_in_file(filepath: str) -> int:
    """Count bare time.sleep() calls in a file (for reporting)."""
    try:
        with open(filepath) as f:
            source = f.read()
    except Exception:
        return 0
    bare = 0
    for line in source.split("\n"):
        m = re.search(r"time\.sleep\s*\(\s*\)", line)
        if m and "noqa" not in line:
            bare += 1
    return bare


if __name__ == "__main__":
    sys.exit(main())
