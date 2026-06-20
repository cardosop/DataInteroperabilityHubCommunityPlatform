#!/usr/bin/env python3
"""
Validate GitHub Actions Workflows for Python 3.12+

This script validates that all GitHub Actions workflows are correctly
configured for Python 3.12+ and provides a checklist for manual verification.
"""

import re
import sys
from pathlib import Path

import yaml

# Colors for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")


def check_python_version_in_workflow(workflow_path: Path) -> tuple[bool, list[str], list[str]]:
    """Check if workflow uses Python 3.12+."""
    issues = []
    findings = []

    try:
        with open(workflow_path) as f:
            content = f.read()
            yaml.safe_load(content)
    except Exception as e:
        return False, [f"Error reading workflow: {e}"], []

    # Check for setup-python actions
    python_versions_found = []

    # Search for python-version in setup-python actions
    # First, check for matrix arrays (e.g., ['3.12', '3.13', '3.14'])
    matrix_array_pattern = r"python-version:\s*\[(.*?)\]"
    matrix_matches = re.findall(matrix_array_pattern, content, re.DOTALL | re.IGNORECASE)
    for matrix_match in matrix_matches:
        # Extract versions from array
        versions = re.findall(r'["\']?([3]\.[12-9][0-9]?)["\']?', matrix_match)
        for version in versions:
            if version in ["3.12", "3.13", "3.14"] or (
                version.startswith("3.1") and int(version.split(".")[1]) >= 12
            ):
                findings.append(f"✅ Matrix includes Python {version}")
                python_versions_found.append(version)

    # Then check for single python-version values
    python_version_pattern = r'python-version:\s*["\']?([^"\'\s\[\]]+)["\']?'
    matches = re.findall(python_version_pattern, content, re.IGNORECASE)

    for match in matches:
        # Skip if it's part of a matrix array (already handled)
        if "[" in content[max(0, content.find(match) - 20) : content.find(match) + 20]:
            continue
        if match.startswith("${{"):
            # Matrix variable
            findings.append(f"Uses matrix variable: {match}")
            # Check if matrix is defined
            if "matrix" in content.lower() or "strategy" in content.lower():
                findings.append("Matrix strategy found")
        elif match in ["3.12", "3.13", "3.14"] or (match.startswith("3.1") and len(match) >= 4):
            python_versions_found.append(match)
            if match in ["3.12", "3.13", "3.14"] or (
                match.startswith("3.1") and int(match.split(".")[1]) >= 12
            ):
                findings.append(f"✅ Uses Python {match}")
            else:
                issues.append(f"Uses Python {match} (should be 3.12+)")
        elif match and not match.startswith("["):
            # Only report as issue if it's not a matrix array
            if not any(v in match for v in ["3.12", "3.13", "3.14"]):
                issues.append(f"Uses Python version: {match}")

    # Check for matrix definition
    if "matrix" in content.lower() or "strategy" in content.lower():
        # Try to find matrix python-version
        matrix_pattern = r"matrix:.*?python-version:.*?\[(.*?)\]"
        matrix_match = re.search(matrix_pattern, content, re.DOTALL | re.IGNORECASE)
        if matrix_match:
            matrix_content = matrix_match.group(1)
            if "3.12" in matrix_content:
                findings.append("✅ Matrix includes Python 3.12")
            if "3.13" in matrix_content:
                findings.append("✅ Matrix includes Python 3.13")
            if "3.14" in matrix_content:
                findings.append("✅ Matrix includes Python 3.14")

    # Check if any Python 3.12+ is found
    has_python_312 = any("3.12" in v or "3.13" in v or "3.14" in v for v in python_versions_found)
    has_matrix = "matrix" in content.lower() or "${{" in content

    if not has_python_312 and not has_matrix:
        issues.append("No Python 3.12+ version found")

    return len(issues) == 0, issues, findings


def validate_workflow(workflow_path: Path) -> dict:
    """Validate a single workflow file."""
    workflow_name = workflow_path.stem

    print(f"\n{BOLD}Validating: {workflow_name}{RESET}")

    is_valid, issues, findings = check_python_version_in_workflow(workflow_path)

    if is_valid and findings:
        print_success(f"{workflow_name} is configured for Python 3.12+")
        for finding in findings:
            print(f"  {finding}")
    elif issues:
        print_error(f"{workflow_name} has issues:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print_warning(f"{workflow_name} - Unable to verify Python version")

    return {"name": workflow_name, "valid": is_valid, "issues": issues, "findings": findings}


def main():
    """Main validation function."""
    print_header("GitHub Actions Workflow Validation - Python 3.12+")

    workflows_dir = Path(".github/workflows")

    if not workflows_dir.exists():
        print_error("Workflows directory not found")
        sys.exit(1)

    # Find all workflow files
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

    if not workflow_files:
        print_error("No workflow files found")
        sys.exit(1)

    print_info(f"Found {len(workflow_files)} workflow file(s)")

    results = []
    for workflow_file in sorted(workflow_files):
        result = validate_workflow(workflow_file)
        results.append(result)

    # Summary
    print_header("Validation Summary")

    valid_count = sum(1 for r in results if r["valid"])
    total_count = len(results)

    print(f"\n{BOLD}Total Workflows:{RESET} {total_count}")
    print(f"{GREEN}✅ Valid:{RESET} {valid_count}")
    print(f"{RED}❌ Issues:{RESET} {total_count - valid_count}")

    # Detailed results
    print_header("Detailed Results")

    for result in results:
        print(f"\n{BOLD}{result['name']}{RESET}")
        if result["valid"]:
            print_success("Configuration is valid")
            if result["findings"]:
                for finding in result["findings"]:
                    print(f"  {finding}")
        else:
            print_error("Configuration has issues")
            for issue in result["issues"]:
                print(f"  {issue}")

    # Manual verification checklist
    print_header("Manual Verification Checklist")

    print_info("The following steps require manual execution on GitHub:")
    print("")
    print("1. Push changes to a test branch:")
    print("   git checkout -b test/python-312-upgrade")
    print("   git add .")
    print("   git commit -m 'test: Python 3.12+ upgrade verification'")
    print("   git push origin test/python-312-upgrade")
    print("")
    print("2. Verify GitHub Actions workflows trigger:")
    print("   - Go to GitHub Actions tab")
    print("   - Check that workflows run automatically on push")
    print("   - Verify all workflows start")
    print("")
    print("3. Check workflow logs for Python 3.12+ usage:")
    print("   - Open each workflow run")
    print("   - Check 'Set up Python' step")
    print("   - Verify Python version is 3.12, 3.13, or 3.14")
    print("")
    print("4. Verify test matrix runs for all Python versions:")
    print("   - Check ci.yml workflow")
    print("   - Verify jobs run for Python 3.12, 3.13, 3.14")
    print("   - Check that all matrix jobs complete")
    print("")
    print("5. Verify all CI/CD jobs pass:")
    print("   - Check lint job passes")
    print("   - Check test job passes for all Python versions")
    print("   - Check docker-build job passes")
    print("   - Check e2e job passes")
    print("   - Check openapi-validation job passes")
    print("   - Check security-scan job passes")
    print("")

    # Final status
    if valid_count == total_count:
        print_success("All workflows are configured correctly for Python 3.12+")
        print_info("Ready for GitHub push and manual verification")
        sys.exit(0)
    else:
        print_error("Some workflows need attention")
        print_info("Fix issues above before pushing to GitHub")
        sys.exit(1)


if __name__ == "__main__":
    main()
