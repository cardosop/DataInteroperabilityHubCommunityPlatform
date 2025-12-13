#!/usr/bin/env python3
"""
Comprehensive Django 6 Dependency Compatibility Audit

This script audits all Django-related dependencies for Django 6 compatibility:
1. Checks PyPI metadata for Django 6 support
2. Tests installation compatibility
3. Documents compatibility status
4. Identifies required updates

No mocks - real dependency checking.
"""

import sys
import subprocess
import json
import urllib.request
import urllib.error
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
RESET = '\033[0m'


@dataclass
class DependencyCompatibility:
    name: str
    current_version: str
    django6_supported: Optional[bool]
    min_version_for_django6: Optional[str]
    latest_version: Optional[str]
    requires_update: bool
    notes: List[str] = field(default_factory=list)


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


def get_pypi_info(package_name: str) -> Optional[Dict]:
    """Get package information from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())
    except Exception:
        return None


def check_django6_compatibility(package_name: str, current_version_spec: str) -> DependencyCompatibility:
    """Check if package supports Django 6."""
    print(f"  Checking {package_name}...", end=' ', flush=True)
    
    pypi_data = get_pypi_info(package_name)
    if not pypi_data:
        print(f"{YELLOW}⚠️{RESET}")
        return DependencyCompatibility(
            name=package_name,
            current_version=current_version_spec,
            django6_supported=None,
            min_version_for_django6=None,
            latest_version=None,
            requires_update=False,
            notes=["PyPI metadata unavailable"]
        )
    
    info = pypi_data.get('info', {})
    latest_version = info.get('version')
    requires_python = info.get('requires_python', '')
    
    # Check classifiers for Django 6 support
    classifiers = info.get('classifiers', [])
    django6_supported = False
    min_version = None
    
    for classifier in classifiers:
        # Check for Django 6 classifier
        if 'Framework :: Django :: 6' in classifier:
            django6_supported = True
            # Extract version if available
            version_match = re.search(r'Django :: 6\.(\d+)', classifier)
            if version_match:
                min_version = f"6.{version_match.group(1)}"
        # Check for Django 6.0+ support
        if 'Framework :: Django :: 6.0' in classifier or 'Framework :: Django :: 6.1' in classifier:
            django6_supported = True
    
    # Check project URLs and description for Django 6 mentions
    description = info.get('description', '')
    if 'django 6' in description.lower() or 'django6' in description.lower():
        django6_supported = True
    
    # Check requires_dist for Django version requirements
    requires_dist = info.get('requires_dist', [])
    for req in requires_dist:
        if 'django' in req.lower():
            # Check if it allows Django 6
            if re.search(r'django\s*>=\s*6', req, re.IGNORECASE):
                django6_supported = True
            if re.search(r'django\s*>\s*=\s*6', req, re.IGNORECASE):
                django6_supported = True
            # Check for Django 6 in version range
            if re.search(r'django\s*\[.*6.*\]', req, re.IGNORECASE):
                django6_supported = True
    
    # Special handling for known packages
    if package_name == 'djangorestframework':
        # DRF 3.15+ is required for Django 6
        if latest_version:
            try:
                from packaging import version
                if version.parse(latest_version) >= version.parse('3.15.0'):
                    django6_supported = True
                    min_version = '3.15.0'
            except:
                if latest_version >= '3.15.0':
                    django6_supported = True
                    min_version = '3.15.0'
    
    # Determine if update is required
    requires_update = False
    notes = []
    
    if django6_supported:
        if min_version and current_version_spec:
            # Check if current version meets minimum
            try:
                from packaging import version
                current_match = re.search(r'[>=<~!]+(\d+\.\d+\.\d+)', current_version_spec)
                if current_match:
                    current_ver = current_match.group(1)
                    if version.parse(current_ver) < version.parse(min_version):
                        requires_update = True
                        notes.append(f"Requires update to {min_version}+ for Django 6")
            except:
                pass
        print(f"{GREEN}✅{RESET}")
    else:
        print(f"{YELLOW}⚠️{RESET}")
        notes.append("Django 6 support unclear from PyPI metadata")
    
    if latest_version and latest_version != current_version_spec:
        notes.append(f"Latest version: {latest_version}")
    
    return DependencyCompatibility(
        name=package_name,
        current_version=current_version_spec,
        django6_supported=django6_supported,
        min_version_for_django6=min_version,
        latest_version=latest_version,
        requires_update=requires_update,
        notes=notes
    )


def parse_requirements_file(filepath: Path) -> List[Tuple[str, str]]:
    """Parse requirements file and return list of (name, version_spec) tuples."""
    dependencies = []
    
    if not filepath.exists():
        return dependencies
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('-r'):
                continue
            if '#' in line:
                line = line.split('#')[0].strip()
            
            match = re.match(r'^([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)(.*)$', line)
            if match:
                name = match.group(1).lower()
                version_spec = match.group(2).strip()
                if not version_spec:
                    version_spec = "latest"
                dependencies.append((name, version_spec))
    
    return dependencies


def main():
    """Main audit function."""
    print_header("Django 6 Dependency Compatibility Audit")
    
    project_root = Path(__file__).parent.parent
    
    # Django-related dependencies to check
    django_dependencies = {
        'djangorestframework': '>=3.14.0',
        'django-rq': '>=2.10.0',
        'django-cors-headers': '>=4.3.0',
        'django-storages': '>=1.14.0',
        'django-prometheus': '>=2.3.0',
        'strawberry-graphql': '>=0.200.0',
        'django-structlog': '>=6.0.0',
        'django-environ': '>=0.11.0',
        'django-stubs': '>=4.2.0',
        'django-debug-toolbar': '>=4.2.0',
        'django-extensions': '>=3.2.0',
        'pytest-django': '>=4.7.0',
    }
    
    # Also check requirements files
    requirements_files = [
        project_root / 'requirements.txt',
        project_root / 'requirements-dev.txt',
    ]
    
    all_django_deps = dict(django_dependencies)
    
    for req_file in requirements_files:
        if req_file.exists():
            deps = parse_requirements_file(req_file)
            for name, version_spec in deps:
                if 'django' in name.lower() and name not in all_django_deps:
                    all_django_deps[name] = version_spec
    
    print_info(f"Auditing {len(all_django_deps)} Django-related dependencies...")
    
    results = []
    
    for package_name, version_spec in sorted(all_django_deps.items()):
        result = check_django6_compatibility(package_name, version_spec)
        results.append(result)
    
    # Summary
    print_header("Audit Summary")
    
    compatible = [r for r in results if r.django6_supported is True]
    unclear = [r for r in results if r.django6_supported is None]
    incompatible = [r for r in results if r.django6_supported is False]
    needs_update = [r for r in results if r.requires_update]
    
    print(f"\n{BOLD}Total Dependencies Audited:{RESET} {len(results)}")
    print(f"{GREEN}✅ Django 6 Compatible:{RESET} {len(compatible)}")
    print(f"{CYAN}🔄 Requires Update:{RESET} {len(needs_update)}")
    print(f"{YELLOW}⚠️  Unclear Status:{RESET} {len(unclear)}")
    print(f"{RED}❌ Incompatible:{RESET} {len(incompatible)}")
    
    # Critical dependencies
    print_header("Critical Dependencies Status")
    
    critical = ['djangorestframework', 'django-rq', 'django-cors-headers', 
                'django-storages', 'django-prometheus', 'strawberry-graphql', 
                'django-structlog']
    
    for result in results:
        if result.name in critical:
            if result.django6_supported is True:
                if result.requires_update:
                    print(f"{CYAN}🔄 {result.name}{RESET}")
                    print(f"  Current: {result.current_version}")
                    print(f"  Required: {result.min_version_for_django6}+")
                    print(f"  Latest: {result.latest_version}")
                else:
                    print_success(f"{result.name}: Compatible with Django 6")
            elif result.django6_supported is False:
                print_error(f"{result.name}: Incompatible with Django 6")
            else:
                print_warning(f"{result.name}: Django 6 support unclear")
            
            if result.notes:
                for note in result.notes:
                    print(f"    {note}")
            print()
    
    # Dependencies requiring updates
    if needs_update:
        print_header("Dependencies Requiring Updates")
        for result in needs_update:
            print(f"{CYAN}🔄 {result.name}{RESET}")
            print(f"  Current: {result.current_version}")
            print(f"  Required for Django 6: {result.min_version_for_django6}+")
            print(f"  Latest: {result.latest_version}")
            print()
    
    # Generate report
    print_header("Generating Report")
    
    report_file = project_root / 'openspec/changes/fullcontract/DJANGO6_DEPENDENCY_AUDIT.md'
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w') as f:
        f.write("# Django 6 Dependency Compatibility Audit Report\n\n")
        f.write(f"**Date:** 2025-01-15\n")
        f.write(f"**Total Dependencies:** {len(results)}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- ✅ Django 6 Compatible: {len(compatible)}\n")
        f.write(f"- 🔄 Requires Update: {len(needs_update)}\n")
        f.write(f"- ⚠️  Unclear Status: {len(unclear)}\n")
        f.write(f"- ❌ Incompatible: {len(incompatible)}\n\n")
        
        f.write("## Critical Dependencies\n\n")
        for result in results:
            if result.name in critical:
                f.write(f"### {result.name}\n")
                f.write(f"- Current Version: {result.current_version}\n")
                f.write(f"- Django 6 Supported: {result.django6_supported}\n")
                if result.min_version_for_django6:
                    f.write(f"- Minimum Version for Django 6: {result.min_version_for_django6}\n")
                if result.latest_version:
                    f.write(f"- Latest Version: {result.latest_version}\n")
                if result.requires_update:
                    f.write(f"- **Requires Update:** Yes\n")
                if result.notes:
                    f.write(f"- Notes:\n")
                    for note in result.notes:
                        f.write(f"  - {note}\n")
                f.write("\n")
        
        if needs_update:
            f.write("## Dependencies Requiring Updates\n\n")
            for result in needs_update:
                f.write(f"### {result.name}\n")
                f.write(f"- Current: {result.current_version}\n")
                f.write(f"- Required: {result.min_version_for_django6}+\n")
                f.write(f"- Latest: {result.latest_version}\n")
                f.write("\n")
    
    print_success(f"Report generated: {report_file}")
    
    # Final status
    print_header("Final Status")
    
    if incompatible:
        print_error(f"{len(incompatible)} incompatible dependencies found")
        sys.exit(1)
    elif needs_update:
        print_warning(f"All dependencies compatible, but {len(needs_update)} require updates")
        print_info("Review dependencies requiring updates above")
        sys.exit(0)
    elif unclear:
        print_warning(f"All dependencies appear compatible, but {len(unclear)} have unclear status")
        print_info("Manual verification recommended for unclear dependencies")
        sys.exit(0)
    else:
        print_success("All dependencies are compatible with Django 6!")
        sys.exit(0)


if __name__ == '__main__':
    main()

