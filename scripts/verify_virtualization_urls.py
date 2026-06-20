#!/usr/bin/env python3
"""
Script to verify virtualization URLs are correctly configured.

Checks:
1. URLs file exists and is properly configured
2. URLs are registered in main API URLs
3. No duplicate basenames
4. All ViewSets are registered
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def verify_virtualization_urls():
    """Verify virtualization URLs configuration"""
    errors = []
    warnings = []

    # 1. Check if urls.py exists
    urls_file = project_root / "hub" / "apps" / "virtualization" / "urls.py"
    if not urls_file.exists():
        errors.append(f"Virtualization URLs file not found: {urls_file}")
        return errors, warnings

    # 2. Check if URLs are registered in main API URLs
    api_urls_file = project_root / "hub" / "apps" / "api" / "urls.py"
    if api_urls_file.exists():
        with open(api_urls_file) as f:
            content = f.read()
            if "virtualization/" not in content or "hub.apps.virtualization.urls" not in content:
                errors.append("Virtualization URLs not registered in hub/apps/api/urls.py")
    else:
        errors.append(f"Main API URLs file not found: {api_urls_file}")

    # 3. Check for required ViewSets in urls.py
    with open(urls_file) as f:
        content = f.read()
        required_viewsets = [
            "VirtualDatasetViewSet",
            "QueryExecutionViewSet",
            "VirtualizationTopologyViewSet",
        ]
        for viewset in required_viewsets:
            if viewset not in content:
                errors.append(f"ViewSet {viewset} not found in urls.py")

    # 4. Check for required basenames
    required_basenames = ["virtual-dataset", "query-execution", "virtualization-topology"]
    for basename in required_basenames:
        if f'basename="{basename}"' not in content and f"basename='{basename}'" not in content:
            errors.append(f"Basename '{basename}' not found in urls.py")

    # 5. Check for duplicate basenames across all apps
    basename_map = {}
    apps_dir = project_root / "hub" / "apps"
    for app_dir in apps_dir.iterdir():
        if app_dir.is_dir():
            app_urls = app_dir / "urls.py"
            if app_urls.exists():
                with open(app_urls) as f:
                    app_content = f.read()
                    # Extract basenames using simple regex-like search
                    import re

                    basename_pattern = r'basename=["\']([^"\']+)["\']'
                    matches = re.findall(basename_pattern, app_content)
                    for basename in matches:
                        if basename in basename_map:
                            warnings.append(
                                f"Potential duplicate basename '{basename}' found in "
                                f"{basename_map[basename]} and {app_dir.name}/urls.py"
                            )
                        else:
                            basename_map[basename] = f"{app_dir.name}/urls.py"

    # Check virtualization basenames specifically
    virtualization_basenames = [b for b in basename_map if b.startswith("virtual")]
    if len(virtualization_basenames) != 3:
        warnings.append(
            f"Expected 3 virtualization-related basenames, found {len(virtualization_basenames)}"
        )

    return errors, warnings


if __name__ == "__main__":
    errors, warnings = verify_virtualization_urls()

    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        sys.exit(1)

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    if not errors and not warnings:
        print("✅ All virtualization URL checks passed!")
        print("  - URLs file exists and is properly configured")
        print("  - URLs are registered in main API URLs")
        print("  - All required ViewSets are registered")
        print("  - All required basenames are present")
        print("  - No duplicate basenames found")
        sys.exit(0)
    elif not errors:
        print("✅ Virtualization URLs are correctly configured (with warnings)")
        sys.exit(0)
    else:
        sys.exit(1)
