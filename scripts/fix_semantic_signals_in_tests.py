#!/usr/bin/env python3
"""
Script to add semantic signal disconnection to test files.

This script adds signal disconnection in setUp() and reconnection in tearDown()
to all test files that create Asset/Contract objects but don't already have it.
"""
import os
import re
from pathlib import Path

# Signal disconnection code to add in setUp()
SETUP_CODE = """        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved
            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
"""

# Signal reconnection code to add in tearDown()
TEARDOWN_CODE = """    def tearDown(self):
        \"\"\"Reconnect signals after test\"\"\"
        from django.db.models.signals import post_save
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved
            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
"""


def needs_signal_fix(file_path):
    """Check if file needs signal disconnection fix"""
    with open(file_path, "r") as f:
        content = f.read()

    # Check if file creates Asset/Contract objects
    has_asset_contract_creation = (
        "Asset.objects.create" in content or "Contract.objects.create" in content
    )

    # Check if already has signal disconnection
    has_signal_disconnect = (
        "post_save.disconnect(contract_saved" in content
        or "post_save.disconnect(asset_saved" in content
    )

    # Check if it's a test file
    is_test_file = "TestCase" in content or "TransactionTestCase" in content

    return has_asset_contract_creation and is_test_file and not has_signal_disconnect


def add_signal_disconnect_to_setup(content):
    """Add signal disconnection to setUp method"""
    # Find setUp method
    setup_pattern = (
        r'(def setUp\(self\):.*?"""[^"]*"""\s*\n\s*)(.*?)(self\.tenant|self\.client|self\.user)'
    )

    def replace_setup(match):
        setup_def = match.group(1)
        setup_body_start = match.group(2)
        first_line = match.group(3)

        # Check if signal disconnection already exists
        if "post_save.disconnect" in match.group(0):
            return match.group(0)

        # Add signal disconnection after setUp definition
        return setup_def + SETUP_CODE + "\n" + setup_body_start + first_line

    new_content = re.sub(setup_pattern, replace_setup, content, flags=re.DOTALL)

    # If pattern didn't match, try simpler pattern
    if new_content == content:
        # Look for setUp with just self.tenant or self.user
        simple_pattern = (
            r'(def setUp\(self\):\s*\n\s*"""[^"]*"""\s*\n\s*)(self\.tenant|self\.user|self\.client)'
        )

        def replace_simple(match):
            setup_def = match.group(1)
            first_var = match.group(2)
            return setup_def + SETUP_CODE + "\n        " + first_var

        new_content = re.sub(simple_pattern, replace_simple, content, flags=re.DOTALL)

    return new_content


def add_teardown_method(content):
    """Add tearDown method if it doesn't exist"""
    # Check if tearDown already exists
    if "def tearDown(self):" in content:
        # Check if it already has signal reconnection
        if "post_save.connect(contract_saved" in content:
            return content

        # Add signal reconnection to existing tearDown
        teardown_pattern = (
            r'(def tearDown\(self\):.*?"""[^"]*"""\s*\n\s*)(.*?)(\n\n    def |\nclass |\Z)'
        )

        def replace_teardown(match):
            teardown_def = match.group(1)
            teardown_body = match.group(2)
            next_section = match.group(3)

            # Add signal reconnection at the end of tearDown
            signal_code = (
                "\n        "
                + TEARDOWN_CODE.split("\n", 1)[1].replace("    def tearDown", "").strip()
            )
            return teardown_def + teardown_body + signal_code + next_section

        new_content = re.sub(teardown_pattern, replace_teardown, content, flags=re.DOTALL)
        return new_content

    # Add tearDown method at the end of the class
    class_pattern = r"(class \w+.*?:\s*\n.*?)(\n\nclass |\n\n\Z)"

    def add_teardown_to_class(match):
        class_body = match.group(1)
        next_class = match.group(2)

        # Find last method in class
        last_method_pattern = r"(\n    def \w+\([^)]*\):.*?)(\n\nclass |\n\n\Z)"
        last_match = list(re.finditer(last_method_pattern, class_body, flags=re.DOTALL))

        if last_match:
            last_method = last_match[-1]
            return class_body[: last_method.end(1)] + "\n" + TEARDOWN_CODE + next_class
        else:
            return class_body + "\n" + TEARDOWN_CODE + next_class

    new_content = re.sub(class_pattern, add_teardown_to_class, content, flags=re.DOTALL)
    return new_content


def fix_test_file(file_path):
    """Fix a single test file"""
    print(f"Processing: {file_path}")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Add signal disconnection to setUp
    content = add_signal_disconnect_to_setup(content)

    # Add tearDown method
    content = add_teardown_method(content)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  ✅ Fixed: {file_path}")
        return True
    else:
        print(f"  ⏭️  Skipped (no changes needed): {file_path}")
        return False


def main():
    """Main function"""
    project_root = Path(__file__).parent.parent
    integrations_tests = project_root / "hub" / "apps" / "integrations" / "tests"
    semantic_tests = project_root / "hub" / "apps" / "semantic" / "tests"

    files_to_fix = []

    # Find files in integrations/tests
    for test_file in integrations_tests.rglob("test_*.py"):
        if needs_signal_fix(test_file):
            files_to_fix.append(test_file)

    # Find files in semantic/tests
    for test_file in semantic_tests.rglob("test_*.py"):
        if needs_signal_fix(test_file):
            files_to_fix.append(test_file)

    print(f"Found {len(files_to_fix)} files that need fixing")
    print()

    fixed_count = 0
    for file_path in files_to_fix:
        if fix_test_file(file_path):
            fixed_count += 1

    print()
    print(f"Fixed {fixed_count} out of {len(files_to_fix)} files")


if __name__ == "__main__":
    main()
