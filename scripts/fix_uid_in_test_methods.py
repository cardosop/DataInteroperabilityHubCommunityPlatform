#!/usr/bin/env python3
"""Fix test methods that use {uid} without defining uid."""
import os
import subprocess


def find_files():
    r = subprocess.run(
        ["grep", "-rln", "{uid}", "hub/apps/", "--include=*.py"],
        capture_output=True, text=True, cwd="/app"
    )
    return [f for f in r.stdout.strip().split("\n") if f]


def fix_file(filepath):
    full = os.path.join("/app", filepath)
    with open(full) as f:
        lines = f.readlines()

    original = "".join(lines)
    result = []
    in_method = False
    method_indent = 0
    uid_defined = False
    method_name = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect method start
        if stripped.startswith("def "):
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            uid_defined = False
            method_name = stripped

        # Detect leaving method (new method or class at same/lower indent)
        if in_method and not stripped.startswith("def ") and stripped and not stripped.startswith("#") and not stripped.startswith('"""') and not stripped.startswith("'''"):
            curr_indent = len(line) - len(line.lstrip())
            if curr_indent <= method_indent and stripped:
                in_method = False
                uid_defined = False

        # Check if uid is defined
        if "uid = uuid.uuid4().hex[:8]" in line:
            uid_defined = True

        # If we use {uid} but haven't defined it, add definition
        if in_method and not uid_defined and "{uid}" in line and "uid =" not in line:
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "uid = uuid.uuid4().hex[:8]\n")
            uid_defined = True

        result.append(line)

    content = "".join(result)
    if content != original:
        with open(full, "w") as f:
            f.write(content)
        return True
    return False


if __name__ == "__main__":
    files = find_files()
    print(f"Checking {len(files)} files")
    fixed = 0
    for fp in files:
        if fix_file(fp):
            fixed += 1
            print(f"  Fixed: {fp}")
    print(f"\nTotal fixed: {fixed}")
