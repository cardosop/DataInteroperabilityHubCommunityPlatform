#!/usr/bin/env python3
"""
285.14.6.12 — Test pattern enforcement.

Scans app test directories for minimum required test patterns:
  - Models: test_create, test_str, test_constraints
  - Views: test_auth_required, test_throttle, test_response_shape
  - RLS: test_rls_policy_

Informational for 30 days, then blocks CI. Exit 0 always (info-only phase).
"""

import os
import sys
from collections import defaultdict

REQUIRED_PATTERNS = {
    "model": ["test_create", "test_str", "test_constraints"],
    "view": ["test_auth_required", "test_throttle", "test_response_shape"],
    "rls": ["test_rls_policy_"],
}

APP_DIRS = [d for d in os.listdir("hub/apps") if os.path.isdir(f"hub/apps/{d}/tests")]

results: dict[str, dict[str, bool]] = defaultdict(dict)

for app in sorted(APP_DIRS):
    test_dir = f"hub/apps/{app}/tests"
    all_content = ""
    for root, _dirs, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".py") and not f.startswith("__"):
                try:
                    with open(os.path.join(root, f)) as fh:
                        all_content += fh.read()
                except Exception:
                    pass

    for category, patterns in REQUIRED_PATTERNS.items():
        found = all(p in all_content for p in patterns)
        results[app][category] = found

missing_count = sum(
    1 for app in results for cat in REQUIRED_PATTERNS if not results[app].get(cat, False)
)

print(f"Test pattern audit: {len(results)} apps, {missing_count} gaps")
print("(Informational phase — no CI block until 30-day window elapses)")
print()

for app, cats in sorted(results.items()):
    statuses = []
    for cat in sorted(cats):
        statuses.append(f"{cat}={'✅' if cats[cat] else '❌'}")
    print(f"  {app:<20} {' | '.join(statuses)}")

sys.exit(0)  # Always exit 0 during informational phase
