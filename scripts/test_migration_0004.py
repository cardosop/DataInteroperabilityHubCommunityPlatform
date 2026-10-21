#!/usr/bin/env python
"""
Test script for migration 0004_remove_datacontract_com_from_original_spec_type.

This script tests the database migration to ensure it works correctly.

Usage:
    python scripts/test_migration_0004.py

Note: This requires a test database. Use Django's test framework for full testing.
"""

import os
import sys
from pathlib import Path

import django

# Setup Django
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from hub.apps.contracts.models import Contract, OriginalSpecType


def test_migration_enum_choices():
    """Test that OriginalSpecType enum only has ODCS"""
    print("Testing OriginalSpecType enum choices...")

    choices = [choice[0] for choice in OriginalSpecType.choices]

    print(f"  Found choices: {choices}")

    assert len(choices) == 1, f"Expected 1 choice (ODCS), found {len(choices)}: {choices}"
    assert choices[0] == OriginalSpecType.ODCS, f"Expected ODCS, found {choices[0]}"
    assert "DATACONTRACT_COM" not in choices, "DATACONTRACT_COM should not be in choices"

    print("  ✓ OriginalSpecType enum only contains ODCS")


def test_migration_sql():
    """Test that migration SQL is correct"""
    print("\nTesting migration SQL...")

    import importlib.util

    migration_path = (
        project_root
        / "hub"
        / "apps"
        / "contracts"
        / "migrations"
        / "0004_remove_datacontract_com_from_original_spec_type.py"
    )

    spec = importlib.util.spec_from_file_location("migration_0004", migration_path)
    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)

    # Check that migration exists
    assert hasattr(migration_module, "Migration"), "Migration class not found"

    migration = migration_module.Migration

    # Check dependencies
    deps_str = str(migration.dependencies)
    assert "0003" in deps_str, f"Migration should depend on 0003, found: {deps_str}"

    # Check operations
    assert len(migration.operations) >= 2, (
        f"Migration should have at least 2 operations, found {len(migration.operations)}"
    )

    print("  ✓ Migration structure is correct")


def test_migration_data_function():
    """Test that migration data function exists and is callable"""
    print("\nTesting migration data function...")

    import importlib.util

    migration_path = (
        project_root
        / "hub"
        / "apps"
        / "contracts"
        / "migrations"
        / "0004_remove_datacontract_com_from_original_spec_type.py"
    )

    spec = importlib.util.spec_from_file_location("migration_0004", migration_path)
    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)

    # Check that data migration function exists
    assert hasattr(migration_module, "migrate_datacontract_com_contracts"), (
        "migrate_datacontract_com_contracts function not found"
    )

    func = migration_module.migrate_datacontract_com_contracts
    assert callable(func), "migrate_datacontract_com_contracts should be callable"

    print("  ✓ Migration data function exists and is callable")


def test_model_field_constraints():
    """Test that Contract model field constraints are correct"""
    print("\nTesting Contract model field constraints...")

    # Get field
    field = Contract._meta.get_field("original_spec_type")

    # Check choices
    choices = field.choices
    choice_values = [choice[0] for choice in choices] if choices else []

    print(f"  Field choices: {choice_values}")

    # Should only have ODCS
    assert len(choice_values) == 1, f"Expected 1 choice, found {len(choice_values)}"
    assert choice_values[0] == OriginalSpecType.ODCS, f"Expected ODCS, found {choice_values[0]}"

    print("  ✓ Contract model field constraints are correct")


def main():
    """Run all migration tests"""
    print("=" * 80)
    print("Testing Migration 0004: Remove DATACONTRACT_COM from OriginalSpecType")
    print("=" * 80)
    print()

    try:
        test_migration_enum_choices()
        test_migration_sql()
        test_migration_data_function()
        test_model_field_constraints()

        print()
        print("=" * 80)
        print("✓ All migration tests passed!")
        print("=" * 80)
        print()
        print("Note: To test the actual migration execution, use Django's test framework:")
        print("  python manage.py test hub.apps.contracts.tests.test_migration")
        print()

        return 0

    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"✗ Migration test failed: {e}")
        print("=" * 80)
        return 1
    except Exception as e:
        print()
        print("=" * 80)
        print(f"✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
