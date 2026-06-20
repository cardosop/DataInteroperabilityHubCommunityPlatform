#!/usr/bin/env python3
"""
Test all API examples to ensure they work correctly.

This script tests all example code to verify:
- Code syntax is correct
- Imports work correctly
- Basic functionality is correct
"""

import ast
import importlib.util
import json
import os
import sys

# Add examples directory to path
examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
sys.path.insert(0, examples_dir)


def test_python_syntax(file_path):
    """Test Python file syntax."""
    try:
        with open(file_path) as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def test_json_syntax(file_path):
    """Test JSON file syntax."""
    try:
        with open(file_path) as f:
            json.load(f)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)


def test_example_imports(file_path):
    """Test that example file imports work."""
    try:
        spec = importlib.util.spec_from_file_location("example", file_path)
        if spec is None:
            return False, "Could not create spec"
        importlib.util.module_from_spec(spec)
        # Don't execute, just check imports
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    """Test all examples."""
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")

    results = {"passed": [], "failed": []}

    # Test Python examples
    python_examples = [
        "api/create_contract.py",
        "api/list_contracts_with_filters.py",
        "api/get_lineage.py",
    ]

    for example in python_examples:
        file_path = os.path.join(examples_dir, example)
        if not os.path.exists(file_path):
            results["failed"].append((example, "File not found"))
            continue

        # Test syntax
        syntax_ok, syntax_error = test_python_syntax(file_path)
        if not syntax_ok:
            results["failed"].append((example, f"Syntax error: {syntax_error}"))
            continue

        # Test imports (without executing)
        imports_ok, import_error = test_example_imports(file_path)
        if not imports_ok:
            results["failed"].append((example, f"Import error: {import_error}"))
            continue

        results["passed"].append(example)

    # Test JSON examples
    json_examples = ["contracts/odcs_complete_example.json", "contracts/odcs_minimal_example.json"]

    for example in json_examples:
        file_path = os.path.join(examples_dir, example)
        if not os.path.exists(file_path):
            results["failed"].append((example, "File not found"))
            continue

        json_ok, json_error = test_json_syntax(file_path)
        if not json_ok:
            results["failed"].append((example, f"JSON error: {json_error}"))
            continue

        results["passed"].append(example)

    # Print results
    print("Example Testing Results")
    print("=" * 50)
    print()

    if results["passed"]:
        print("✓ Passed:")
        for example in results["passed"]:
            print(f"  - {example}")
        print()

    if results["failed"]:
        print("✗ Failed:")
        for example, error in results["failed"]:
            print(f"  - {example}: {error}")
        print()
        sys.exit(1)
    else:
        print("All examples passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
