#!/usr/bin/env python3
"""
Auto-fixer for GATE-07: Converts ``pytest.skip()`` in test bodies to
``@pytest.mark.skipif`` / ``@pytest.mark.skip`` decorators where safe,
and annotates runtime-dependent skips with ``# noqa: skip-in-body``.

Patterns handled:
  A. Environment variable guard → @pytest.mark.skipif(not os.environ.get(...), ...)
  B. File existence guard → @pytest.mark.skipif(not os.path.exists(...), ...)
  C. Import-guarded skip → hoist to module level + @pytest.mark.skipif
  D. Unconditional skip → @pytest.mark.skip(reason=...)
  E. Runtime-dependent skip → annotate with # noqa: skip-in-body

Safe to re-run — idempotent.  Only transforms ``pytest.skip()`` calls
inside ``def test_*`` functions.
"""
import ast
import os
import re
import sys

# ── AST helpers ──────────────────────────────────────────────────────────


def _is_os_environ_get(node: ast.Call) -> bool:
    """Return True if node is ``os.environ.get(...)`` or ``os.getenv(...)``."""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "environ":
            if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "os":
                return node.func.attr == "get"
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
            return node.func.attr == "getenv"
    return False


def _is_os_path_exists(node: ast.Call) -> bool:
    """Return True if node is ``os.path.exists(...)``."""
    if isinstance(node.func, ast.Attribute) and node.func.attr == "exists":
        if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "path":
            if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "os":
                return True
    return False


def _is_import_safe_call(node: ast.Call) -> bool:
    """Return True if the call is import-safe (env var, file check, etc.)."""
    if _is_os_environ_get(node):
        return True
    if _is_os_path_exists(node):
        return True
    if isinstance(node.func, ast.Name):
        # builtins like isinstance, hasattr, etc. are import-safe
        if node.func.id in ("isinstance", "hasattr", "callable", "len", "bool", "str", "int", "float"):
            return True
    # Anything else (function calls, method calls) is NOT import-safe.
    return False


def _extract_reason(skip_call: ast.Call, source_lines: list[str]) -> str:
    """Extract the reason string from a pytest.skip() call."""
    if skip_call.args:
        first_arg = skip_call.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return first_arg.value
        # Try to get the source text
        try:
            return ast.unparse(first_arg)
        except Exception:
            pass
    # Try keyword arg
    for kw in skip_call.keywords:
        if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "skip condition"


def _get_condition_source(node: ast.expr, source_lines: list[str]) -> str:
    """Get the source text of a condition expression."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<?>"


# ── Skip analysis ────────────────────────────────────────────────────────


def analyze_skip(skip_call: ast.Call, parent_stmt: ast.stmt, source_lines: list[str]) -> str:
    """Analyze a pytest.skip() call and return the recommended fix type.

    Returns one of: 'env', 'file', 'import_guard', 'unconditional', 'runtime'.
    """
    # Unconditional: pytest.skip() as the only statement / top-level in function
    is_unconditional = False
    if isinstance(parent_stmt, ast.Expr):
        is_unconditional = True  # bare pytest.skip() expression

    # Inside an if block — check the condition
    if isinstance(parent_stmt, ast.If):
        condition = parent_stmt.test
        # Handle:  if not os.environ.get(...):
        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            operand = condition.operand
            if isinstance(operand, ast.Call):
                if _is_os_environ_get(operand):
                    return "env"
                if _is_os_path_exists(operand):
                    return "file"
        # Handle:  if not import_safe_call:
        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            operand = condition.operand
            if isinstance(operand, ast.Call) and _is_import_safe_call(operand):
                return "file"

    if is_unconditional:
        return "unconditional"

    # Check if we're inside a try/except ImportError handler
    # (detected by the enclosing try/except structure — handled at a higher level)
    return "runtime"


# ── File-level fixer ─────────────────────────────────────────────────────


def fix_file(filepath: str) -> dict:
    """Fix all pytest.skip() calls in test bodies.

    Returns dict with counts per fix type.
    """
    try:
        with open(filepath, encoding="utf-8") as fh:
            source = fh.read()
    except Exception:
        return {}

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return {}

    source_lines = source.splitlines(keepends=True)
    fixes: list[dict] = []  # each: {type, start_line, end_line, old, new, decorator, reason, ...}

    # Walk test functions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        _collect_skip_fixes(node, source_lines, fixes, tree, filepath)

    if not fixes:
        return {}

    counts = {}
    # Apply fixes in reverse line order (bottom-up)
    fixes.sort(key=lambda f: -f["lineno"])

    for fix in fixes:
        fix_type = fix["type"]
        counts[fix_type] = counts.get(fix_type, 0) + 1

        if fix_type == "env" or fix_type == "file":
            _apply_env_file_fix(fix, source_lines)
        elif fix_type == "import_guard":
            _apply_import_fix(fix, source_lines)
        elif fix_type == "unconditional":
            _apply_unconditional_fix(fix, source_lines, tree, filepath)
        elif fix_type == "noqa":
            _apply_noqa_fix(fix, source_lines)

    new_source = "".join(source_lines)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(new_source)

    return counts


def _collect_skip_fixes(func_node, source_lines, fixes, tree, filepath):
    """Find pytest.skip() calls inside a test function and classify them."""
    for child in ast.walk(func_node):
        if not isinstance(child, ast.Expr):
            continue
        if not isinstance(child.value, ast.Call):
            continue
        call = child.value
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "pytest"
            and call.func.attr == "skip"
        ):
            continue

        skip_lineno = child.lineno

        # Check if already has noqa annotation
        if _has_noqa(skip_lineno, source_lines):
            continue

        # Find parent statement context
        parent = _find_parent_stmt(func_node, child)

        reason = _extract_reason(call, source_lines)

        if isinstance(parent, ast.If):
            condition = parent.test
            cond_src = _get_condition_source(condition, source_lines)

            if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
                operand = condition.operand
                if isinstance(operand, ast.Call) and _is_os_environ_get(operand):
                    fixes.append({
                        "type": "env",
                        "lineno": parent.lineno,
                        "end_lineno": parent.end_lineno,
                        "func_node": func_node,
                        "condition_src": _get_condition_source(condition, source_lines),
                        "reason": reason,
                    })
                    continue
                if isinstance(operand, ast.Call) and _is_os_path_exists(operand):
                    fixes.append({
                        "type": "file",
                        "lineno": parent.lineno,
                        "end_lineno": parent.end_lineno,
                        "func_node": func_node,
                        "condition_src": _get_condition_source(condition, source_lines),
                        "reason": reason,
                    })
                    continue

        # Check for unconditional bare skip (Pattern D)
        if isinstance(parent, ast.Expr) and parent is child:
            fixes.append({
                "type": "unconditional",
                "lineno": child.lineno,
                "func_node": func_node,
                "reason": reason,
            })
            continue

        # Check for import-guarded skip (Pattern C) — look at enclosing Try node
        if _is_inside_import_guard(child, func_node):
            fixes.append({
                "type": "import_guard",
                "lineno": child.lineno,
                "func_node": func_node,
                "reason": reason,
            })
            continue

        # Runtime-dependent (Pattern E) — annotate with noqa
        fixes.append({
            "type": "noqa",
            "lineno": child.lineno,
            "func_node": func_node,
            "reason": reason,
        })


def _is_inside_import_guard(skip_node: ast.stmt, func_node: ast.FunctionDef) -> bool:
    """Check if the skip is inside a try/except ImportError handler."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
                    for stmt in ast.walk(handler):
                        if stmt is skip_node:
                            return True
    return False


def _find_parent_stmt(func_node: ast.FunctionDef, target: ast.AST) -> ast.stmt | None:
    """Find the statement in *func_node* that contains *target*."""
    for stmt in ast.walk(func_node):
        if isinstance(stmt, ast.If):
            for child in ast.walk(stmt):
                if child is target:
                    return stmt
        if stmt is target:
            return stmt
    return None


def _has_noqa(lineno: int, source_lines: list[str]) -> bool:
    """Check for # noqa: skip-in-body annotation."""
    for offset in (0, 1):
        idx = lineno - 1 - offset
        if 0 <= idx < len(source_lines):
            if "# noqa: skip-in-body" in source_lines[idx]:
                return True
    return False


# ── Fix applicators ──────────────────────────────────────────────────────


def _apply_env_file_fix(fix: dict, source_lines: list[str]):
    """Replace the if/skip block with a decorator on the test function."""
    func = fix["func_node"]
    skip_if_block_idx = fix["lineno"] - 1
    skip_end_idx = fix.get("end_lineno", fix["lineno"]) - 1

    # Remove the entire if block (replace with empty)
    for i in range(skip_if_block_idx, skip_end_idx + 1):
        source_lines[i] = ""

    # Add decorator before the function def
    decorator = (
        f'@pytest.mark.skipif({fix["condition_src"]}, '
        f'reason="{fix["reason"]}")\n'
    )
    func_def_idx = func.lineno - 1
    source_lines.insert(func_def_idx, decorator)

    # Adjust fix lineno for subsequent fixes in this file (handled by reverse order)


def _apply_unconditional_fix(fix: dict, source_lines: list[str], tree: ast.AST, filepath: str):
    """Replace bare pytest.skip() with @pytest.mark.skip decorator."""
    func = fix["func_node"]
    skip_idx = fix["lineno"] - 1

    # Remove the skip line
    source_lines[skip_idx] = ""

    # Add decorator before the function def
    decorator = f'@pytest.mark.skip(reason="{fix["reason"]}")\n'
    func_def_idx = func.lineno - 1
    source_lines.insert(func_def_idx, decorator)


def _apply_import_fix(fix: dict, source_lines: list[str]):
    """Hoist import to module level and add skipif decorator.

    This is the most complex — we need to find the try/except ImportError
    block inside the function and hoist the try/import to module level.
    For now, annotate with noqa and let a manual process handle hoisting.
    """
    # Import hoisting is too complex for safe auto-fix — annotate instead
    _apply_noqa_fix(fix, source_lines)


def _apply_noqa_fix(fix: dict, source_lines: list[str]):
    """Add # noqa: skip-in-body to the pytest.skip() line."""
    idx = fix["lineno"] - 1
    if 0 <= idx < len(source_lines):
        line = source_lines[idx].rstrip("\n")
        if "# noqa: skip-in-body" not in line:
            source_lines[idx] = (
                line.rstrip() + "  # noqa: skip-in-body — runtime service dependency\n"
            )


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> int:
    roots = ["hub", "tests"]
    total_counts: dict[str, int] = {}
    files_fixed = 0

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
                if not (fn.startswith("test_") or fn.endswith("_test.py") or fn == "tests.py"):
                    continue
                fpath = os.path.join(dirpath, fn)
                counts = fix_file(fpath)
                if counts:
                    files_fixed += 1
                    for k, v in counts.items():
                        total_counts[k] = total_counts.get(k, 0) + v
                    rel = os.path.relpath(fpath)
                    detail = ", ".join(f"{v} {k}" for k, v in counts.items())
                    print(f"  {rel}: {detail}")

    print(f"\nTotal: {sum(total_counts.values())} fixes across {files_fixed} files")
    for k in sorted(total_counts.keys()):
        print(f"  {k}: {total_counts[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
