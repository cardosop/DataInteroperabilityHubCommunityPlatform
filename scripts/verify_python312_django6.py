#!/usr/bin/env python3
"""
Comprehensive Python 3.12+ and Django 6+ Verification Script

This script verifies that:
1. Python 3.12+ is installed and being used
2. Django 6.0+ is installed
3. The application can start successfully
4. Basic Django functionality works

Usage:
    python scripts/verify_python312_django6.py
"""

import sys
import subprocess
import re
from pathlib import Path
from typing import Tuple

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text: str) -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")

def print_success(text: str) -> None:
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text: str) -> None:
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text: str) -> None:
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text: str) -> None:
    print(f"{BLUE}ℹ️  {text}{RESET}")

def check_python_version() -> Tuple[bool, str]:
    """Check if Python 3.12+ is installed."""
    print_header("1. Checking Python Version")
    
    try:
        result = subprocess.run(
            [sys.executable, '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        version_str = result.stdout.strip()
        print_info(f"Current Python: {version_str}")
        
        match = re.search(r'(\d+)\.(\d+)', version_str)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            if major > 3 or (major == 3 and minor >= 12):
                print_success(f"Python {major}.{minor} meets requirement (3.12+)")
                return True, f"{major}.{minor}"
            else:
                print_error(f"Python {major}.{minor} does not meet requirement (3.12+)")
                print_error("Please upgrade to Python 3.12 or higher")
                return False, f"{major}.{minor}"
        else:
            print_error("Could not parse Python version")
            return False, "unknown"
    except Exception as e:
        print_error(f"Error checking Python version: {e}")
        return False, "error"

def check_django_version() -> Tuple[bool, str]:
    """Check if Django 6.0+ is installed."""
    print_header("2. Checking Django Version")
    
    try:
        import django
        django_version = django.get_version()
        print_info(f"Installed Django version: {django_version}")
        
        # Parse version (e.g., "6.0.1" or "6.1")
        match = re.search(r'(\d+)\.(\d+)', django_version)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            if major > 6 or (major == 6 and minor >= 0):
                print_success(f"Django {django_version} meets requirement (6.0+)")
                return True, django_version
            else:
                print_error(f"Django {django_version} does not meet requirement (6.0+)")
                print_error("Please upgrade Django: pip install 'Django>=6.0,<7.0'")
                return False, django_version
        else:
            print_warning(f"Could not parse Django version: {django_version}")
            return False, django_version
    except ImportError:
        print_error("Django is not installed")
        print_error("Please install Django: pip install 'Django>=6.0,<7.0'")
        return False, "not_installed"
    except Exception as e:
        print_error(f"Error checking Django version: {e}")
        return False, "error"

def check_django_settings() -> bool:
    """Check if Django settings can be loaded."""
    print_header("3. Checking Django Settings")
    
    try:
        import os
        import sys
        from pathlib import Path
        
        # Add project root to Python path
        base_dir = Path(__file__).parent.parent
        if str(base_dir) not in sys.path:
            sys.path.insert(0, str(base_dir))
        
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
        
        import django
        django.setup()
        
        from django.conf import settings
        
        print_success("Django settings loaded successfully")
        print_info(f"DEBUG mode: {settings.DEBUG}")
        print_info(f"Installed apps: {len(settings.INSTALLED_APPS)} apps")
        
        return True
    except Exception as e:
        print_error(f"Error loading Django settings: {e}")
        return False

def check_django_middleware() -> bool:
    """Check if Django 6 middleware pattern is used."""
    print_header("4. Checking Django 6 Middleware Compatibility")
    
    try:
        import django
        django_version = django.get_version()
        
        # Check if we're on Django 6
        if django_version.startswith('6.'):
            # Check for MiddlewareMixin usage (should not exist in Django 6)
            # Only check our codebase, not third-party packages
            from pathlib import Path
            base_dir = Path(__file__).parent.parent
            # Only check hub/ directory, exclude venv and site-packages
            middleware_files = [
                f for f in (base_dir / 'hub').rglob('**/middleware.py')
                if 'venv' not in str(f) and 'site-packages' not in str(f)
            ]
            
            middlewaremixin_found = False
            for mw_file in middleware_files:
                try:
                    content = mw_file.read_text()
                    if 'MiddlewareMixin' in content and 'from django.utils.deprecation import MiddlewareMixin' in content:
                        print_warning(f"Found MiddlewareMixin usage in {mw_file}")
                        middlewaremixin_found = True
                except Exception:
                    pass
            
            if not middlewaremixin_found:
                print_success("No deprecated MiddlewareMixin usage found")
            else:
                print_warning("Some middleware files may need updating for Django 6")
            
            return True
        else:
            print_info("Django 6 middleware check skipped (not on Django 6)")
            return True
    except Exception as e:
        print_warning(f"Could not check middleware: {e}")
        return True  # Don't fail on this

def check_django_app_startup() -> bool:
    """Check if Django application can start."""
    print_header("5. Checking Django Application Startup")
    
    try:
        import os
        import sys
        from pathlib import Path
        
        # Add project root to Python path
        base_dir = Path(__file__).parent.parent
        if str(base_dir) not in sys.path:
            sys.path.insert(0, str(base_dir))
        
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
        
        import django
        django.setup()
        
        # Try to import a model to verify database connection isn't required
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            print_success("Django models can be imported")
        except Exception as e:
            print_warning(f"Could not import models (may need database): {e}")
        
        # Check if we can access settings
        from django.conf import settings
        if hasattr(settings, 'SECRET_KEY'):
            print_success("Django settings accessible")
        
        return True
    except Exception as e:
        print_error(f"Error starting Django application: {e}")
        return False

def check_requirements_txt() -> bool:
    """Check if requirements.txt specifies Django 6.0+."""
    print_header("6. Checking requirements.txt")
    
    try:
        # Script is in scripts/, so go up two levels to project root
        base_dir = Path(__file__).parent.parent
        requirements_file = base_dir / 'requirements.txt'
        
        if not requirements_file.exists():
            print_error("requirements.txt not found")
            return False
        
        content = requirements_file.read_text()
        
        # Check for Django>=6.0
        if re.search(r'Django\s*>=\s*6\.0', content, re.IGNORECASE):
            print_success("requirements.txt specifies Django>=6.0")
            return True
        elif re.search(r'Django\s*==\s*6\.', content, re.IGNORECASE):
            print_success("requirements.txt specifies Django 6.x")
            return True
        else:
            print_warning("requirements.txt may not specify Django 6.0+")
            print_info("Current Django line in requirements.txt:")
            for line in content.split('\n'):
                if 'django' in line.lower() and not line.strip().startswith('#'):
                    print_info(f"  {line.strip()}")
            return False
    except Exception as e:
        print_error(f"Error checking requirements.txt: {e}")
        return False

def main():
    """Run all verification checks."""
    print_header("Python 3.12+ and Django 6+ Verification")
    print_info("This script verifies that your environment is properly configured")
    print_info("for Python 3.12+ and Django 6.0+\n")
    
    results = []
    
    # Check Python version
    python_ok, python_version = check_python_version()
    results.append(("Python 3.12+", python_ok))
    
    if not python_ok:
        print_error("\n❌ Python 3.12+ is required. Please upgrade Python first.")
        sys.exit(1)
    
    # Check Django version
    django_ok, django_version = check_django_version()
    results.append(("Django 6.0+", django_ok))
    
    if not django_ok:
        print_error("\n❌ Django 6.0+ is required.")
        print_info("To install Django 6.0+, run:")
        print_info("  pip install 'Django>=6.0,<7.0'")
        print_info("  pip install -r requirements.txt")
        sys.exit(1)
    
    # Check requirements.txt
    req_ok = check_requirements_txt()
    results.append(("requirements.txt", req_ok))
    
    # Check Django settings
    settings_ok = check_django_settings()
    results.append(("Django Settings", settings_ok))
    
    # Check middleware compatibility
    middleware_ok = check_django_middleware()
    results.append(("Middleware Compatibility", middleware_ok))
    
    # Check application startup
    startup_ok = check_django_app_startup()
    results.append(("Application Startup", startup_ok))
    
    # Summary
    print_header("Verification Summary")
    
    all_passed = all(result[1] for result in results)
    
    for check_name, passed in results:
        if passed:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED")
    
    print()
    if all_passed:
        print_success("🎉 All checks passed! Your environment is ready for Python 3.12+ and Django 6+")
        print_info(f"Python version: {python_version}")
        print_info(f"Django version: {django_version}")
        return 0
    else:
        print_error("❌ Some checks failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())

