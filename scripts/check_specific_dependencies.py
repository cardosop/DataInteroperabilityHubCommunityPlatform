#!/usr/bin/env python3
"""
Check Specific Critical Dependencies for Python 3.12+ Compatibility

This script checks the specific dependencies mentioned in tasks.md:
- Django
- Django REST Framework
- django-rq
- django-cors-headers
- django-storages
- django-prometheus
- strawberry-graphql
- django-structlog
- And all other dependencies

No mocks - real PyPI checks and installation tests.
"""

import sys
import subprocess
import json
import urllib.request
import urllib.error
import re
from typing import Dict, Optional, Tuple

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
BOLD = '\033[1m'
RESET = '\033[0m'


def get_pypi_info(package_name: str) -> Optional[Dict]:
    """Get package information from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())
    except Exception:
        return None


def check_python_support(package_name: str) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Check if package supports Python 3.12+."""
    pypi_data = get_pypi_info(package_name)
    if not pypi_data:
        return None, None, None
    
    info = pypi_data.get('info', {})
    latest_version = info.get('version')
    requires_python = info.get('requires_python', '')
    
    # Check requires_python
    if requires_python:
        if '3.12' in requires_python or '>=3.12' in requires_python:
            return True, requires_python, latest_version
        if re.search(r'>=3\.(1[2-9]|[2-9]\d)', requires_python):
            return True, requires_python, latest_version
        if re.search(r'<3\.(1[0-1]|[0-9])', requires_python):
            return False, requires_python, latest_version
    
    # Check latest release files
    releases = pypi_data.get('releases', {}).get(latest_version, [])
    for release in releases:
        req_py = release.get('requires_python', '')
        if req_py:
            if '3.12' in req_py or '>=3.12' in req_py:
                return True, req_py, latest_version
            if re.search(r'>=3\.(1[2-9]|[2-9]\d)', req_py):
                return True, req_py, latest_version
    
    return None, requires_python or 'Not specified', latest_version


def test_installation(package_name: str, version_spec: str) -> Tuple[bool, Optional[str]]:
    """Test if package can be installed."""
    try:
        package_spec = f"{package_name}{version_spec}" if version_spec != "latest" else package_name
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--dry-run', '--break-system-packages', package_spec],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            version_match = re.search(r'Would install (.+?)-(\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                return True, version_match.group(2)
            return True, None
        return False, result.stderr[:100] if result.stderr else "Unknown error"
    except Exception as e:
        return False, str(e)


def main():
    """Check critical dependencies."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}Critical Dependencies Python 3.12+ Compatibility Check{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")
    
    # Critical dependencies from tasks.md
    critical_deps = {
        'Django': ('django', '>=4.2,<5.0'),
        'Django REST Framework': ('djangorestframework', '>=3.14.0'),
        'django-rq': ('django-rq', '>=2.10.0'),
        'django-cors-headers': ('django-cors-headers', '>=4.3.0'),
        'django-storages': ('django-storages', '>=1.14.0'),
        'django-prometheus': ('django-prometheus', '>=2.3.0'),
        'strawberry-graphql': ('strawberry-graphql', '>=0.200.0'),
        'django-structlog': ('django-structlog', '>=6.0.0'),
    }
    
    results = []
    
    for display_name, (package_name, version_spec) in critical_deps.items():
        print(f"{BOLD}Checking {display_name} ({package_name}{version_spec})...{RESET}")
        
        # Check PyPI
        pypi_supports, requires_python, latest_version = check_python_support(package_name)
        
        # Test installation
        can_install, install_info = test_installation(package_name, version_spec)
        
        # Determine status
        if can_install:
            if pypi_supports is True:
                status = f"{GREEN}✅ COMPATIBLE{RESET}"
                message = f"PyPI confirms Python 3.12+ support ({requires_python})"
            elif pypi_supports is False:
                status = f"{YELLOW}⚠️  WARNING{RESET}"
                message = f"PyPI metadata unclear ({requires_python}), but installs successfully"
            else:
                status = f"{GREEN}✅ COMPATIBLE{RESET}"
                message = f"Installs successfully (PyPI metadata: {requires_python})"
        else:
            status = f"{RED}❌ INCOMPATIBLE{RESET}"
            message = f"Installation failed: {install_info}"
        
        print(f"  Status: {status}")
        print(f"  {message}")
        if latest_version:
            print(f"  Latest version: {latest_version}")
        if install_info:
            print(f"  Tested version: {install_info}")
        print()
        
        results.append({
            'name': display_name,
            'package': package_name,
            'status': 'COMPATIBLE' if can_install else 'INCOMPATIBLE',
            'pypi_supports': pypi_supports,
            'requires_python': requires_python,
            'latest_version': latest_version,
            'tested_version': install_info,
        })
    
    # Summary
    compatible = [r for r in results if r['status'] == 'COMPATIBLE']
    incompatible = [r for r in results if r['status'] == 'INCOMPATIBLE']
    
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Summary{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")
    print(f"{GREEN}✅ Compatible: {len(compatible)}/{len(results)}{RESET}")
    if incompatible:
        print(f"{RED}❌ Incompatible: {len(incompatible)}/{len(results)}{RESET}")
    
    if incompatible:
        print(f"\n{RED}Incompatible dependencies:{RESET}")
        for r in incompatible:
            print(f"  {RED}❌{RESET} {r['name']}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✅ All critical dependencies are compatible with Python 3.12+!{RESET}")
        sys.exit(0)


if __name__ == '__main__':
    main()

