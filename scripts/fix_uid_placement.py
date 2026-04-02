#!/usr/bin/env python3
"""Fix uid placement - move uid= line out of Tenant.objects.create() calls."""
import os
import re
import subprocess


def find_broken_files():
    """Find files where uid= is inside a create() call."""
    r = subprocess.run(
        ["grep", "-rln", "uid = uuid.uuid4", "hub/apps/", "--include=*.py"],
        capture_output=True, text=True, cwd="/app"
    )
    return [f for f in r.stdout.strip().split("\n") if f]


def fix_file(filepath):
    full = os.path.join("/app", filepath)
    if not os.path.exists(full):
        return False

    with open(full) as f:
        content = f.read()

    original = content

    # Pattern: uid line is INSIDE a create/objects call (indented inside parens)
    # Fix: move it BEFORE the create call
    lines = content.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this is "uid = uuid.uuid4().hex[:8]" inside a call
        if stripped == "uid = uuid.uuid4().hex[:8]":
            # Check if previous line has an open paren (we're inside a call)
            if i > 0:
                prev = lines[i - 1].rstrip()
                if prev.endswith("(") or prev.endswith(","):
                    # We're inside a function call - move this line before the call
                    # Find the start of the call (Tenant.objects.create, etc)
                    call_start = i - 1
                    while call_start > 0 and not lines[call_start].strip().endswith("("):
                        call_start -= 1
                    # Get indentation of the call
                    indent = len(lines[call_start]) - len(lines[call_start].lstrip())
                    # Insert uid definition before the call
                    result.insert(call_start, " " * indent + "uid = uuid.uuid4().hex[:8]")
                    i += 1  # skip this line (it's been moved)
                    continue

        result.append(line)
        i += 1

    content = "\n".join(result)

    if content != original:
        with open(full, "w") as f:
            f.write(content)
        return True
    return False


if __name__ == "__main__":
    files = find_broken_files()
    print(f"Checking {len(files)} files with uid definitions")
    fixed = 0
    for fp in files:
        if fix_file(fp):
            fixed += 1
            print(f"  Fixed: {fp}")
    print(f"\nTotal fixed: {fixed}")
