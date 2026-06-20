#!/usr/bin/env python3
"""
API Endpoint Audit Script

Comprehensive audit tool for analyzing Django REST Framework API endpoints.
Parses URL patterns, detects duplicates and inconsistencies, and generates
endpoint inventory reports.

Usage:
    python audit-api-endpoints.py [options]

Options:
    --urls-file PATH    Path to hub/apps/api/urls.py (default: auto-detect)
    --output-format     Output format: json, markdown (default: markdown)
    --output-file PATH  Output file path (default: stdout)
    --check-duplicates  Check for duplicate endpoints
    --check-naming      Check for inconsistent naming patterns
    --verbose           Verbose output
    --help              Show this help message
"""

import argparse
import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


class URLPatternParser:
    """Parse Django URL patterns (path, re_path, include, router)"""

    def __init__(self):
        self.endpoints = []

    def parse_pattern(
        self,
        pattern: Any,
        base_path: str = "/api/v1",
        prefix: str = "",
        service_name: str = "",
    ) -> dict[str, Any] | None:
        """
        Parse a Django URL pattern.

        Args:
            pattern: Django URL pattern object
            base_path: Base API path (e.g., '/api/v1')
            prefix: URL prefix (e.g., 'auth/')
            service_name: Service name (e.g., 'auth')

        Returns:
            Parsed endpoint information or None
        """
        pattern_type = type(pattern).__name__

        # Check for URLResolver first (include patterns)
        if pattern_type == "URLResolver" or hasattr(pattern, "urlconf_name"):
            # Handle include() patterns
            return self._parse_include_pattern(pattern, base_path, prefix, service_name)
        elif pattern_type == "URLPattern":
            # Handle path() patterns
            return self._parse_path_pattern(pattern, base_path, prefix, service_name)
        elif hasattr(pattern, "pattern") and hasattr(pattern, "callback"):
            # Handle re_path() patterns or other patterns with pattern and callback
            return self._parse_re_path_pattern(pattern, base_path, prefix, service_name)
        else:
            return None

    def _parse_path_pattern(
        self,
        pattern: Any,
        base_path: str,
        prefix: str,
        service_name: str,
    ) -> dict[str, Any] | None:
        """Parse path() pattern"""
        try:
            pattern_str = str(pattern.pattern)
            callback = pattern.callback
            name = pattern.name or ""

            # Build full path
            # prefix already includes base_path and accumulated path (e.g., "/api/v1/auth/")
            # pattern_str is the endpoint pattern (e.g., "login/")
            # Just combine prefix + pattern_str (don't add base_path again)
            if prefix:
                prefix_clean = prefix.rstrip("/")
                pattern_clean = pattern_str.lstrip("/")
                if pattern_clean:
                    full_path = prefix_clean + "/" + pattern_clean
                else:
                    full_path = prefix_clean
            else:
                # No prefix, use base_path + pattern_str
                full_path = base_path.rstrip("/") + "/" + pattern_str.lstrip("/")

            full_path = re.sub(r"/+", "/", full_path)  # Normalize slashes
            # Keep trailing slash for consistency with Django URL patterns
            if pattern_str.endswith("/") and not full_path.endswith("/"):
                full_path += "/"

            # Determine HTTP methods from callback
            methods = self._get_http_methods(callback)

            return {
                "type": "path",
                "pattern": pattern_str,
                "full_path": full_path,
                "name": name,
                "service": service_name,
                "methods": methods,
                "callback": self._get_callback_name(callback),
            }
        except Exception:
            return None

    def _parse_re_path_pattern(
        self,
        pattern: Any,
        base_path: str,
        prefix: str,
        service_name: str,
    ) -> dict[str, Any] | None:
        """Parse re_path() pattern"""
        try:
            pattern_str = str(pattern.pattern)
            callback = pattern.callback
            name = pattern.name or ""

            # Build full path (simplified regex pattern)
            simplified_pattern = self._simplify_regex_pattern(pattern_str)
            # prefix already includes the full path from root (e.g., "/api/v1/auth/")
            # simplified_pattern is the endpoint pattern
            if prefix:
                # Prefix already includes base_path, so just append simplified_pattern
                prefix_clean = prefix.rstrip("/")
                pattern_clean = simplified_pattern.lstrip("/")
                if pattern_clean:
                    full_path = prefix_clean + "/" + pattern_clean
                else:
                    full_path = prefix_clean
            else:
                # No prefix, use base_path + simplified_pattern
                full_path = base_path.rstrip("/") + "/" + simplified_pattern.lstrip("/")

            full_path = re.sub(r"/+", "/", full_path)
            # Keep trailing slash for consistency
            if pattern_str.endswith("/") and not full_path.endswith("/"):
                full_path += "/"

            methods = self._get_http_methods(callback)

            return {
                "type": "re_path",
                "pattern": pattern_str,
                "simplified_pattern": simplified_pattern,
                "full_path": full_path,
                "name": name,
                "service": service_name,
                "methods": methods,
                "callback": self._get_callback_name(callback),
            }
        except Exception:
            return None

    def _parse_include_pattern(
        self,
        pattern: Any,
        base_path: str,
        prefix: str,
        service_name: str,
    ) -> dict[str, Any] | None:
        """Parse include() pattern"""
        try:
            # Get included URL module
            urlconf = pattern.urlconf_name
            url_patterns = pattern.url_patterns

            # Extract prefix from pattern
            include_prefix = str(pattern.pattern) if hasattr(pattern, "pattern") else ""

            # Combine prefixes
            new_prefix = prefix.rstrip("/") + "/" + include_prefix.lstrip("/")
            new_prefix = re.sub(r"/+", "/", new_prefix).rstrip("/") + "/"

            # Extract service name from module path
            if not service_name and isinstance(urlconf, str):
                # Extract service name from module path (e.g., 'hub.apps.auth.urls' -> 'auth')
                parts = urlconf.split(".")
                if len(parts) >= 3 and parts[-2] in ["apps", "api"]:
                    service_name = (
                        parts[-3] if parts[-2] == "apps" else parts[-1].replace("urls", "")
                    )

            # Recursively parse included patterns
            endpoints = []
            for sub_pattern in url_patterns:
                result = self.parse_pattern(sub_pattern, base_path, new_prefix, service_name)
                if result:
                    if result.get("type") == "include":
                        # Handle nested includes
                        endpoints.extend(result.get("endpoints", []))
                    else:
                        endpoints.append(result)

            return {
                "type": "include",
                "module": str(urlconf),
                "prefix": new_prefix,
                "service": service_name,
                "endpoints": endpoints,
            }
        except Exception:
            return None

    def _simplify_regex_pattern(self, pattern: str) -> str:
        """Simplify regex pattern for display"""
        # Remove regex anchors and convert named groups
        simplified = pattern
        simplified = simplified.replace("^", "").replace("$", "")
        simplified = re.sub(r"\(\?P<(\w+)>[^)]+\)", r"<\1>", simplified)
        simplified = re.sub(r"\([^)]*\)", "<id>", simplified)
        return simplified

    def _get_http_methods(self, callback: Any) -> list[str]:
        """Extract HTTP methods from callback"""
        methods = ["GET"]  # Default

        if hasattr(callback, "actions"):
            # ViewSet with actions
            actions = callback.actions
            if isinstance(actions, dict):
                methods = list(actions.keys())
        elif hasattr(callback, "http_method_names"):
            # Generic view
            methods = [m.upper() for m in callback.http_method_names if m.upper() != "OPTIONS"]
        elif hasattr(callback, "cls"):
            # ViewSet class
            viewset = callback.cls
            if hasattr(viewset, "http_method_names"):
                methods = [m.upper() for m in viewset.http_method_names if m.upper() != "OPTIONS"]

        return methods if methods else ["GET"]

    def _get_callback_name(self, callback: Any) -> str:
        """Get callback name for identification"""
        if hasattr(callback, "__name__"):
            return callback.__name__
        elif hasattr(callback, "cls"):
            return callback.cls.__name__
        elif hasattr(callback, "__class__"):
            return callback.__class__.__name__
        return str(callback)


class ServiceMountPointMapper:
    """Map service mount points from hub/apps/api/urls.py"""

    def __init__(self):
        self.mount_points = {}

    def map_from_file(self, urls_file: str) -> dict[str, str]:
        """
        Map service mount points from urls.py file.

        Args:
            urls_file: Path to hub/apps/api/urls.py

        Returns:
            Dictionary mapping service names to URL module paths
        """
        if not os.path.exists(urls_file):
            return {}

        try:
            with open(urls_file, encoding="utf-8") as f:
                content = f.read()

            # Parse AST to extract path() and include() patterns
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for path() calls
                    if isinstance(node.func, ast.Name) and node.func.id == "path":
                        self._extract_path_mapping(node)
                    elif isinstance(node.func, ast.Name) and node.func.id == "include":
                        self._extract_include_mapping(node)

        except Exception as e:
            print(f"Error parsing urls.py: {e}", file=sys.stderr)

        return self.mount_points

    def _extract_path_mapping(self, node: ast.Call):
        """Extract path() -> include() mappings"""
        if len(node.args) >= 2:
            # First arg is the path prefix
            prefix_node = node.args[0]
            if isinstance(prefix_node, ast.Constant):
                prefix = prefix_node.value
            elif isinstance(prefix_node, ast.Str):  # Python < 3.8
                prefix = prefix_node.s

            # Second arg might be include()
            include_node = node.args[1]
            if isinstance(include_node, ast.Call):
                if isinstance(include_node.func, ast.Name) and include_node.func.id == "include":
                    if len(include_node.args) > 0:
                        module_node = include_node.args[0]
                        if isinstance(module_node, ast.Constant) or isinstance(
                            module_node, ast.Str
                        ):
                            module = module_node.value

                        # Extract service name from prefix
                        service_name = prefix.rstrip("/").split("/")[-1] if prefix else ""
                        if service_name:
                            self.mount_points[service_name] = module

    def _extract_include_mapping(self, node: ast.Call):
        """Extract include() mappings"""
        if len(node.args) > 0:
            module_node = node.args[0]
            if isinstance(module_node, ast.Constant) or isinstance(module_node, ast.Str):
                module = module_node.value

            # Extract service name from module path
            if isinstance(module, str):
                parts = module.split(".")
                if len(parts) >= 3:
                    # Extract service name (e.g., 'hub.apps.auth.urls' -> 'auth')
                    if "apps" in parts:
                        idx = parts.index("apps")
                        if idx + 1 < len(parts):
                            service_name = parts[idx + 1]
                            self.mount_points[service_name] = module


class DuplicateServiceNameDetector:
    """Detect duplicate service names and paths"""

    def detect(self, endpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect duplicate endpoints.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            List of duplicate endpoint reports
        """
        duplicates = []

        # Group by path
        path_groups = defaultdict(list)
        for endpoint in endpoints:
            path = endpoint.get("full_path", "")
            if path:
                path_groups[path].append(endpoint)

        # Find duplicates
        for path, endpoint_list in path_groups.items():
            if len(endpoint_list) > 1:
                duplicates.append(
                    {
                        "type": "duplicate_path",
                        "path": path,
                        "count": len(endpoint_list),
                        "endpoints": endpoint_list,
                    }
                )

        # Group by name
        name_groups = defaultdict(list)
        for endpoint in endpoints:
            name = endpoint.get("name", "")
            if name:
                name_groups[name].append(endpoint)

        # Find duplicate names
        for name, endpoint_list in name_groups.items():
            if len(endpoint_list) > 1:
                # Check if they're actually different endpoints
                paths = set(e.get("full_path", "") for e in endpoint_list)
                if len(paths) > 1:
                    duplicates.append(
                        {
                            "type": "duplicate_name",
                            "name": name,
                            "count": len(endpoint_list),
                            "endpoints": endpoint_list,
                        }
                    )

        return duplicates


class InconsistentNamingPatternDetector:
    """Detect inconsistent naming patterns"""

    def detect(self, endpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect inconsistent naming patterns.

        Args:
            endpoints: List of endpoint dictionaries

        Returns:
            List of inconsistency reports
        """
        inconsistencies = []

        # Group by service
        service_groups = defaultdict(list)
        for endpoint in endpoints:
            service = endpoint.get("service", "")
            if service:
                service_groups[service].append(endpoint)

        # Check naming patterns within each service
        for service, service_endpoints in service_groups.items():
            # Check name prefix consistency
            name_prefixes = {}
            for endpoint in service_endpoints:
                name = endpoint.get("name", "")
                if name:
                    # Extract prefix (e.g., 'auth-login' -> 'auth')
                    parts = name.split("-")
                    if len(parts) > 1:
                        prefix = parts[0]
                        if prefix not in name_prefixes:
                            name_prefixes[prefix] = []
                        name_prefixes[prefix].append(endpoint)

            # If multiple prefixes exist, flag inconsistency
            if len(name_prefixes) > 1:
                inconsistencies.append(
                    {
                        "type": "inconsistent_name_prefix",
                        "service": service,
                        "prefixes": list(name_prefixes.keys()),
                        "endpoints": service_endpoints,
                    }
                )

            # Check path naming consistency
            path_patterns = {}
            for endpoint in service_endpoints:
                path = endpoint.get("full_path", "")
                if path:
                    # Extract pattern (e.g., '/api/v1/auth/login/' -> 'login')
                    parts = path.rstrip("/").split("/")
                    if len(parts) > 0:
                        last_part = parts[-1]
                        if last_part not in path_patterns:
                            path_patterns[last_part] = []
                        path_patterns[last_part].append(endpoint)

        return inconsistencies


class EndpointInventoryGenerator:
    """Generate endpoint inventory"""

    def generate(
        self,
        endpoints: list[dict[str, Any]],
        group_by: str = "service",
    ) -> dict[str, Any]:
        """
        Generate endpoint inventory.

        Args:
            endpoints: List of endpoint dictionaries
            group_by: Grouping strategy ('service', 'method', 'none')

        Returns:
            Inventory dictionary
        """
        inventory = {
            "summary": {
                "total_endpoints": len(endpoints),
                "total_services": len(set(e.get("service", "") for e in endpoints)),
            },
            "endpoints": endpoints,
        }

        # Group endpoints
        if group_by == "service":
            grouped = defaultdict(list)
            for endpoint in endpoints:
                service = endpoint.get("service", "unknown")
                grouped[service].append(endpoint)
            inventory["by_service"] = dict(grouped)
        elif group_by == "method":
            grouped = defaultdict(list)
            for endpoint in endpoints:
                methods = endpoint.get("methods", ["GET"])
                for method in methods:
                    grouped[method].append(endpoint)
            inventory["by_method"] = dict(grouped)

        return inventory


class EndpointAuditor:
    """Main endpoint auditor"""

    def __init__(self):
        self.parser = URLPatternParser()
        self.mapper = ServiceMountPointMapper()
        self.duplicate_detector = DuplicateServiceNameDetector()
        self.naming_detector = InconsistentNamingPatternDetector()
        self.inventory_generator = EndpointInventoryGenerator()

    def audit(
        self,
        urls_file: str,
        base_path: str = "/api/v1",
        check_duplicates: bool = True,
        check_naming: bool = True,
    ) -> dict[str, Any]:
        """
        Perform full endpoint audit.

        Args:
            urls_file: Path to hub/apps/api/urls.py
            base_path: Base API path
            check_duplicates: Whether to check for duplicates
            check_naming: Whether to check naming consistency

        Returns:
            Audit results dictionary
        """
        # Map service mount points
        mount_points = self.mapper.map_from_file(urls_file)

        # Load Django URL configuration
        try:
            # Set up Django environment
            django_setup_done = False
            if "DJANGO_SETTINGS_MODULE" not in os.environ:
                # Find project root - urls_file is hub/apps/api/urls.py
                # Resolve to absolute path first
                urls_path = Path(urls_file)
                if not urls_path.is_absolute():
                    urls_path = Path.cwd() / urls_path
                urls_path = urls_path.resolve()

                # Find the directory containing 'hub' directory
                # urls_path is /app/hub/apps/api/urls.py
                # We need to find /app (which contains hub/)
                # Simple approach: walk up until we find a directory that contains 'hub' subdirectory
                current = urls_path
                project_root = None
                max_iterations = 10
                iteration = 0

                # Start from the file's parent directory and walk up
                # urls_path is /app/hub/apps/api/urls.py
                # We want to find /app (which contains hub/)
                current = urls_path.parent  # Start at /app/hub/apps/api
                while current != current.parent and iteration < max_iterations:
                    # Check if current directory contains 'hub' subdirectory
                    # For /app/hub/apps/api, we check /app/hub/apps/api/hub - doesn't exist
                    # For /app/hub/apps, we check /app/hub/apps/hub - doesn't exist
                    # For /app/hub, we check /app/hub/hub - doesn't exist
                    # For /app, we check /app/hub - EXISTS!
                    if (current / "hub").is_dir() and (
                        current / "hub" / "apps" / "api" / "urls.py"
                    ).exists():
                        project_root = current
                        break
                    current = current.parent
                    iteration += 1

                if not project_root:
                    # Fallback: use current working directory
                    cwd = Path.cwd()
                    if (cwd / "hub" / "apps" / "api" / "urls.py").exists():
                        project_root = cwd
                    else:
                        # Last resort: assume /app (Docker environment)
                        project_root = Path("/app")

                # Ensure project_root is absolute and exists
                project_root = project_root.resolve()
                if not (project_root / "hub" / "apps" / "api" / "urls.py").exists():
                    # Final fallback: try /app
                    if Path("/app/hub/apps/api/urls.py").exists():
                        project_root = Path("/app")

                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
                # Add project root to Python path (must be first, before any other paths)
                project_root_str = str(project_root.resolve())
                # Remove from path if already there, then insert at beginning
                if project_root_str in sys.path:
                    sys.path.remove(project_root_str)
                sys.path.insert(0, project_root_str)

                django_setup_done = True

            import django

            if not django_setup_done or not django.apps.apps.ready:
                django.setup()

            # Import URL configuration
            from django.urls import get_resolver

            # Get resolver for the API URLs
            resolver = get_resolver()

            # Find API v1 resolver
            api_resolver = None
            for pattern in resolver.url_patterns:
                if hasattr(pattern, "pattern") and "api/v1" in str(pattern.pattern):
                    if hasattr(pattern, "url_patterns"):
                        api_resolver = pattern
                        break

            # Parse all URL patterns
            # Start with prefix that includes base_path
            initial_prefix = base_path.rstrip("/") + "/"
            all_endpoints = []
            if api_resolver:
                self._parse_resolver(
                    api_resolver, base_path, initial_prefix, all_endpoints, mount_points
                )
            else:
                # Fallback: parse all patterns
                self._parse_resolver(
                    resolver, base_path, initial_prefix, all_endpoints, mount_points
                )

        except Exception as e:
            print(f"Error loading Django URLs: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            return {"error": str(e), "endpoints": []}

        # Generate inventory
        inventory = self.inventory_generator.generate(all_endpoints)

        # Detect issues
        issues = {}
        if check_duplicates:
            issues["duplicates"] = self.duplicate_detector.detect(all_endpoints)
        if check_naming:
            issues["naming_inconsistencies"] = self.naming_detector.detect(all_endpoints)

        return {
            "inventory": inventory,
            "issues": issues,
            "mount_points": mount_points,
        }

    def _parse_resolver(
        self,
        resolver: Any,
        base_path: str,
        prefix: str,
        endpoints: list[dict[str, Any]],
        mount_points: dict[str, str],
    ):
        """Recursively parse URL resolver"""
        if not hasattr(resolver, "url_patterns"):
            return

        for pattern in resolver.url_patterns:
            # Determine service name from mount points
            service_name = ""
            urlconf_name = getattr(pattern, "urlconf_name", None)
            if urlconf_name and isinstance(urlconf_name, str):
                module = str(urlconf_name)
                # Find matching mount point
                for service, mod in mount_points.items():
                    if mod == module:
                        service_name = service
                        break
                # Also try to extract from module path
                if not service_name:
                    parts = module.split(".")
                    if len(parts) >= 3 and "apps" in parts:
                        idx = parts.index("apps")
                        if idx + 1 < len(parts):
                            service_name = parts[idx + 1]

            # If we still don't have a service name, try to infer from prefix
            if not service_name and prefix:
                # Extract service from prefix (e.g., "/api/v1/auth/" -> "auth")
                parts = prefix.rstrip("/").split("/")
                if len(parts) >= 3 and parts[-1]:  # parts[-1] is the service name
                    service_name = parts[-1]

            # Check if this is an include pattern (URLResolver) or a direct pattern (URLPattern)
            if hasattr(pattern, "urlconf_name"):
                # This is a URLResolver (include pattern) - it contributes to the prefix
                urlconf_name = pattern.urlconf_name

                # Skip if urlconf_name is not a string (some resolvers have lists or other types)
                if not isinstance(urlconf_name, str):
                    # Try to get url_patterns directly if available
                    if hasattr(pattern, "url_patterns"):
                        # This resolver already has its patterns loaded
                        pattern_prefix = ""
                        if hasattr(pattern, "pattern"):
                            pattern_prefix = str(pattern.pattern)
                            pattern_prefix = pattern_prefix.replace("^", "").replace("$", "")

                        # Build new prefix
                        if pattern_prefix:
                            prefix_clean = prefix.rstrip("/") if prefix else ""
                            pattern_clean = pattern_prefix.lstrip("/")
                            if prefix_clean:
                                new_prefix = prefix_clean + "/" + pattern_clean
                            else:
                                new_prefix = pattern_clean
                            new_prefix = re.sub(r"/+", "/", new_prefix)
                            if not new_prefix.endswith("/"):
                                new_prefix += "/"
                        else:
                            new_prefix = (
                                prefix
                                if prefix.endswith("/")
                                else (prefix + "/" if prefix else "/")
                            )

                        # Parse the patterns directly
                        self._parse_resolver(
                            pattern,
                            base_path,
                            new_prefix,
                            endpoints,
                            mount_points,
                        )
                    continue

                pattern_prefix = ""
                if hasattr(pattern, "pattern"):
                    pattern_prefix = str(pattern.pattern)
                    # Remove regex anchors
                    pattern_prefix = pattern_prefix.replace("^", "").replace("$", "")

                # Build new prefix by combining current prefix with pattern_prefix
                # Example: prefix="/api/v1/", pattern_prefix="auth/" -> new_prefix="/api/v1/auth/"
                if pattern_prefix:
                    prefix_clean = prefix.rstrip("/") if prefix else ""
                    pattern_clean = pattern_prefix.lstrip("/")
                    if prefix_clean:
                        new_prefix = prefix_clean + "/" + pattern_clean
                    else:
                        new_prefix = pattern_clean
                    new_prefix = re.sub(r"/+", "/", new_prefix)
                    if not new_prefix.endswith("/"):
                        new_prefix += "/"
                else:
                    new_prefix = (
                        prefix if prefix.endswith("/") else (prefix + "/" if prefix else "/")
                    )

                # Recursively parse included patterns with new prefix
                try:
                    from django.urls import get_resolver

                    included_resolver = get_resolver(urlconf_name)
                    self._parse_resolver(
                        included_resolver,
                        base_path,
                        new_prefix,
                        endpoints,
                        mount_points,
                    )
                except Exception as e:
                    # Log error but continue - some includes might fail
                    if hasattr(self, "_verbose") and self._verbose:
                        print(f"Warning: Failed to parse {urlconf_name}: {e}", file=sys.stderr)
            else:
                # This is a URLPattern (direct endpoint) - use current prefix as-is
                # The pattern's own pattern_str will be appended in _parse_path_pattern
                result = self.parser.parse_pattern(pattern, base_path, prefix, service_name)
                if result and result.get("type") != "include":
                    endpoints.append(result)

    def output_json(self, data: dict[str, Any]) -> str:
        """Output data as JSON"""
        return json.dumps(data, indent=2, default=str)

    def output_markdown(self, data: dict[str, Any]) -> str:
        """Output data as Markdown"""
        lines = ["# API Endpoint Audit Report\n"]

        # Summary
        inventory = data.get("inventory", {})
        summary = inventory.get("summary", {})
        lines.append("## Summary\n")
        lines.append(f"- Total Endpoints: {summary.get('total_endpoints', 0)}")
        lines.append(f"- Total Services: {summary.get('total_services', 0)}\n")

        # Issues
        issues = data.get("issues", {})
        if issues:
            lines.append("## Issues\n")

            duplicates = issues.get("duplicates", [])
            if duplicates:
                lines.append("### Duplicate Endpoints\n")
                for dup in duplicates:
                    lines.append(
                        f"- **{dup.get('type', 'unknown')}**: {dup.get('path', dup.get('name', ''))}"
                    )
                    lines.append(f"  - Count: {dup.get('count', 0)}")

            naming = issues.get("naming_inconsistencies", [])
            if naming:
                lines.append("### Naming Inconsistencies\n")
                for inc in naming:
                    lines.append(
                        f"- **{inc.get('type', 'unknown')}**: Service '{inc.get('service', '')}'"
                    )
                    if "prefixes" in inc:
                        lines.append(f"  - Prefixes: {', '.join(inc['prefixes'])}")

        # Endpoints by service
        by_service = inventory.get("by_service", {})
        if by_service:
            lines.append("\n## Endpoints by Service\n")
            for service, service_endpoints in sorted(by_service.items()):
                lines.append(f"### {service.title()}\n")
                for endpoint in service_endpoints:
                    path = endpoint.get("full_path", endpoint.get("pattern", ""))
                    name = endpoint.get("name", "")
                    methods = ", ".join(endpoint.get("methods", ["GET"]))
                    lines.append(f"- `{methods}` {path}")
                    if name:
                        lines.append(f"  - Name: `{name}`")
                lines.append("")

        return "\n".join(lines)


def find_urls_file() -> str | None:
    """Find hub/apps/api/urls.py file"""
    # Try multiple possible locations
    possible_paths = [
        "hub/apps/api/urls.py",
        "../hub/apps/api/urls.py",
        "../../hub/apps/api/urls.py",
        Path(__file__).parent.parent / "hub" / "apps" / "api" / "urls.py",
    ]

    for path in possible_paths:
        full_path = Path(path).resolve()
        if full_path.exists():
            return str(full_path)

    return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Audit Django REST Framework API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--urls-file",
        type=str,
        default=None,
        help="Path to hub/apps/api/urls.py (default: auto-detect)",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--check-duplicates",
        action="store_true",
        default=True,
        help="Check for duplicate endpoints (default: True)",
    )
    parser.add_argument(
        "--no-check-duplicates",
        dest="check_duplicates",
        action="store_false",
        help="Disable duplicate checking",
    )
    parser.add_argument(
        "--check-naming",
        action="store_true",
        default=True,
        help="Check for inconsistent naming patterns (default: True)",
    )
    parser.add_argument(
        "--no-check-naming",
        dest="check_naming",
        action="store_false",
        help="Disable naming consistency checking",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Find URLs file
    urls_file = args.urls_file or find_urls_file()
    if not urls_file:
        print("Error: Could not find hub/apps/api/urls.py", file=sys.stderr)
        print("Please specify --urls-file option", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(urls_file):
        print(f"Error: URLs file not found: {urls_file}", file=sys.stderr)
        sys.exit(1)

    # Run audit
    auditor = EndpointAuditor()
    try:
        results = auditor.audit(
            urls_file,
            check_duplicates=args.check_duplicates,
            check_naming=args.check_naming,
        )
    except Exception as e:
        print(f"Error during audit: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    # Generate output
    if args.output_format == "json":
        output = auditor.output_json(results)
    else:
        output = auditor.output_markdown(results)

    # Write output
    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(output)
        if args.verbose:
            print(f"Output written to {args.output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
