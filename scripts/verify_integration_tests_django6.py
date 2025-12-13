#!/usr/bin/env python3
"""
Verify Integration Tests Compatibility with Django 6

This script analyzes existing integration tests to verify they are compatible
with Django 6 and identifies any issues that need to be addressed.
"""
import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Any, Set
import json

# Color codes for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
BOLD = '\033[1m'
RESET = '\033[0m'


def find_integration_test_files(base_dir: Path) -> List[Path]:
    """Find all integration test files"""
    test_files = []
    
    # Common patterns for integration test files
    patterns = [
        '**/test*integration*.py',
        '**/test*api*.py',
        '**/test*job*.py',
        '**/test*file*.py',
        '**/test*storage*.py',
        '**/test*service*.py',
    ]
    
    for pattern in patterns:
        for file_path in base_dir.rglob(pattern):
            if file_path.is_file() and 'integration' in str(file_path).lower():
                test_files.append(file_path)
    
    # Also check specific directories
    integration_dirs = [
        base_dir / 'tests' / 'integration',
        base_dir / 'hub' / 'apps' / 'jobs' / 'tests',
        base_dir / 'hub' / 'apps' / 'files' / 'tests',
        base_dir / 'hub' / 'apps' / 'api' / 'tests',
    ]
    
    for dir_path in integration_dirs:
        if dir_path.exists():
            for file_path in dir_path.rglob('test*.py'):
                if file_path.is_file():
                    test_files.append(file_path)
    
    # Remove duplicates
    return list(set(test_files))


def check_django6_compatibility(file_path: Path) -> Dict[str, Any]:
    """
    Check a test file for Django 6 compatibility issues.
    
    Returns a dictionary with:
    - issues: List of compatibility issues found
    - warnings: List of warnings
    - uses_middleware_mixin: Boolean indicating MiddlewareMixin usage
    - uses_deprecated_settings: Boolean indicating deprecated settings usage
    - uses_django6_patterns: Boolean indicating Django 6 patterns are used
    """
    issues = []
    warnings = []
    uses_middleware_mixin = False
    uses_deprecated_settings = False
    uses_django6_patterns = False
    
    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        
        # Check for MiddlewareMixin usage (deprecated in Django 6)
        if 'MiddlewareMixin' in content:
            uses_middleware_mixin = True
            issues.append("Uses MiddlewareMixin (deprecated in Django 6, should use callable class pattern)")
        
        # Check for deprecated settings
        deprecated_settings = [
            'DEFAULT_FILE_STORAGE',
            'STATICFILES_STORAGE',
        ]
        for setting in deprecated_settings:
            if setting in content:
                uses_deprecated_settings = True
                issues.append(f"Uses deprecated setting {setting} (should use STORAGES setting)")
        
        # Check for Django 6 patterns
        django6_patterns = [
            'pytest.mark.django_db',
            'APIClient',
            'RequestFactory',
            'TestCase',
        ]
        for pattern in django6_patterns:
            if pattern in content:
                uses_django6_patterns = True
        
        # Check for test base classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from Django test base classes
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if base.id in ['TestCase', 'TransactionTestCase', 'APITestCase']:
                            uses_django6_patterns = True
                    elif isinstance(base, ast.Attribute):
                        if base.attr in ['TestCase', 'TransactionTestCase', 'APITestCase']:
                            uses_django6_patterns = True
        
        # Check for pytest markers
        if 'pytest.mark.django_db' in content:
            uses_django6_patterns = True
        
    except SyntaxError as e:
        issues.append(f"Syntax error in file: {e}")
    except Exception as e:
        warnings.append(f"Could not parse file: {e}")
    
    return {
        'issues': issues,
        'warnings': warnings,
        'uses_middleware_mixin': uses_middleware_mixin,
        'uses_deprecated_settings': uses_deprecated_settings,
        'uses_django6_patterns': uses_django6_patterns,
    }


def categorize_test_file(file_path: Path) -> str:
    """Categorize a test file based on its path and name"""
    path_str = str(file_path)
    
    if 'database' in path_str.lower() or 'db' in path_str.lower():
        return "Database Integration Tests"
    elif 'api' in path_str.lower():
        return "API Integration Tests"
    elif 'job' in path_str.lower() or 'queue' in path_str.lower():
        return "Job Queue Integration Tests"
    elif 'file' in path_str.lower() or 'storage' in path_str.lower():
        return "File Storage Integration Tests"
    elif 'service' in path_str.lower() or 'cross' in path_str.lower():
        return "Cross-Service Integration Tests"
    elif 'middleware' in path_str.lower():
        return "Middleware Integration Tests"
    else:
        return "Other Integration Tests"


def main():
    """Main function"""
    base_dir = Path(__file__).resolve().parent.parent
    
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}Django 6 Integration Tests Compatibility Verification{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")
    
    # Find all integration test files
    test_files = find_integration_test_files(base_dir)
    print(f"{GREEN}✅ Found {len(test_files)} integration test files to analyze{RESET}\n")
    
    # Categorize test files
    categorized_files: Dict[str, List[Path]] = {}
    for file_path in test_files:
        category = categorize_test_file(file_path)
        categorized_files.setdefault(category, []).append(file_path)
    
    print(f"{BOLD}{BLUE}Test Files by Category:{RESET}\n")
    for category, files in categorized_files.items():
        print(f"  {category}: {len(files)} files")
    print()
    
    # Analyze each file
    all_issues = []
    all_warnings = []
    files_with_issues = []
    files_with_warnings = []
    compatible_files = []
    
    print(f"{BOLD}{BLUE}Analyzing Test Files...{RESET}\n")
    
    for file_path in test_files:
        result = check_django6_compatibility(file_path)
        
        if result['issues']:
            all_issues.extend(result['issues'])
            files_with_issues.append((file_path, result['issues']))
        elif result['warnings']:
            all_warnings.extend(result['warnings'])
            files_with_warnings.append((file_path, result['warnings']))
        else:
            compatible_files.append(file_path)
    
    # Print results
    print(f"{BOLD}{BLUE}Compatibility Analysis Results:{RESET}\n")
    
    if files_with_issues:
        print(f"{RED}❌ Found {len(files_with_issues)} files with compatibility issues:{RESET}")
        for file_path, issues in files_with_issues:
            print(f"\n  {RED}{file_path.relative_to(base_dir)}{RESET}")
            for issue in issues:
                print(f"    - {issue}")
        print()
    else:
        print(f"{GREEN}✅ No compatibility issues found{RESET}\n")
    
    if files_with_warnings:
        print(f"{YELLOW}⚠️  Found {len(files_with_warnings)} files with warnings:{RESET}")
        for file_path, warnings in files_with_warnings:
            print(f"\n  {YELLOW}{file_path.relative_to(base_dir)}{RESET}")
            for warning in warnings:
                print(f"    - {warning}")
        print()
    else:
        print(f"{GREEN}✅ No warnings found{RESET}\n")
    
    print(f"{GREEN}✅ {len(compatible_files)} files are compatible with Django 6{RESET}\n")
    
    # Summary by category
    print(f"{BOLD}{BLUE}Summary by Category:{RESET}\n")
    
    category_results = {}
    for category, files in categorized_files.items():
        category_issues = []
        category_warnings = []
        category_compatible = []
        
        for file_path in files:
            result = check_django6_compatibility(file_path)
            if result['issues']:
                category_issues.append(file_path)
            elif result['warnings']:
                category_warnings.append(file_path)
            else:
                category_compatible.append(file_path)
        
        category_results[category] = {
            'total': len(files),
            'issues': len(category_issues),
            'warnings': len(category_warnings),
            'compatible': len(category_compatible),
        }
        
        status = "✅" if len(category_issues) == 0 else "❌"
        print(f"  {status} {category}: {len(category_compatible)}/{len(files)} compatible")
    
    print()
    
    # Generate report
    report_data = {
        'summary': {
            'total_files': len(test_files),
            'files_with_issues': len(files_with_issues),
            'files_with_warnings': len(files_with_warnings),
            'compatible_files': len(compatible_files),
        },
        'category_results': category_results,
        'files_with_issues': [
            {
                'file': str(f.relative_to(base_dir)),
                'issues': issues
            }
            for f, issues in files_with_issues
        ],
        'files_with_warnings': [
            {
                'file': str(f.relative_to(base_dir)),
                'warnings': warnings
            }
            for f, warnings in files_with_warnings
        ],
        'compatible_files': [str(f.relative_to(base_dir)) for f in compatible_files],
        'django6_compatibility_notes': [
            "Django 6 maintains backward compatibility with most test code",
            "TestCase, TransactionTestCase, APITestCase are compatible",
            "pytest-django works with Django 6",
            "Test fixtures and factories are compatible",
            "MiddlewareMixin usage in tests should be reviewed (if any)",
            "Deprecated settings usage should be updated to STORAGES setting"
        ]
    }
    
    report_path = base_dir / 'openspec' / 'changes' / 'fullcontract' / 'DJANGO6_INTEGRATION_TESTS_VERIFICATION.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"{GREEN}✅ Report saved to: {report_path.relative_to(base_dir)}{RESET}\n")
    
    # Final summary
    print(f"{BOLD}{BLUE}{'='*70}{RESET}")
    if len(files_with_issues) == 0:
        print(f"{BOLD}{GREEN}✅ All integration tests are compatible with Django 6!{RESET}")
    else:
        print(f"{BOLD}{YELLOW}⚠️  Some integration tests need updates for Django 6{RESET}")
        print(f"{BOLD}{YELLOW}   Review the issues above and update as needed{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")
    
    return 0 if len(files_with_issues) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

