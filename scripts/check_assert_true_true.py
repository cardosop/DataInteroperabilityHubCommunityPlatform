#!/usr/bin/env python3
"""
285.14.6.7 — CI-ASSERT-REAL gate.

Scans test files for common placeholder assertions that indicate
a test was stubbed but never implemented:

  - ``assertTrue(True)`` — trivially true, masks missing logic
  - ``assertIsNotNone(response)`` without further assertions
  - ``self.assertTrue(True)`` — same as above in TestCase

Exit 0 on clean, 1 if violations found.
"""
import os
import re
import sys

PATTERNS = [
    (r"assertTrue\(\s*True\s*\)", "assertTrue(True) — trivially true"),
    (r"assertIsNotNone\(\s*response\s*\)\s*$", "bare assertIsNotNone(response)"),
]

VIOLATIONS: list[tuple[str, int, str]] = []

for root, dirs, files in os.walk("hub/apps"):
    dirs[:] = [d for d in dirs if d not in ("migrations", "__pycache__", ".git")]
    for f in files:
        if not f.startswith("test_") or not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        try:
            with open(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    for pattern, desc in PATTERNS:
                        if re.search(pattern, line.strip()):
                            VIOLATIONS.append((path, lineno, desc))
        except Exception:
            pass

if VIOLATIONS:
    print(f"ASSERT-REAL gate: {len(VIOLATIONS)} violation(s) found:")
    for path, lineno, desc in VIOLATIONS[:20]:
        print(f"  {path}:{lineno} — {desc}")
    if len(VIOLATIONS) > 20:
        print(f"  ... and {len(VIOLATIONS) - 20} more")
    sys.exit(1)

print("ASSERT-REAL gate: PASSED — no trivially-true assertions found.")
sys.exit(0)
