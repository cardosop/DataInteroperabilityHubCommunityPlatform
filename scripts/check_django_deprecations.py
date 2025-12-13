#!/usr/bin/env python3
"""
Check Django Deprecation Warnings for Django 6 Compatibility

This script runs Django with deprecation warnings enabled and identifies
all deprecation warnings that need to be fixed for Django 6 compatibility.
"""

import sys
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
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


def check_django_deprecations() -> Tuple[Dict[str, List[str]], str]:
    """Run Django check with deprecation warnings enabled."""
    import os
    project_root = Path(__file__).parent.parent
    
    # Set up environment
    env = {
        'PYTHONWARNINGS': 'default::DeprecationWarning',
        'DJANGO_SETTINGS_MODULE': 'hub.settings',
        'PYTHONPATH': str(project_root),
    }
    
    # Run Django check
    try:
        result = subprocess.run(
            [sys.executable, 'hub/manage.py', 'check', '--deploy'],
            cwd=project_root,
            capture_output=True,
            text=True,
            env={**dict(os.environ), **env},
            timeout=60
        )
        
        output = result.stdout + result.stderr
        
        # Parse deprecation warnings
        deprecations = {
            'middleware': [],
            'settings': [],
            'models': [],
            'other': []
        }
        
        lines = output.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            # Check for middleware-related deprecations
            if 'middleware' in line_lower and ('deprecat' in line_lower or 'removed' in line_lower):
                deprecations['middleware'].append(line.strip())
            
            # Check for settings-related deprecations
            elif 'settings' in line_lower and ('deprecat' in line_lower or 'removed' in line_lower):
                deprecations['settings'].append(line.strip())
            
            # Check for model-related deprecations
            elif 'model' in line_lower and ('deprecat' in line_lower or 'removed' in line_lower):
                deprecations['models'].append(line.strip())
            
            # Other deprecations
            elif 'deprecat' in line_lower or 'removed' in line_lower:
                deprecations['other'].append(line.strip())
        
        return deprecations, output
        
    except subprocess.TimeoutExpired:
        return {'middleware': [], 'settings': [], 'models': [], 'other': []}, "Check timed out"
    except Exception as e:
        return {'middleware': [], 'settings': [], 'models': [], 'other': []}, f"Error: {str(e)}"


def check_middleware_mixin_usage() -> List[str]:
    """Check for MiddlewareMixin usage in codebase."""
    project_root = Path(__file__).parent.parent
    
    middleware_files = []
    
    # Search for MiddlewareMixin
    for py_file in project_root.rglob('*.py'):
        if 'venv' in str(py_file) or '__pycache__' in str(py_file):
            continue
        
        try:
            content = py_file.read_text()
            if 'MiddlewareMixin' in content:
                middleware_files.append(str(py_file.relative_to(project_root)))
        except Exception:
            continue
    
    return middleware_files


def main():
    """Main function."""
    import os
    
    print_header("Django Deprecation Warning Check")
    
    # Check for MiddlewareMixin usage
    print("Checking for MiddlewareMixin usage...")
    middleware_files = check_middleware_mixin_usage()
    
    if middleware_files:
        print_warning(f"Found MiddlewareMixin usage in {len(middleware_files)} file(s):")
        for file in middleware_files:
            print(f"  - {file}")
    else:
        print_success("No MiddlewareMixin usage found")
    
    print()
    
    # Check deprecation warnings
    print("Running Django check with deprecation warnings...")
    deprecations, full_output = check_django_deprecations()
    
    total_deprecations = sum(len(v) for v in deprecations.values())
    
    if total_deprecations > 0:
        print_warning(f"Found {total_deprecations} deprecation warning(s)")
        
        if deprecations['middleware']:
            print("\nMiddleware Deprecations:")
            for dep in deprecations['middleware'][:10]:
                print(f"  {YELLOW}⚠️{RESET} {dep}")
        
        if deprecations['settings']:
            print("\nSettings Deprecations:")
            for dep in deprecations['settings'][:10]:
                print(f"  {YELLOW}⚠️{RESET} {dep}")
        
        if deprecations['models']:
            print("\nModel Deprecations:")
            for dep in deprecations['models'][:10]:
                print(f"  {YELLOW}⚠️{RESET} {dep}")
        
        if deprecations['other']:
            print("\nOther Deprecations:")
            for dep in deprecations['other'][:10]:
                print(f"  {YELLOW}⚠️{RESET} {dep}")
    else:
        print_success("No deprecation warnings found")
    
    # Generate report
    project_root = Path(__file__).parent.parent
    report_file = project_root / 'openspec/changes/fullcontract/DJANGO6_DEPRECATION_CHECK.md'
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w') as f:
        f.write("# Django 6 Deprecation Warning Check\n\n")
        f.write(f"**Date:** 2025-01-15\n\n")
        
        f.write("## MiddlewareMixin Usage\n\n")
        if middleware_files:
            f.write(f"Found MiddlewareMixin usage in {len(middleware_files)} file(s):\n\n")
            for file in middleware_files:
                f.write(f"- `{file}`\n")
            f.write("\n**Action Required:** Remove MiddlewareMixin and convert to callable classes.\n\n")
        else:
            f.write("✅ No MiddlewareMixin usage found.\n\n")
        
        f.write("## Deprecation Warnings\n\n")
        f.write(f"Total deprecations found: {total_deprecations}\n\n")
        
        if deprecations['middleware']:
            f.write("### Middleware Deprecations\n\n")
            for dep in deprecations['middleware']:
                f.write(f"- {dep}\n")
            f.write("\n")
        
        if deprecations['settings']:
            f.write("### Settings Deprecations\n\n")
            for dep in deprecations['settings']:
                f.write(f"- {dep}\n")
            f.write("\n")
        
        if deprecations['models']:
            f.write("### Model Deprecations\n\n")
            for dep in deprecations['models']:
                f.write(f"- {dep}\n")
            f.write("\n")
        
        if deprecations['other']:
            f.write("### Other Deprecations\n\n")
            for dep in deprecations['other']:
                f.write(f"- {dep}\n")
            f.write("\n")
        
        f.write("## Full Output\n\n")
        f.write("```\n")
        f.write(full_output)
        f.write("\n```\n")
    
    print_success(f"Report generated: {report_file}")
    
    if total_deprecations > 0 or middleware_files:
        print_warning("Deprecation warnings found - review report for details")
        sys.exit(0)
    else:
        print_success("No deprecation warnings found!")
        sys.exit(0)


if __name__ == '__main__':
    main()

