#!/usr/bin/env python3
"""
Test Validation Script for Connection Validation Rules

Validates that the connection validation rules implementation is correct
and tests can be run successfully.

This script checks:
1. All required methods exist
2. Method signatures are correct
3. Test files exist and are properly structured
4. Dependencies are available
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def check_method_exists(module, method_name, expected_signature_hints=None):
    """Check if a method exists in a module"""
    if not hasattr(module, method_name):
        print(f"❌ Method {method_name} not found in {module.__name__}")
        return False

    method = getattr(module, method_name)
    if not callable(method):
        print(f"❌ {method_name} exists but is not callable")
        return False

    print(f"✓ Method {method_name} exists")
    return True

def check_test_file_exists(test_file_path):
    """Check if test file exists"""
    if not test_file_path.exists():
        print(f"❌ Test file not found: {test_file_path}")
        return False

    print(f"✓ Test file exists: {test_file_path}")
    return True

def validate_imports():
    """Validate that all required imports work"""
    print("\n=== Validating Imports ===")
    try:
        from hub.apps.integrations.business_rules import (
            MarketplaceIntegrationBusinessRules,
            validate_connection_config,
            validate_connection_access,
            validate_connection_test,
        )
        print("❌ Methods should not be imported directly - they are instance methods")
        return False
    except ImportError:
        pass

    try:
        from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules
        print("✓ MarketplaceIntegrationBusinessRules imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import MarketplaceIntegrationBusinessRules: {e}")
        return False

    try:
        from hub.apps.integrations.models import MarketplaceConnection
        print("✓ MarketplaceConnection imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import MarketplaceConnection: {e}")
        return False

    try:
        from hub.apps.integrations.base import MarketplaceType
        print("✓ MarketplaceType imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import MarketplaceType: {e}")
        return False

    try:
        from hub.apps.core.business_rules.base import ValidationResult
        print("✓ ValidationResult imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import ValidationResult: {e}")
        return False

    return True

def validate_methods():
    """Validate that all required methods exist"""
    print("\n=== Validating Methods ===")
    try:
        from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules

        methods_to_check = [
            'validate_connection_config',
            'validate_connection_access',
            'validate_connection_test',
        ]

        all_exist = True
        for method_name in methods_to_check:
            if not check_method_exists(MarketplaceIntegrationBusinessRules, method_name):
                all_exist = False

        return all_exist
    except Exception as e:
        print(f"❌ Error validating methods: {e}")
        return False

def validate_test_files():
    """Validate that test files exist"""
    print("\n=== Validating Test Files ===")

    test_files = [
        PROJECT_ROOT / "hub" / "apps" / "integrations" / "tests" / "test_connection_validation_rules.py",
        PROJECT_ROOT / "hub" / "apps" / "integrations" / "tests" / "test_connection_validation_integration.py",
    ]

    all_exist = True
    for test_file in test_files:
        if not check_test_file_exists(test_file):
            all_exist = False

    return all_exist

def validate_method_signatures():
    """Validate method signatures are correct"""
    print("\n=== Validating Method Signatures ===")
    try:
        import inspect
        from hub.apps.integrations.business_rules import MarketplaceIntegrationBusinessRules

        # Check validate_connection_config signature
        sig = inspect.signature(MarketplaceIntegrationBusinessRules.validate_connection_config)
        params = list(sig.parameters.keys())
        expected_params = ['self', 'marketplace_type', 'config', 'connection_name', 'tenant_id', 'connection_id']
        if params != expected_params:
            print(f"❌ validate_connection_config signature mismatch. Expected: {expected_params}, Got: {params}")
            return False
        print("✓ validate_connection_config signature is correct")

        # Check validate_connection_access signature
        sig = inspect.signature(MarketplaceIntegrationBusinessRules.validate_connection_access)
        params = list(sig.parameters.keys())
        expected_params = ['self', 'user_id', 'tenant_id']
        if params != expected_params:
            print(f"❌ validate_connection_access signature mismatch. Expected: {expected_params}, Got: {params}")
            return False
        print("✓ validate_connection_access signature is correct")

        # Check validate_connection_test signature
        sig = inspect.signature(MarketplaceIntegrationBusinessRules.validate_connection_test)
        params = list(sig.parameters.keys())
        expected_params = ['self', 'connection', 'test_results']
        if params != expected_params:
            print(f"❌ validate_connection_test signature mismatch. Expected: {expected_params}, Got: {params}")
            return False
        print("✓ validate_connection_test signature is correct")

        return True
    except Exception as e:
        print(f"❌ Error validating signatures: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main validation function"""
    print("=" * 60)
    print("Connection Validation Rules Test Validation")
    print("=" * 60)

    results = []

    # Validate imports
    results.append(("Imports", validate_imports()))

    # Validate methods exist
    results.append(("Methods", validate_methods()))

    # Validate test files exist
    results.append(("Test Files", validate_test_files()))

    # Validate method signatures
    results.append(("Method Signatures", validate_method_signatures()))

    # Print summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{name:20s}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All validations passed!")
        print("\nTo run the tests:")
        print("  docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules")
        print("  docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_integration")
        return 0
    else:
        print("\n❌ Some validations failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

