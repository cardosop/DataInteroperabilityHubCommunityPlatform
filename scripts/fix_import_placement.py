#!/usr/bin/env python3
"""Fix import uuid placement - ensure it's not inside multi-line imports."""

import os
import subprocess


def find_files():
    r = subprocess.run(
        ["grep", "-rln", "import uuid", "hub/apps/", "--include=*.py"],
        check=False,
        capture_output=True,
        text=True,
        cwd="/app",
    )
    return [f for f in r.stdout.strip().split("\n") if f]


def fix_file(filepath):
    full = os.path.join("/app", filepath)
    with open(full) as f:
        lines = f.readlines()

    original = "".join(lines)
    # Check for syntax errors first
    try:
        compile(original, filepath, "exec")
        return False  # No syntax error, skip
    except SyntaxError:
        pass

    # Find and fix misplaced "import uuid" lines
    result = []
    uuid_import_needed = False
    uuid_already_at_top = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "import uuid":
            # Check if we're inside a multi-line import (previous line ends with ( or ,)
            if i > 0:
                prev = lines[i - 1].rstrip()
                if prev.endswith("(") or prev.endswith(","):
                    # Inside a multi-line import! Skip this line
                    uuid_import_needed = True
                    continue
                else:
                    uuid_already_at_top = True
        result.append(line)

    if uuid_import_needed and not uuid_already_at_top:
        # Add import uuid at the proper place (after last clean import)
        final = []
        last_import = 0
        for i, line in enumerate(result):
            stripped = line.strip()
            if (
                stripped.startswith("import ") or stripped.startswith("from ")
            ) and "(" not in stripped:
                last_import = i
        for i, line in enumerate(result):
            final.append(line)
            if i == last_import:
                final.append("import uuid\n")
        result = final

    content = "".join(result)
    if content != original:
        # Verify it compiles
        try:
            compile(content, filepath, "exec")
        except SyntaxError:
            # Still broken, try different approach - just add at top after first import
            result2 = []
            added = False
            for line in lines:
                stripped = line.strip()
                if stripped == "import uuid" and not added:
                    # Skip misplaced import
                    continue
                result2.append(line)
                if (
                    not added
                    and (stripped.startswith("import ") or stripped.startswith("from "))
                    and "(" not in stripped
                    and ")" not in stripped
                ) and stripped != "import uuid":
                    result2.append("import uuid\n")
                    added = True
            content = "".join(result2)
            try:
                compile(content, filepath, "exec")
            except SyntaxError:
                return False

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
