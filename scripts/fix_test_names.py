#!/usr/bin/env python3
"""Fix hardcoded tenant/user names in TransactionTestCase test files.

Replaces fixed names like "Test Tenant" / "test-tenant" / "test@example.com"
with UUID-based unique names to prevent IntegrityError collisions in --reuse-db mode.
"""
import os
import re
import subprocess


def find_target_files():
    """Find files with transaction=True AND fixed tenant names."""
    r1 = subprocess.run(
        ["grep", "-rln", "transaction=True", "hub/apps/", "--include=*.py"],
        capture_output=True, text=True, cwd="/app"
    )
    tx = set(r1.stdout.strip().split("\n")) if r1.stdout.strip() else set()

    r2 = subprocess.run(
        ["grep", "-rln", '"Test Tenant"', "hub/apps/", "--include=*.py"],
        capture_output=True, text=True, cwd="/app"
    )
    tn = set(r2.stdout.strip().split("\n")) if r2.stdout.strip() else set()

    return sorted(tx & tn)


def fix_file(filepath):
    """Fix a single file."""
    full = os.path.join("/app", filepath)
    if not os.path.exists(full):
        return False

    with open(full) as f:
        content = f.read()

    # Already fixed?
    if 'f"Test Tenant {uid}"' in content:
        return False

    original = content

    # Add import uuid
    if "import uuid" not in content:
        lines = content.split("\n")
        last_imp = 0
        for i, ln in enumerate(lines):
            if ln.startswith("import ") or ln.startswith("from "):
                last_imp = i
        lines.insert(last_imp + 1, "import uuid")
        content = "\n".join(lines)

    # Replace fixed names
    content = content.replace('name="Test Tenant"', 'name=f"Test Tenant {uid}"')
    content = content.replace("name='Test Tenant'", "name=f'Test Tenant {uid}'")
    content = content.replace('slug="test-tenant"', 'slug=f"test-tenant-{uid}"')
    content = content.replace("slug='test-tenant'", "slug=f'test-tenant-{uid}'")

    # Replace fixed emails near tenant/user creation
    content = content.replace('email="test@example.com"', 'email=f"test-{uid}@example.com"')
    content = content.replace('email="user@example.com"', 'email=f"user-{uid}@example.com"')

    if content == original:
        return False

    # Ensure uid is defined in each setUp that uses it
    lines = content.split("\n")
    result = []
    in_setup = False
    uid_defined_in_setup = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("def setUp("):
            in_setup = True
            uid_defined_in_setup = False
        elif in_setup and stripped.startswith("def ") and not stripped.startswith("def setUp"):
            in_setup = False
            uid_defined_in_setup = False

        if in_setup and "uid = uuid.uuid4().hex[:8]" in line:
            uid_defined_in_setup = True

        if in_setup and not uid_defined_in_setup and "{uid}" in line:
            indent = len(line) - len(line.lstrip())
            result.append(" " * indent + "uid = uuid.uuid4().hex[:8]")
            uid_defined_in_setup = True

        result.append(line)

    content = "\n".join(result)

    with open(full, "w") as f:
        f.write(content)
    return True


if __name__ == "__main__":
    files = find_target_files()
    print(f"Found {len(files)} candidate files")
    fixed = 0
    for fp in files:
        if fix_file(fp):
            fixed += 1
            print(f"  Fixed: {fp}")
    print(f"\nTotal fixed: {fixed}/{len(files)}")
