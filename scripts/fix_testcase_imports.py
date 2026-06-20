#!/usr/bin/env python
"""
Script to add pytest.mark.django_db(transaction=True) to all TestCase classes.

This fixes the threading issue between Django's TestCase and pytest-django.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def fix_testcase_file(file_path: Path):
    """Add pytestmark to TestCase classes in a file"""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Skip if already has pytestmark
        if "pytestmark = pytest.mark.django_db" in content:
            return False

        # Skip if no TestCase import
        if (
            "from django.test import TestCase" not in content
            and "from django.test import TestCase," not in content
        ):
            return False

        # Skip if no TestCase classes
        if "class " not in content or "TestCase" not in content:
            return False

        # Add pytest import if not present
        if "import pytest" not in content:
            # Find the first import line
            lines = content.split("\n")
            import_idx = None
            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    import_idx = i
                    break

            if import_idx is not None:
                lines.insert(import_idx, "import pytest")
                content = "\n".join(lines)

        # Find where to insert pytestmark (after imports, before first class)
        lines = content.split("\n")
        insert_idx = None

        # Find the last import/from statement
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("import ") or lines[i].startswith("from "):
                insert_idx = i + 1
                break

        if insert_idx is None:
            return False

        # Skip blank lines after imports
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1

        # Insert pytestmark
        pytestmark_line = "pytestmark = pytest.mark.django_db(transaction=True)"

        # Check if we need to add a blank line before
        if insert_idx > 0 and lines[insert_idx - 1].strip() != "":
            lines.insert(insert_idx, "")
            insert_idx += 1

        lines.insert(insert_idx, pytestmark_line)
        lines.insert(insert_idx, "")

        new_content = "\n".join(lines)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Find and fix all TestCase files"""
    test_files = list(PROJECT_ROOT.glob("hub/apps/**/test_*.py"))
    test_files.extend(PROJECT_ROOT.glob("tests/**/test_*.py"))

    fixed = 0
    skipped = 0

    for test_file in test_files:
        if fix_testcase_file(test_file):
            print(f"✅ Fixed: {test_file.relative_to(PROJECT_ROOT)}")
            fixed += 1
        else:
            skipped += 1

    print(f"\n✅ Fixed {fixed} files")
    print(f"⏭️  Skipped {skipped} files (already fixed or no TestCase)")


if __name__ == "__main__":
    main()
