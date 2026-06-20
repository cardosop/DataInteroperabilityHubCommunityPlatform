#!/usr/bin/env python3
"""Fix broken test files by removing sed artifacts line-by-line.

Collectively handles: double-closing-parens, missing bracket closures,
dict opening without closing, and misshapen assertIn tuples.
"""

import os
import re
import sys


def fix(path):
    with open(path) as fh:
        lines = fh.readlines()
    fixed = []
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        # (1) self.assertEqual(x, y))  →  self.assertEqual(x, y)
        if re.search(r"self\.assert\w+\([^)]+\)\s*\)", stripped):
            # extra closing paren at end
            stripped = re.sub(r"\)\s*$", "", stripped)
            stripped += ")"
        # (2) self.assertIn(x, ()  →  self.assertIn(x, [status.HTTP_...)
        #     followed by lines with status codes, then a closing )
        # We handle this by removing the leading ( from the multi-line
        # and replacing the trailing ) with ] in a second pass below.
        # (3) self.assertIn(x not, y)  →  self.assertNotIn(x, y)
        stripped = re.sub(
            r"self\.assertIn\(([^)]+?) not,\s*(\S+)\s*\)",
            r"self.assertNotIn(\1, \2)",
            stripped,
        )
        # (4) self.assertEqual(x, {)  →  self.assertEqual(x, {})
        stripped = re.sub(
            r"self\.assertEqual\(([^,]+),\s*\{\)",
            r"self.assertEqual(\1, {})",
            stripped,
        )
        fixed.append(stripped + "\n")

    content = "".join(fixed)

    # Pass 2: fix self.assertIn(x, () multi-line → self.assertIn(x, [...])
    # and self.assertEqual(X, ( → self.assertEqual(X, (...)
    content = re.sub(
        r"self\.assertIn\(([^,]+), \(\)",
        r"self.assertIn(\1, [",
        content,
    )
    # Fix the closing ) of former tuple to ]
    lines2 = content.split("\n")
    for i, line in enumerate(lines2):
        if "self.assertIn(" in line and ", [" in line:
            # Scan forward for the closing )
            depth = 0
            for j in range(i, min(i + 15, len(lines2))):
                s = lines2[j].strip()
                for ch in lines2[j]:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    elif ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                if s in (")", "),") and depth <= 0 and j > i:
                    lines2[j] = lines2[j].replace(")", "]", 1)
                    break

    content = "\n".join(lines2)

    with open(path, "w") as fh:
        fh.write(content)

    try:
        compile(content, path, "exec")
        print(f"  ✓ {path}")
        return True
    except SyntaxError as e:
        print(f"  ✗ {path} — {e}")
        return False


for path in sys.argv[1:]:
    if os.path.isfile(path):
        fix(path)
