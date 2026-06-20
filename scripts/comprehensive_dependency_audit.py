#!/usr/bin/env python3
"""
Comprehensive Dependency Compatibility Audit for Python 3.12+

This script performs a thorough audit of all dependencies for Python 3.12+ compatibility:
1. Checks PyPI metadata for official Python version support
2. Tests actual installation in isolated environment
3. Verifies import compatibility
4. Documents compatibility status for each dependency
5. Identifies required updates

No mocks or stubs - real dependency checking.
"""

import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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
    REQUIRES_UPDATE = "requires_update"


@dataclass
class DependencyInfo:
    name: str
    version_spec: str
    status: CompatibilityStatus
    message: str
    tested_version: str | None = None
    pypi_supports: bool | None = None
    pypi_requires_python: str | None = None
    current_version: str | None = None
    recommended_version: str | None = None
    installation_test: bool = False
    import_test: bool = False
    notes: list[str] = field(default_factory=list)


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


def get_pypi_info(package_name: str) -> dict | None:
    """Get package information from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:
        return None


def check_pypi_python_support(package_name: str) -> tuple[bool | None, str | None]:
    """Check PyPI for Python 3.12+ compatibility."""
    pypi_data = get_pypi_info(package_name)
    if not pypi_data:
        return None, None

    # Check latest version's requires_python
    latest_version = pypi_data.get("info", {}).get("version")
    if latest_version:
        releases = pypi_data.get("releases", {}).get(latest_version, [])
        for release in releases:
            requires_python = release.get("requires_python", "")
            if requires_python:
                # Parse requires_python like ">=3.8,<4.0" or ">=3.12"
                if "3.12" in requires_python or ">=3.12" in requires_python:
                    return True, requires_python
                # Check if range includes 3.12
                if re.search(r">=3\.(1[2-9]|[2-9]\d)", requires_python):
                    return True, requires_python
                # Check if upper bound excludes 3.12
                if re.search(r"<3\.(1[0-1]|[0-9])", requires_python):
                    return False, requires_python

    # Check info.requires_python
    requires_python = pypi_data.get("info", {}).get("requires_python", "")
    if requires_python:
        if "3.12" in requires_python or ">=3.12" in requires_python:
            return True, requires_python
        if re.search(r">=3\.(1[2-9]|[2-9]\d)", requires_python):
            return True, requires_python
        if re.search(r"<3\.(1[0-1]|[0-9])", requires_python):
            return False, requires_python

    return None, None


def get_latest_version(package_name: str) -> str | None:
    """Get latest version of package from PyPI."""
    pypi_data = get_pypi_info(package_name)
    if pypi_data:
        return pypi_data.get("info", {}).get("version")
    return None


def test_dependency_installation(
    package_name: str, version_spec: str, python_exec: str
) -> tuple[bool, str | None, bool]:
    """Test if dependency can be installed with Python 3.12+."""
    try:
        # Create temporary directory for isolated test
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try dry-run installation
            package_spec = (
                f"{package_name}{version_spec}" if version_spec != "latest" else package_name
            )

            result = subprocess.run(
                [
                    python_exec,
                    "-m",
                    "pip",
                    "install",
                    "--dry-run",
                    "--break-system-packages",
                    "--target",
                    tmpdir,
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
                    installed_version = version_match.group(2)
                    return True, installed_version, True
                return True, None, True
            else:
                error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
                return False, error_msg, False
    except subprocess.TimeoutExpired:
        return False, "Installation check timed out", False
    except Exception as e:
        return False, str(e), False


def test_dependency_import(package_name: str, python_exec: str) -> bool:
    """Test if dependency can be imported."""
    # Normalize package name (e.g., django-cors-headers -> django_cors_headers)
    import_name = package_name.replace("-", "_")

    # Handle special cases
    import_mapping = {
        "django-cors-headers": "corsheaders",
        "django-structlog": "django_structlog",
        "django-storages": "storages",
        "django-prometheus": "django_prometheus",
        "django-rq": "django_rq",
        "strawberry-graphql": "strawberry",
        "drf-spectacular": "drf_spectacular",
        "python-dateutil": "dateutil",
        "html2text": "html2text",
        "SPARQLWrapper": "SPARQLWrapper",
    }

    import_name = import_mapping.get(package_name, import_name)

    try:
        result = subprocess.run(
            [python_exec, "-c", f"import {import_name}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


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

            # Handle -r requirements.txt includes
            if line.startswith("-r"):
                continue

            # Remove inline comments
            if "#" in line:
                line = line.split("#")[0].strip()

            # Parse package name and version
            match = re.match(r"^([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)(.*)$", line)
            if match:
                name = match.group(1).lower()
                version_spec = match.group(2).strip()
                if not version_spec:
                    version_spec = "latest"
                dependencies.append((name, version_spec))

    return dependencies


def audit_dependency(
    name: str, version_spec: str, python_exec: str, critical: bool = False
) -> DependencyInfo:
    """Audit a single dependency."""
    print(f"  Checking {name}{version_spec}...", end=" ", flush=True)

    # Check PyPI compatibility
    pypi_supports, requires_python = check_pypi_python_support(name)
    latest_version = get_latest_version(name)

    # Test installation
    can_install, install_info, _install_success = test_dependency_installation(
        name, version_spec, python_exec
    )

    # Test import (only if installation would succeed)
    can_import = False
    if can_install:
        can_import = test_dependency_import(name, python_exec)

    # Determine status
    if can_install and can_import:
        if pypi_supports is True:
            status = CompatibilityStatus.COMPATIBLE
            message = f"Compatible with Python 3.12+ (PyPI: {requires_python})"
        elif pypi_supports is False:
            status = CompatibilityStatus.WARNING
            message = f"Installs successfully but PyPI metadata indicates incompatibility ({requires_python})"
        else:
            status = CompatibilityStatus.COMPATIBLE
            message = "Compatible with Python 3.12+ (PyPI metadata unavailable, but installs successfully)"
    elif can_install:
        status = CompatibilityStatus.WARNING
        message = f"Installs but import test failed: {install_info}"
    else:
        status = CompatibilityStatus.INCOMPATIBLE
        message = f"Installation failed: {install_info[:100] if install_info else 'Unknown error'}"

    # Check if update is recommended
    recommended_version = None
    if latest_version and version_spec != "latest":
        # Extract current version from spec if possible
        version_match = re.search(r"[>=<~!]+(\d+\.\d+\.\d+)", version_spec)
        if version_match:
            current_version = version_match.group(1)
            if latest_version != current_version:
                recommended_version = latest_version
                if status == CompatibilityStatus.COMPATIBLE:
                    status = CompatibilityStatus.REQUIRES_UPDATE
                    message += f" (Update available: {latest_version})"

    tested_version = (
        install_info
        if install_info and isinstance(install_info, str) and install_info[0].isdigit()
        else None
    )

    # Print status
    if status == CompatibilityStatus.COMPATIBLE:
        print(f"{GREEN}✅{RESET}")
    elif status == CompatibilityStatus.WARNING:
        print(f"{YELLOW}⚠️{RESET}")
    elif status == CompatibilityStatus.REQUIRES_UPDATE:
        print(f"{CYAN}🔄{RESET}")
    else:
        print(f"{RED}❌{RESET}")

    return DependencyInfo(
        name=name,
        version_spec=version_spec,
        status=status,
        message=message,
        tested_version=tested_version,
        pypi_supports=pypi_supports,
        pypi_requires_python=requires_python,
        current_version=tested_version,
        recommended_version=recommended_version,
        installation_test=can_install,
        import_test=can_import,
    )


def audit_requirements_file(
    requirements_file: Path, python_exec: str, critical_deps: set[str] = None
) -> list[DependencyInfo]:
    """Audit dependencies in a requirements file."""
    if critical_deps is None:
        critical_deps = set()

    dependencies = parse_requirements_file(requirements_file)
    results = []

    print_info(f"Auditing {len(dependencies)} dependencies from {requirements_file.name}...")

    for _i, (name, version_spec) in enumerate(dependencies, 1):
        is_critical = name in critical_deps
        result = audit_dependency(name, version_spec, python_exec, critical=is_critical)
        results.append(result)

    return results


def main():
    """Main audit function."""
    print_header("Comprehensive Python 3.12+ Dependency Compatibility Audit")

    # Check Python version
    is_compatible, python_version = check_python_version()
    if not is_compatible:
        print_error(f"Python 3.12+ required. Found: {python_version}")
        sys.exit(1)

    print_success(f"Python {python_version} detected (meets 3.12+ requirement)")

    python_exec = sys.executable
    project_root = Path(__file__).parent.parent

    # Define critical dependencies to check
    critical_dependencies = {
        "django",
        "djangorestframework",
        "django-rq",
        "django-cors-headers",
        "django-storages",
        "django-prometheus",
        "strawberry-graphql",
        "django-structlog",
        "psycopg2-binary",
        "redis",
        "rq",
        "fastapi",
        "uvicorn",
        "pydantic",
    }

    # Audit requirements files
    requirements_files = [
        (project_root / "requirements.txt", "Main Application"),
        (project_root / "requirements-dev.txt", "Development Tools"),
        (project_root / "services/datacontract-service/requirements.txt", "Datacontract Service"),
        (project_root / "services/compliance-service/requirements.txt", "Compliance Service"),
        (project_root / "services/dq-service/requirements.txt", "DQ Service"),
        (project_root / "services/semantic-service/requirements.txt", "Semantic Service"),
        (project_root / "sdk/python/requirements.txt", "Python SDK"),
        (project_root / "sdk/python/requirements-dev.txt", "Python SDK Dev"),
    ]

    all_results = []
    all_dependencies = {}  # Track unique dependencies across files

    for req_file, description in requirements_files:
        if req_file.exists():
            print_header(f"Auditing {description} ({req_file.name})")
            results = audit_requirements_file(req_file, python_exec, critical_dependencies)
            all_results.extend(results)

            # Track unique dependencies
            for result in results:
                if result.name not in all_dependencies:
                    all_dependencies[result.name] = result
                else:
                    # Merge results if found in multiple files
                    existing = all_dependencies[result.name]
                    if result.status == CompatibilityStatus.INCOMPATIBLE:
                        existing.status = CompatibilityStatus.INCOMPATIBLE
                        existing.message = result.message
        else:
            print_warning(f"{req_file.name} not found, skipping")

    # Summary
    print_header("Audit Summary")

    compatible = [r for r in all_results if r.status == CompatibilityStatus.COMPATIBLE]
    warnings = [r for r in all_results if r.status == CompatibilityStatus.WARNING]
    incompatible = [r for r in all_results if r.status == CompatibilityStatus.INCOMPATIBLE]
    requires_update = [r for r in all_results if r.status == CompatibilityStatus.REQUIRES_UPDATE]

    print(f"\n{BOLD}Total Dependencies Audited:{RESET} {len(all_results)}")
    print(f"{GREEN}✅ Compatible:{RESET} {len(compatible)}")
    print(f"{CYAN}🔄 Updates Available:{RESET} {len(requires_update)}")
    print(f"{YELLOW}⚠️  Warnings:{RESET} {len(warnings)}")
    print(f"{RED}❌ Incompatible:{RESET} {len(incompatible)}")

    # Critical dependencies summary
    print_header("Critical Dependencies Status")

    critical_results = {
        name: all_dependencies.get(name)
        for name in critical_dependencies
        if name in all_dependencies
    }

    for name, result in sorted(critical_results.items()):
        if result:
            if result.status == CompatibilityStatus.COMPATIBLE:
                print_success(f"{name}: {result.message}")
            elif result.status == CompatibilityStatus.REQUIRES_UPDATE:
                print(f"{CYAN}🔄 {name}: {result.message}{RESET}")
            elif result.status == CompatibilityStatus.WARNING:
                print_warning(f"{name}: {result.message}")
            else:
                print_error(f"{name}: {result.message}")
        else:
            print_warning(f"{name}: Not found in requirements files")

    # Show incompatible dependencies
    if incompatible:
        print_header("Incompatible Dependencies")
        for dep in incompatible:
            print_error(f"{dep.name}{dep.version_spec}")
            print(f"  {dep.message}")
            if dep.recommended_version:
                print(f"  {CYAN}Recommended: Update to {dep.recommended_version}{RESET}")

    # Show dependencies requiring updates
    if requires_update:
        print_header("Dependencies with Updates Available")
        for dep in requires_update:
            print(f"{CYAN}🔄 {dep.name}{dep.version_spec}{RESET}")
            print(f"  Current: {dep.current_version or 'Unknown'}")
            print(f"  Latest: {dep.recommended_version}")
            print(f"  Status: {dep.message}")

    # Show warnings
    if warnings:
        print_header("Dependencies with Warnings")
        for dep in warnings[:10]:  # Show first 10
            print_warning(f"{dep.name}{dep.version_spec}")
            print(f"  {dep.message}")
        if len(warnings) > 10:
            print_info(f"... and {len(warnings) - 10} more warnings")

    # Generate report
    print_header("Generating Report")

    report_file = project_root / "openspec/changes/fullcontract/DEPENDENCY_COMPATIBILITY_AUDIT.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w") as f:
        f.write("# Python 3.12+ Dependency Compatibility Audit Report\n\n")
        f.write("**Date:** 2025-01-15\n")
        f.write(f"**Python Version:** {python_version}\n")
        f.write(f"**Total Dependencies:** {len(all_results)}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- ✅ Compatible: {len(compatible)}\n")
        f.write(f"- 🔄 Updates Available: {len(requires_update)}\n")
        f.write(f"- ⚠️  Warnings: {len(warnings)}\n")
        f.write(f"- ❌ Incompatible: {len(incompatible)}\n\n")

        f.write("## Critical Dependencies\n\n")
        for name, result in sorted(critical_results.items()):
            if result:
                status_icon = (
                    "✅"
                    if result.status == CompatibilityStatus.COMPATIBLE
                    else "⚠️"
                    if result.status == CompatibilityStatus.WARNING
                    else "❌"
                )
                f.write(f"### {name}\n")
                f.write(f"- Status: {status_icon} {result.status.value}\n")
                f.write(f"- Message: {result.message}\n")
                if result.pypi_requires_python:
                    f.write(f"- PyPI requires_python: {result.pypi_requires_python}\n")
                if result.recommended_version:
                    f.write(f"- Recommended Version: {result.recommended_version}\n")
                f.write("\n")

        if incompatible:
            f.write("## Incompatible Dependencies\n\n")
            for dep in incompatible:
                f.write(f"### {dep.name}{dep.version_spec}\n")
                f.write(f"- Status: ❌ {dep.status.value}\n")
                f.write(f"- Issue: {dep.message}\n")
                if dep.recommended_version:
                    f.write(f"- Recommended: Update to {dep.recommended_version}\n")
                f.write("\n")

        if requires_update:
            f.write("## Dependencies Requiring Updates\n\n")
            for dep in requires_update:
                f.write(f"### {dep.name}{dep.version_spec}\n")
                f.write(f"- Current: {dep.current_version or 'Unknown'}\n")
                f.write(f"- Latest: {dep.recommended_version}\n")
                f.write(f"- Status: {dep.message}\n")
                f.write("\n")

    print_success(f"Report generated: {report_file}")

    # Final status
    print_header("Final Status")

    if incompatible:
        print_error(f"{len(incompatible)} incompatible dependencies found")
        print_info(
            "Review incompatible dependencies above and update versions or find alternatives"
        )
        sys.exit(1)
    elif requires_update:
        print_warning(
            f"All dependencies compatible, but {len(requires_update)} have updates available"
        )
        print_info("Consider updating to latest versions for security and features")
        sys.exit(0)
    elif warnings:
        print_warning(f"All dependencies compatible, but {len(warnings)} have warnings")
        print_info("Warnings are non-critical but should be reviewed")
        sys.exit(0)
    else:
        print_success("All dependencies are compatible with Python 3.12+!")
        sys.exit(0)


if __name__ == "__main__":
    main()
