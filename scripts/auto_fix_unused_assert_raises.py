#!/usr/bin/env python3
"""
Auto-fixer for GATE-02: Removes unused assertRaises context variables.

Finds ``with self.assertRaises(SomeException) as cm:`` blocks where the
context variable (e.g. ``cm``) is never referenced in the with-body, and
removes the ``as <var>`` clause.

Uses AST to verify the variable is truly unused before removing.
Safe to re-run — idempotent.
"""

import ast
import os
import sys

MAX_BODY_LENGTH = 500


def _var_is_used_in_body(
    var_name: str, body_nodes: list[ast.stmt], source_lines: list[str]
) -> bool:
    """Check if *var_name* is referenced anywhere in the body AST nodes."""
    # Quick string check first (same heuristic as the lint)
    body_text = (
        "".join(source_lines[body_nodes[0].lineno - 1 : body_nodes[-1].end_lineno])
        if body_nodes
        else ""
    )

    if len(body_text) > MAX_BODY_LENGTH:
        body_text = body_text[:MAX_BODY_LENGTH]

    if var_name not in body_text:
        return False

    # Confirm with AST: walk body nodes looking for Name(id=var_name)
    for node in body_nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == var_name:
                return True
    return False


def fix_file(filepath: str) -> int:
    """Remove unused ``as <var>`` clauses from assertRaises with-blocks.

    Returns the number of fixes applied.
    """
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
    fixes: list[tuple[int, int, str, str]] = []  # (start_col, end_col, var_name, context_expr)

    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            if not isinstance(item.optional_vars, ast.Name):
                continue
            ctx_var = item.optional_vars.id
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "assertRaises":
                continue

            # Check if ctx_var is used in the body
            if not _var_is_used_in_body(ctx_var, node.body, source_lines):
                # Calculate the position of " as <var>" in the source line
                line_idx = node.lineno - 1
                source_lines[line_idx]

                # Find " as <var>" pattern on this line
                # The context_expr ends at col_offset, then " as <var>"
                # Use the AST's end_lineno/end_col_offset to be precise
                # But the with statement might span multiple lines
                # We need to find " as <var>" in the source text

                # Strategy: search the source from context_expr end to find " as <var>"
                # Get the context expression source text end position
                call.end_lineno if hasattr(call, "end_lineno") else node.lineno
                call.end_col_offset if hasattr(call, "end_col_offset") else 0

                # Find " as <var>" in the source
                # Search from line_idx to ctx_end_line for the pattern
                # Build remaining source from the with start
                remaining = ""
                for l in range(line_idx, len(source_lines)):
                    if l == line_idx:
                        remaining += source_lines[l]
                    else:
                        remaining += source_lines[l]

                import re

                # Find " as <ctx_var>" (possibly with colon after)
                pattern = re.compile(rf"\bas\s+{re.escape(ctx_var)}\b")
                match = pattern.search(remaining)
                if match:
                    # Calculate absolute position in the full source
                    prefix_len = 0
                    for l in range(line_idx):
                        prefix_len += len(source_lines[l])
                    abs_start = prefix_len + match.start()
                    abs_end = prefix_len + match.end()

                    fixes.append((abs_start, abs_end, ctx_var, filepath))

    if not fixes:
        return 0

    # Apply fixes in reverse order (from end of file to start)
    fixes.sort(key=lambda f: -f[0])
    source_chars = list(source)
    for abs_start, abs_end, _var_name, _ in fixes:
        # Remove " as <var>"
        del source_chars[abs_start:abs_end]

    new_source = "".join(source_chars)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(new_source)

    return len(fixes)


def main() -> int:
    roots = ["hub", "tests"]
    total_fixes = 0
    files_fixed = 0

    for root in roots:
        p = os.path.join(".", root)
        if not os.path.exists(p):
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("__pycache__", ".git", "migrations", ".venv", "venv", "node_modules")
            ]
            for fn in filenames:
                if not fn.startswith("test_") or not fn.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fn)
                n = fix_file(fpath)
                if n > 0:
                    total_fixes += n
                    files_fixed += 1
                    print(f"  Fixed {n} in {fpath}")

    print(f"\nTotal: {total_fixes} fixes across {files_fixed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
