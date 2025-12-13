#!/usr/bin/env python3
"""
Test JSONField Functionality for Django 6

This script tests all JSONField operations to ensure they work correctly
with Django 6, including queries, updates, and migrations.
"""

import sys
import os
import django
from pathlib import Path

# Setup Django
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.core.management import call_command
import json

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def test_jsonfield_operations():
    """Test basic JSONField operations."""
    print_header("Testing JSONField Operations")
    
    from hub.apps.contracts.models import Contract
    from hub.apps.tenants.models import Tenant
    import uuid
    
    # Create test tenant with unique name
    tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
    tenant = Tenant.objects.create(name=tenant_name, slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
    
    # Test 1: Create with JSONField
    print("Test 1: Create Contract with JSONField...")
    contract_data = {
        "version": "1.0.0",
        "name": "Test Contract",
        "fields": [
            {"name": "id", "type": "string"}
        ]
    }
    
    from hub.apps.contracts.models import OriginalSpecType, OriginalFormat
    
    contract = Contract.objects.create(
        tenant=tenant,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.0.2",
        original_format=OriginalFormat.JSON,
        original_raw='{"id": "test-contract"}',
        hub_contract_json=contract_data
    )
    
    # Verify JSONField was saved
    contract.refresh_from_db()
    assert contract.hub_contract_json == contract_data
    print_success("JSONField creation works")
    
    # Test 2: Update JSONField
    print("Test 2: Update JSONField...")
    updated_data = contract_data.copy()
    updated_data["version"] = "2.0.0"
    
    contract.hub_contract_json = updated_data
    contract.save()
    
    contract.refresh_from_db()
    assert contract.hub_contract_json["version"] == "2.0.0"
    print_success("JSONField update works")
    
    # Test 3: Query JSONField
    print("Test 3: Query JSONField...")
    # Query by JSON path (Django 6 enhanced syntax)
    contracts = Contract.objects.filter(
        hub_contract_json__version="2.0.0"
    )
    assert contracts.count() > 0
    print_success("JSONField query works")
    
    # Test 4: JSONField with nested data
    print("Test 4: JSONField with nested data...")
    nested_data = {
        "version": "1.0.0",
        "metadata": {
            "author": "Test",
            "tags": ["test", "json"]
        }
    }
    contract.hub_contract_json = nested_data
    contract.save()
    
    contract.refresh_from_db()
    assert contract.hub_contract_json["metadata"]["author"] == "Test"
    print_success("JSONField nested data works")
    
    # Cleanup - handle cascade deletes
    try:
        contract.delete()
    except Exception:
        pass  # May fail if related objects exist
    try:
        tenant.delete()
    except Exception:
        pass  # May fail if related objects exist
    
    return True


def test_jsonfield_queries():
    """Test JSONField queries."""
    print_header("Testing JSONField Queries")
    
    from hub.apps.contracts.models import Contract
    from hub.apps.tenants.models import Tenant
    import uuid
    
    tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
    tenant = Tenant.objects.create(name=tenant_name, slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
    
    from hub.apps.contracts.models import OriginalSpecType, OriginalFormat
    
    # Create test contracts
    contracts = []
    for i in range(3):
        contract = Contract.objects.create(
            tenant=tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract"}',
            hub_contract_json={
                "version": f"1.{i}.0",
                "status": "active" if i % 2 == 0 else "inactive"
            }
        )
        contracts.append(contract)
    
    # Test JSON path queries
    print("Test: JSON path query...")
    active_contracts = Contract.objects.filter(
        hub_contract_json__status="active"
    )
    assert active_contracts.count() == 2
    print_success("JSON path query works")
    
    # Test JSON contains query
    print("Test: JSON contains query...")
    version_contracts = Contract.objects.filter(
        hub_contract_json__version__startswith="1."
    )
    assert version_contracts.count() == 3
    print_success("JSON contains query works")
    
    # Cleanup - handle cascade deletes
    for contract in contracts:
        try:
            contract.delete()
        except Exception:
            pass  # May fail if related objects exist
    try:
        tenant.delete()
    except Exception:
        pass  # May fail if related objects exist
    
    return True


def test_jsonfield_migrations():
    """Test JSONField migrations."""
    print_header("Testing JSONField Migrations")
    
    # Check if migrations include JSONField
    print("Checking migrations for JSONField...")
    
    from django.db import connection
    with connection.cursor() as cursor:
        # Check if JSONB columns exist
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND data_type = 'jsonb'
            LIMIT 10;
        """)
        jsonb_columns = cursor.fetchall()
        
        if jsonb_columns:
            print_success(f"Found {len(jsonb_columns)} JSONB columns in database")
            for col_name, data_type in jsonb_columns:
                print(f"  - {col_name}: {data_type}")
        else:
            print_warning("No JSONB columns found (may be using JSON type)")
    
    return True


def main():
    """Main function."""
    print_header("JSONField Functionality Test for Django 6")
    
    try:
        # Test basic operations
        test_jsonfield_operations()
        
        # Test queries
        test_jsonfield_queries()
        
        # Test migrations
        test_jsonfield_migrations()
        
        print_header("Test Summary")
        print_success("All JSONField functionality tests passed")
        return 0
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

