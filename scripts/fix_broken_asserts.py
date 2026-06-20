#!/usr/bin/env python3
"""Fix broken assert*() calls in test files mangled by a prior sed script.

Repairs two common artifacts:
1. ``self.assertIn(x, (`` → the ``(`` should be ``[`` and the
   matching ``)`` on a later line should be ``]``.
2. ``self.assertIn(x not, y)`` → ``self.assertNotIn(x, y)``
3. ``self.assertEqual(x, {)`` → ``self.assertEqual(x, {})``
"""

import os
import re
import sys


def fix_file(path: str) -> bool:
    with open(path) as fh:
        content = fh.read()

    original = content

    # Fix 1: self.assertIn(X, ()  →  self.assertIn(X, [
    content = re.sub(
        r"self\.assertIn\(([^,]+), \(\)",
        r"self.assertIn(\1, [",
        content,
    )

    # Fix 2: self.assertIn(X not, Y)  →  self.assertNotIn(X, Y)
    content = re.sub(
        r"self\.assertIn\(([^,]+) not,\s*([^)]+)\)",
        r"self.assertNotIn(\1, \2)",
        content,
    )

    # Fix 3: closing ) after tuple→list conversion for assertIn.
    # self.assertIn(x, [\n  val1,\n  val2,\n) → ])
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if "self.assertIn(" in line and ", [" in line:
            # Track bracket depth to find matching closing paren
            depth = 1
            for j in range(i + 1, min(i + 10, len(lines))):
                stripped = lines[j].strip()
                for ch in lines[j]:
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                # If this line closes the original tuple with just ")"
                if stripped == ")" and depth == 1:
                    lines[j] = lines[j].replace(")", "]", 1)
                    break
                if stripped.startswith(")") and depth == 1:
                    lines[j] = lines[j].replace(")", "]", 1)
                    break
        i += 1

    # Fix 4: self.assertEqual(x, {) → self.assertEqual(x, {})
    content = "\n".join(lines)
    content = re.sub(
        r"self\.assertEqual\(([^,]+), \{\)",
        r"self.assertEqual(\1, {})",
        content,
    )

    # Fix 5: self.assert*(globals()[name], name  # comment
    # The original was `assert globals()[name] == name  # comment`
    # → self.assertEqual(globals()[name], name  # comment)
    # But sed left it as self.assertEqual(globals()[name], name  # with broken paren
    content = re.sub(
        r"self\.assertEqual\(([^)]+),\s*(\S+)\s+#",
        r"self.assertEqual(\1, \2)  #",
        content,
    )

    if content == original:
        return False

    with open(path, "w") as fh:
        fh.write(content)
    return True


def main():
    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue
        changed = fix_file(path)
        try:
            compile(content := open(path).read(), path, "exec")
            print(f"  ✓ {path}" if changed else f"  (ok) {path}")
        except SyntaxError as e:
            print(f"  ✗ STILL BROKEN: {path} — {e}")


if __name__ == "__main__":
    main()
