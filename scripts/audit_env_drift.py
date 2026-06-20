#!/usr/bin/env python3
"""307.12 — Compare .env.example keys against actual .env.* files."""

import os
import re
import sys


def parse_keys(path):
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {m.group(1) for m in re.finditer(r"^([A-Z_][A-Z0-9_]*)\s*=", f.read(), re.MULTILINE)}


def main():
    example = parse_keys(".env.example")
    results = {}
    for f in os.listdir("."):
        if f.startswith(".env.") and f != ".env.example":
            keys = parse_keys(f)
            missing = example - keys
            extra = keys - example
            results[f] = {"missing": sorted(missing), "extra": sorted(extra)}
    for name, r in sorted(results.items()):
        print(f"\n{name}:")
        if r["missing"]:
            print(f"  Missing: {', '.join(r['missing'][:10])}")
        if r["extra"]:
            print(f"  Extra: {', '.join(r['extra'][:10])}")
        if not r["missing"] and not r["extra"]:
            print("  ✅ In sync with .env.example")
    sys.exit(0)


if __name__ == "__main__":
    main()
