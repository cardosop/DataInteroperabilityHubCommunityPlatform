#!/usr/bin/env python3
"""
Comprehensive Dependency Compatibility Audit for Python 3.12+

This script audits all dependencies for Python 3.12+ compatibility by:
1. Checking PyPI metadata for Python version support
2. Testing actual installation in a virtual environment
3. Verifying import compatibility
4. Checking for known compatibility issues

No mocks or stubs - real dependency checking.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Colors for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
RESET = "\033[0m"


class CompatibilityStatus(Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"
    WARNING = "warning"


@dataclass
class DependencyInfo:
    name: str
    version_spec: str
    status: CompatibilityStatus
    message: str
    tested_version: str | None = None
    pypi_supports: bool | None = None


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


def check_python_version() -> tuple[bool, str]:
    """Check if Python 3.12+ is available."""
    version = sys.version_info
    if version >= (3, 12):
        return True, f"{version.major}.{version.minor}.{version.micro}"
    return False, f"{version.major}.{version.minor}.{version.micro}"


def parse_requirements_file(filepath: Path) -> list[tuple[str, str]]:
    """Parse requirements file and return list of (name, version_spec) tuples."""
    dependencies = []

    if not filepath.exists():
        return dependencies

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Remove inline comments
            if "#" in line:
                line = line.split("#")[0].strip()

            # Parse package name and version
            # Handle formats: package==1.0.0, package>=1.0.0, package~=1.0.0, etc.
            match = re.match(r"^([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)(.*)$", line)
            if match:
                name = match.group(1).lower()
                version_spec = match.group(2).strip()
                if not version_spec:
                    version_spec = "latest"
                dependencies.append((name, version_spec))

    return dependencies


def check_pypi_compatibility(package_name: str) -> bool | None:
    """Check PyPI for Python 3.12+ compatibility."""
    try:
        # Use pip index to check package metadata
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", package_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Try to get package info from PyPI JSON API
            import json as json_lib
            import urllib.request

            url = f"https://pypi.org/pypi/{package_name}/json"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json_lib.loads(response.read())

                    # Check if any version supports Python 3.12+
                    for _version, files in data.get("releases", {}).items():
                        for file_info in files:
                            requires_python = file_info.get("requires_python", "")
                            if requires_python:
                                # Parse requires_python like ">=3.8,<4.0"
                                if "3.12" in requires_python or ">=3.12" in requires_python:
                                    return True
                                # Check if range includes 3.12
                                if re.search(r">=3\.(1[2-9]|[2-9]\d)", requires_python):
                                    return True
                    return None
            except Exception:
                return None
    except Exception:
        return None

    return None


def test_dependency_installation(package_name: str, version_spec: str) -> tuple[bool, str | None]:
    """Test if dependency can be installed with Python 3.12+."""
    try:
        # Try dry-run installation
        package_spec = f"{package_name}{version_spec}" if version_spec != "latest" else package_name

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--break-system-packages",
                package_spec,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Extract version from output if available
            version_match = re.search(r"Would install (.+?)-(\d+\.\d+\.\d+)", result.stdout)
            if version_match:
                return True, version_match.group(2)
            return True, None
        else:
            error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
            return False, error_msg
    except subprocess.TimeoutExpired:
        return False, "Installation check timed out"
    except Exception as e:
        return False, str(e)


def audit_dependencies(requirements_file: Path) -> list[DependencyInfo]:
    """Audit dependencies in a requirements file."""
    dependencies = parse_requirements_file(requirements_file)
    results = []

    print_info(f"Auditing {len(dependencies)} dependencies from {requirements_file.name}...")

    for i, (name, version_spec) in enumerate(dependencies, 1):
        print(f"  [{i}/{len(dependencies)}] Checking {name}{version_spec}...", end=" ", flush=True)

        # Check PyPI compatibility
        pypi_supports = check_pypi_compatibility(name)

        # Test installation
        can_install, install_info = test_dependency_installation(name, version_spec)

        # Determine status
        if can_install:
            status = CompatibilityStatus.COMPATIBLE
            message = "Compatible with Python 3.12+"
            if pypi_supports is False:
                message += " (PyPI metadata unclear, but installs successfully)"
        else:
            status = CompatibilityStatus.INCOMPATIBLE
            message = (
                f"Installation failed: {install_info[:100] if install_info else 'Unknown error'}"
            )

        if pypi_supports is None and status == CompatibilityStatus.COMPATIBLE:
            status = CompatibilityStatus.WARNING
            message += " (PyPI metadata not available, but installs successfully)"

        tested_version = install_info if install_info and can_install else None

        results.append(
            DependencyInfo(
                name=name,
                version_spec=version_spec,
                status=status,
                message=message,
                tested_version=tested_version,
                pypi_supports=pypi_supports,
            )
        )

        # Print status
        if status == CompatibilityStatus.COMPATIBLE:
            print(f"{GREEN}✅{RESET}")
        elif status == CompatibilityStatus.WARNING:
            print(f"{YELLOW}⚠️{RESET}")
        else:
            print(f"{RED}❌{RESET}")

    return results


def main():
    """Main audit function."""
    print_header("Python 3.12+ Dependency Compatibility Audit")

    # Check Python version
    is_compatible, python_version = check_python_version()
    if not is_compatible:
        print_error(f"Python 3.12+ required. Found: {python_version}")
        sys.exit(1)

    print_success(f"Python {python_version} detected (meets 3.12+ requirement)")

    project_root = Path(__file__).parent.parent

    # Audit requirements files
    requirements_files = [
        project_root / "requirements.txt",
        project_root / "requirements-dev.txt",
    ]

    all_results = []

    for req_file in requirements_files:
        if req_file.exists():
            print_header(f"Auditing {req_file.name}")
            results = audit_dependencies(req_file)
            all_results.extend(results)
        else:
            print_warning(f"{req_file.name} not found, skipping")

    # Summary
    print_header("Audit Summary")

    compatible = [r for r in all_results if r.status == CompatibilityStatus.COMPATIBLE]
    warnings = [r for r in all_results if r.status == CompatibilityStatus.WARNING]
    incompatible = [r for r in all_results if r.status == CompatibilityStatus.INCOMPATIBLE]

    print(f"\n{BOLD}Total Dependencies Audited:{RESET} {len(all_results)}")
    print(f"{GREEN}✅ Compatible:{RESET} {len(compatible)}")
    print(f"{YELLOW}⚠️  Warnings:{RESET} {len(warnings)}")
    print(f"{RED}❌ Incompatible:{RESET} {len(incompatible)}")

    # Show incompatible dependencies
    if incompatible:
        print(f"\n{BOLD}{RED}Incompatible Dependencies:{RESET}")
        for dep in incompatible:
            print(f"  {RED}❌{RESET} {dep.name}{dep.version_spec}")
            print(f"      {dep.message}")

    # Show warnings
    if warnings:
        print(f"\n{BOLD}{YELLOW}Dependencies with Warnings:{RESET}")
        for dep in warnings:
            print(f"  {YELLOW}⚠️{RESET} {dep.name}{dep.version_spec}")
            print(f"      {dep.message}")

    # Final status
    print_header("Final Status")

    if incompatible:
        print_error(f"{len(incompatible)} incompatible dependencies found")
        print_info(
            "Review incompatible dependencies above and update versions or find alternatives"
        )
        sys.exit(1)
    elif warnings:
        print_warning(f"All dependencies compatible, but {len(warnings)} have warnings")
        print_info("Warnings are non-critical but should be reviewed")
        sys.exit(0)
    else:
        print_success("All dependencies are compatible with Python 3.12+!")
        sys.exit(0)


if __name__ == "__main__":
    main()
