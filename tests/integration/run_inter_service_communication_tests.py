#!/usr/bin/env python3
"""
Standalone test runner for Inter-Service Communication Search tests.

This script runs the tests without requiring pytest or Django, since the tests
only validate JSON report structure.
"""

import importlib.util
import sys
import traceback
from pathlib import Path


def run_tests():
    """Run all tests and report results"""
    # Load the test module directly
    test_file = Path(__file__).parent / "test_inter_service_communication_search.py"
    spec = importlib.util.spec_from_file_location(
        "test_inter_service_communication_search", test_file
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load test module from {test_file}")
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    TestInterServiceCommunicationSearch = test_module.TestInterServiceCommunicationSearch

    test_instance = TestInterServiceCommunicationSearch()
    test_methods = [method for method in dir(test_instance) if method.startswith("test_")]

    passed = 0
    failed = 0
    errors = 0

    print("=" * 80)
    print("Running Inter-Service Communication Search Tests")
    print("=" * 80)
    print()

    for test_method_name in sorted(test_methods):
        test_method = getattr(test_instance, test_method_name)
        print(f"Running {test_method_name}...", end=" ")

        try:
            test_method()
            print("✓ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            traceback.print_exc()
            errors += 1

    print()
    print("=" * 80)
    print("Test Results Summary")
    print("=" * 80)
    print(f"Total tests: {len(test_methods)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print()

    if failed > 0 or errors > 0:
        print("❌ Some tests failed or had errors")
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_tests()
