#!/usr/bin/env python3
"""AST-based conversion of bare Python ``assert`` statements to ``self.assert*()``.

Usage::

    python3 scripts/normalize_test_asserts.py hub/apps/tenants/tests/test_foo.py

Parses the file, walks the AST, and rewrites every top-level ``assert``
inside a ``TestCase`` method into the equivalent ``self.assert*()`` call.
Handles multi-line expressions, comments (preserved via line-level
mapping), and imports the ``status`` module when HTTP status codes are
referenced.

Idempotent — running twice produces the same output.
"""

import ast
import sys
import os
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Mapping from comparison / containment / identity operators to self.assert*()
# ---------------------------------------------------------------------------

_COMPARISON_MAP = {
    ast.Eq: "assertEqual",
    ast.NotEq: "assertNotEqual",
    ast.Gt: "assertGreater",
    ast.GtE: "assertGreaterEqual",
    ast.Lt: "assertLess",
    ast.LtE: "assertLessEqual",
    ast.In: "assertIn",
    ast.NotIn: "assertNotIn",
    ast.Is: "assertIs",
    ast.IsNot: "assertIsNot",
}

# HTTP status code constants — detected in assert expressions so we can
# auto-import ``rest_framework.status``.
_HTTP_CODE_MAP = {
    200: "status.HTTP_200_OK",
    201: "status.HTTP_201_CREATED",
    202: "status.HTTP_202_ACCEPTED",
    204: "status.HTTP_204_NO_CONTENT",
    400: "status.HTTP_400_BAD_REQUEST",
    401: "status.HTTP_401_UNAUTHORIZED",
    403: "status.HTTP_403_FORBIDDEN",
    404: "status.HTTP_404_NOT_FOUND",
    409: "status.HTTP_409_CONFLICT",
    422: "422",
    429: "status.HTTP_429_TOO_MANY_REQUESTS",
    500: "status.HTTP_500_INTERNAL_SERVER_ERROR",
    503: "status.HTTP_503_SERVICE_UNAVAILABLE",
}


def _needs_http_import(code: int) -> bool:
    return code not in (422,)  # 422 is bare int, no status constant


def _is_test_class(node: ast.ClassDef) -> bool:
    """True if the class inherits from a Django TestCase."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in (
            "TestCase", "TransactionTestCase", "SimpleTestCase",
        ):
            return True
        if isinstance(base, ast.Attribute) and base.attr in (
            "TestCase", "TransactionTestCase", "SimpleTestCase",
        ):
            return True
    return False


def _is_test_method(node) -> bool:
    """True if the node is a method starting with ``test``."""
    return isinstance(node, ast.FunctionDef) and node.name.startswith("test")


class AssertTransformer:
    """Walk a test module and convert bare asserts to self.assert*()."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.tree = ast.parse(source)
        self.imports_http = False  # set when we detect a status.HTTP_* usage
        self.used_http_codes = set()  # track which codes we converted
        # Map of (lineno) -> replacement_call_source
        self.replacements: dict[int, str] = {}
        # Lines containing assert that should be removed (the assert stmt
        # spans only one line).  For multi-line asserts we blank them.
        self.lines_to_blank: set[int] = set()

    def transform(self) -> str:
        """Run the transformation and return the new source."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and _is_test_class(node):
                for item in node.body:
                    if _is_test_method(item) or (
                        isinstance(item, ast.FunctionDef)
                        and item.name == "setUp"
                    ):
                        self._visit_function(item)

        return self._build_output()

    # ── visitor per function ──────────────────────────────────────────

    def _visit_function(self, func: ast.FunctionDef):
        for stmt in func.body:
            if isinstance(stmt, ast.Assert):
                call_str = self._convert_assert(stmt)
                if call_str is not None:
                    lineno = stmt.end_lineno or stmt.lineno
                    # multi-line: blank all interior lines, put call on the
                    # last line that was part of the original assert.
                    if stmt.end_lineno and stmt.end_lineno > stmt.lineno:
                        for line in range(stmt.lineno, stmt.end_lineno):
                            self.lines_to_blank.add(line)
                    if lineno not in self.replacements:
                        self.replacements[lineno] = call_str
                    else:
                        self.replacements[lineno] += "\n" + call_str

    def _convert_assert(self, node: ast.Assert) -> Optional[str]:
        """Return a self.assert*(...) source string for *node*, or None."""
        test = node.test
        msg = node.msg  # optional failure message (ast.Constant or None)

        # --- assert x / assert not x (bare boolean) --------------------
        if isinstance(test, ast.Name) and test.id not in ("True", "False", "None"):
            return self._format("assertTrue", _name(test.id), msg)
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            inner_str = ast.unparse(test.operand)
            return self._format("assertFalse", inner_str, msg)

        # --- assert x is True / assert x is False ----------------------
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            op = test.ops[0]
            left = ast.unparse(test.left)
            if isinstance(op, ast.Is):
                right_raw = ast.unparse(test.comparators[0])
                if right_raw == "True":
                    return self._format("assertTrue", left, msg)
                if right_raw == "False":
                    return self._format("assertFalse", left, msg)
                if right_raw == "None":
                    return self._format("assertIsNone", left, msg)
                # assert x is y  → assertIs(x, y)
                return self._format("assertIs", f"{left}, {right_raw}", msg)
            if isinstance(op, ast.IsNot):
                right_raw = ast.unparse(test.comparators[0])
                if right_raw == "None":
                    return self._format("assertIsNotNone", left, msg)
                return self._format(
                    "assertIsNot", f"{left}, {right_raw}", msg,
                )

            # --- comparison operators (==, !=, >, >=, <, <=) ----------
            if type(op) in _COMPARISON_MAP:
                method = _COMPARISON_MAP[type(op)]
                right = self._maybe_http_constant(
                    test.comparators[0],
                )
                right_str = ast.unparse(right)
                return self._format(method, f"{left}, {right_str}", msg)

        # --- assert container / assert not container (truthiness) ----
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return self._format(
                "assertFalse", ast.unparse(test.operand), msg,
            )

        # --- assert callable(args)  (e.g. assert resp.status_code == 200)
        if isinstance(test, ast.Compare):
            for i, op in enumerate(test.ops):
                if isinstance(op, (ast.Eq, ast.NotEq)) and not isinstance(
                    test.comparators[i], ast.Name
                ):
                    try:
                        val = int(ast.literal_eval(test.comparators[i]))
                        if val in _HTTP_CODE_MAP:
                            self.used_http_codes.add(val)
                            left = ast.unparse(test.left)
                            method = "assertEqual" if isinstance(op, ast.Eq) else "assertNotEqual"
                            right = _HTTP_CODE_MAP[val]
                            return self._format(method, f"{left}, {right}", msg)
                    except (ValueError, SyntaxError):
                        pass

        # --- Fallback: generic expression → assertTrue / assertEqual ---
        return self._format("assertTrue", ast.unparse(test), msg)

    def _maybe_http_constant(self, node):
        """If *node* is a literal HTTP code, return a Name referencing
        status.HTTP_* so we can emit the constant instead of magic number."""
        try:
            val = ast.literal_eval(node)
            if isinstance(val, int) and val in _HTTP_CODE_MAP:
                self.used_http_codes.add(val)
                return ast.Name(id=_HTTP_CODE_MAP[val], ctx=ast.Load())
        except (ValueError, SyntaxError):
            pass
        return node

    def _format(self, method: str, args: str, msg) -> str:
        """Build a ``self.method(args)`` or ``self.method(args, msg)`` call."""
        if msg is not None:
            # The AST stores the message as a Constant node.
            msg_str = ast.unparse(msg)
            return f"self.{method}({args}, {msg_str})"
        return f"self.{method}({args})"

    # ── output builder ────────────────────────────────────────────────

    def _build_output(self) -> str:
        result = []
        for idx, line in enumerate(self.lines, start=1):
            if idx in self.lines_to_blank:
                # blank interior lines of multi-line asserts
                result.append("\n")
            elif idx in self.replacements:
                # replace the final line of the assert with new call
                # strip the trailing newline from original, append replacement
                stripped = line.rstrip("\n")
                indent = stripped[: len(stripped) - len(stripped.lstrip())]
                result.append(f"{indent}{self.replacements[idx]}\n")
            else:
                result.append(line)

        output = "".join(result)
        if self.used_http_codes:
            output = self._add_http_import(output)
        return output

    def _add_http_import(self, source: str) -> str:
        """Insert ``from rest_framework import status`` if not already present."""
        if "from rest_framework import status" in source:
            return source
        if "import status" in source:
            return source
        # Insert after the last `from … import …` line.
        lines = source.splitlines(keepends=True)
        last_import_idx = 0
        for i, line in enumerate(lines):
            if re.match(r"^(from|import)\s", line):
                last_import_idx = i
        if last_import_idx > 0:
            lines.insert(
                last_import_idx + 1,
                "from rest_framework import status\n",
            )
        else:
            lines.insert(0, "from rest_framework import status\n")
        return "".join(lines)


def _name(id_str: str) -> str:
    """Wrap a bare identifier so the AST unparser produces a valid expression."""
    return id_str


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <test_file.py>", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"ERROR: not a file: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r") as fh:
        original = fh.read()

    transformer = AssertTransformer(original)
    transformed = transformer.transform()

    if transformed == original:
        print(f"  (no changes) {path}")
        return

    with open(path, "w") as fh:
        fh.write(transformed)
    print(f"  ✓ {path}")


if __name__ == "__main__":
    main()
