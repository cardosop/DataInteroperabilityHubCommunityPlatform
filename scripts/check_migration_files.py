#!/usr/bin/env python3
"""
Check tenant migration files for correctness.

This script checks migration files without requiring database connection.
"""
import os
import re
import sys
from pathlib import Path

def check_migration_files():
    """Check tenant migration files."""
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "hub" / "apps" / "tenants" / "migrations"
    
    errors = []
    warnings = []
    
    # Check for duplicate 0002
    migration_files = list(migrations_dir.glob("*.py"))
    migration_files = [f for f in migration_files if f.name.startswith("000")]
    
    migration_numbers = {}
    for f in migration_files:
        match = re.match(r"(\d+)_", f.name)
        if match:
            num = match.group(1)
            if num in migration_numbers:
                errors.append(f"Duplicate migration number {num}: {migration_numbers[num].name} and {f.name}")
            else:
                migration_numbers[num] = f
    
    # Check for 0002_add_sso_config (should be 0004)
    if (migrations_dir / "0002_add_sso_config.py").exists():
        errors.append("Found 0002_add_sso_config.py - should be renamed to 0004_add_sso_config.py")
    
    # Check for 0004_add_sso_config
    if not (migrations_dir / "0004_add_sso_config.py").exists():
        errors.append("Missing 0004_add_sso_config.py")
    
    # Check migration chain
    required_files = [
        "0001_initial.py",
        "0002_add_tenant_config.py",
        "0003_rename_tenant_configs_tenant_idx_tenant_conf_tenant__37e737_idx_and_more.py",
        "0004_add_sso_config.py"
    ]
    
    for filename in required_files:
        if not (migrations_dir / filename).exists():
            errors.append(f"Missing required migration file: {filename}")
    
    # Check dependencies
    if (migrations_dir / "0004_add_sso_config.py").exists():
        content = (migrations_dir / "0004_add_sso_config.py").read_text()
        if "0003_rename_tenant_configs" not in content:
            errors.append("0004_add_sso_config.py should depend on 0003_rename_tenant_configs...")
    
    if (migrations_dir / "0002_add_tenant_config.py").exists():
        content = (migrations_dir / "0002_add_tenant_config.py").read_text()
        if "0001_initial" not in content:
            errors.append("0002_add_tenant_config.py should depend on 0001_initial")
    
    # Print results
    if errors:
        print("❌ ERRORS FOUND:")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("✅ All migration files are correct!")
        print("\nMigration chain:")
        for filename in sorted(required_files):
            if (migrations_dir / filename).exists():
                print(f"  ✓ {filename}")
        return 0

if __name__ == "__main__":
    sys.exit(check_migration_files())

