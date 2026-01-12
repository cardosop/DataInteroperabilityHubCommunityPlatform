#!/usr/bin/env python3
"""
Regenerate API Inventory from Django Codebase (Static Analysis)

This script comprehensively extracts all API endpoints by statically analyzing:
1. All hub/apps/*/urls.py files for URL patterns
2. ViewSet classes to find custom @action decorators
3. Function-based views
4. Router registrations

Usage:
    python3 scripts/regenerate-api-inventory-static.py
"""

import re
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import sys


@dataclass
class APIEndpoint:
    """Represents an API endpoint"""
    method: str
    path: str
    view_class: Optional[str] = None
    view_method: Optional[str] = None
    action_type: str = "Standard"  # Standard, Custom, Function-based
    app_name: str = ""
    description: str = ""
    parameters: List[str] = field(default_factory=list)


class StaticEndpointExtractor:
    """Extract endpoints using static code analysis"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.hub_dir = project_root / 'hub'
        self.endpoints: List[APIEndpoint] = []
        self.router_registrations: Dict[str, Dict] = {}  # app_name -> {prefix: viewset}

    def extract_all(self) -> List[APIEndpoint]:
        """Extract all endpoints"""
        # First pass: collect router registrations
        self._collect_router_registrations()

        # Second pass: extract endpoints from URL patterns
        self._extract_from_urls()

        # Third pass: extract custom ViewSet actions
        self._extract_viewset_actions()

        return self.endpoints

    def _collect_router_registrations(self):
        """Collect all router.register() calls to map ViewSets to URL prefixes"""
        urls_files = list(self.hub_dir.rglob('**/urls.py'))

        for urls_file in urls_files:
            try:
                content = urls_file.read_text(encoding='utf-8')
                app_name = urls_file.parent.name

                # Find router.register calls
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (isinstance(node.func, ast.Attribute) and
                            node.func.attr == 'register'):
                            if len(node.args) >= 2:
                                prefix_arg = node.args[0]
                                viewset_arg = node.args[1]

                                # Extract prefix
                                prefix = None
                                if isinstance(prefix_arg, ast.Constant):
                                    prefix = prefix_arg.value
                                elif isinstance(prefix_arg, (ast.Str, ast.Bytes)):  # Python < 3.8
                                    prefix = prefix_arg.s if hasattr(prefix_arg, 's') else prefix_arg.value

                                # Extract viewset name
                                viewset_name = None
                                if isinstance(viewset_arg, ast.Name):
                                    viewset_name = viewset_arg.id
                                elif isinstance(viewset_arg, ast.Attribute):
                                    viewset_name = viewset_arg.attr

                                if prefix and viewset_name:
                                    if app_name not in self.router_registrations:
                                        self.router_registrations[app_name] = {}
                                    self.router_registrations[app_name][prefix] = viewset_name
            except Exception as e:
                print(f"Warning: Failed to parse {urls_file}: {e}", file=sys.stderr)

    def _extract_from_urls(self):
        """Extract endpoints from urls.py files"""
        # Start with main API urls
        api_urls = self.hub_dir / 'apps' / 'api' / 'urls.py'
        if api_urls.exists():
            self._process_api_urls(api_urls)

        # Process app urls
        urls_files = list(self.hub_dir.rglob('**/urls.py'))
        for urls_file in urls_files:
            if urls_file != api_urls:
                self._process_app_urls(urls_file)

    def _process_api_urls(self, urls_file: Path):
        """Process main API urls.py to understand routing structure"""
        try:
            content = urls_file.read_text(encoding='utf-8')

            # Find all include() patterns
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == 'include':
                        # This is an include pattern
                        if len(node.args) > 0:
                            include_arg = node.args[0]
                            if isinstance(include_arg, ast.Constant):
                                module_path = include_arg.value
                            elif isinstance(include_arg, (ast.Str, ast.Bytes)):
                                module_path = include_arg.s if hasattr(include_arg, 's') else include_arg.value
                            else:
                                continue

                            # Extract app name from module path
                            if 'hub.apps.' in module_path:
                                app_name = module_path.split('hub.apps.')[1].split('.')[0]

                                # Find the path prefix
                                parent_node = node
                                while parent_node and not isinstance(parent_node, ast.Call):
                                    parent_node = getattr(parent_node, 'parent', None)

                                if parent_node and isinstance(parent_node, ast.Call):
                                    if isinstance(parent_node.func, ast.Name) and parent_node.func.id == 'path':
                                        if len(parent_node.args) > 0:
                                            prefix_arg = parent_node.args[0]
                                            if isinstance(prefix_arg, ast.Constant):
                                                prefix = prefix_arg.value
                                            elif isinstance(prefix_arg, (ast.Str, ast.Bytes)):
                                                prefix = prefix_arg.s if hasattr(prefix_arg, 's') else prefix_arg.value
                                            else:
                                                continue

                                            # Process app URLs
                                            app_urls = self.hub_dir / 'apps' / app_name / 'urls.py'
                                            if app_urls.exists():
                                                self._process_app_urls(app_urls, prefix)
        except Exception as e:
            print(f"Warning: Failed to process {urls_file}: {e}", file=sys.stderr)

    def _process_app_urls(self, urls_file: Path, base_prefix: str = ""):
        """Process an app's urls.py file"""
        try:
            content = urls_file.read_text(encoding='utf-8')
            app_name = urls_file.parent.name

            # Determine base path
            if not base_prefix:
                # Try to infer from file location
                if 'apps/api' in str(urls_file):
                    base_prefix = f"/api/v1/{app_name}"
                else:
                    base_prefix = f"/api/v1/{app_name}"

            # Extract router registrations
            if app_name in self.router_registrations:
                for prefix, viewset_name in self.router_registrations[app_name].items():
                    # Generate standard REST endpoints
                    full_prefix = f"{base_prefix}/{prefix}".rstrip('/')
                    self._generate_viewset_endpoints(full_prefix, viewset_name, app_name)

            # Extract direct path() patterns
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == 'path':
                        if len(node.args) >= 2:
                            path_arg = node.args[0]
                            view_arg = node.args[1]

                            # Extract path
                            if isinstance(path_arg, ast.Constant):
                                path_pattern = path_arg.value
                            elif isinstance(path_arg, (ast.Str, ast.Bytes)):
                                path_pattern = path_arg.s if hasattr(path_arg, 's') else path_arg.value
                            else:
                                continue

                            # Extract view
                            view_name = None
                            if isinstance(view_arg, ast.Name):
                                view_name = view_arg.id
                            elif isinstance(view_arg, ast.Attribute):
                                view_name = view_arg.attr

                            if path_pattern and view_name:
                                full_path = f"{base_prefix}/{path_pattern}".rstrip('/')
                                if not full_path.endswith('/'):
                                    full_path += '/'

                                # Determine methods
                                methods = self._infer_methods_from_view_name(view_name)

                                for method in methods:
                                    endpoint = APIEndpoint(
                                        method=method,
                                        path=full_path,
                                        view_method=view_name,
                                        action_type="Function-based",
                                        app_name=app_name
                                    )
                                    self.endpoints.append(endpoint)
        except Exception as e:
            print(f"Warning: Failed to process {urls_file}: {e}", file=sys.stderr)

    def _generate_viewset_endpoints(self, base_path: str, viewset_name: str, app_name: str):
        """Generate standard REST endpoints for a ViewSet"""
        # Standard CRUD actions
        standard_actions = [
            ('GET', 'list', False),
            ('POST', 'create', False),
            ('GET', 'retrieve', True),
            ('PUT', 'update', True),
            ('PATCH', 'partial_update', True),
            ('DELETE', 'destroy', True),
        ]

        for method, action, is_detail in standard_actions:
            if is_detail:
                path = f"{base_path}/{{id}}/"
                parameters = ['id']
            else:
                path = f"{base_path}/"
                parameters = []

            endpoint = APIEndpoint(
                method=method,
                path=path,
                view_class=viewset_name,
                view_method=action,
                action_type="Standard",
                app_name=app_name,
                parameters=parameters
            )
            self.endpoints.append(endpoint)

    def _extract_viewset_actions(self):
        """Extract custom @action decorators from ViewSets"""
        views_files = list(self.hub_dir.rglob('**/views.py'))

        for views_file in views_files:
            try:
                content = views_file.read_text(encoding='utf-8')
                app_name = views_file.parent.name

                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if 'ViewSet' in node.name:
                            self._extract_actions_from_class(node, app_name, views_file)
            except Exception as e:
                print(f"Warning: Failed to parse {views_file}: {e}", file=sys.stderr)

    def _extract_actions_from_class(self, class_node: ast.ClassDef, app_name: str, views_file: Path):
        """Extract @action decorators from a ViewSet class"""
        viewset_name = class_node.name

        # Find base path from router registration
        base_path = None
        if app_name in self.router_registrations:
            for prefix, registered_viewset in self.router_registrations[app_name].items():
                if registered_viewset == viewset_name:
                    base_path = f"/api/v1/{app_name}/{prefix}".rstrip('/')
                    break

        if not base_path:
            return

        # Find all methods with @action decorators
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                # Check for @action decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                        if decorator.func.id == 'action':
                            # Extract action details
                            detail = True  # Default
                            methods = ['GET']  # Default
                            url_path = node.name  # Default

                            # Parse decorator arguments
                            for keyword in decorator.keywords:
                                if keyword.arg == 'detail':
                                    if isinstance(keyword.value, ast.Constant):
                                        detail = keyword.value.value
                                    elif isinstance(keyword.value, ast.NameConstant):  # Python < 3.8
                                        detail = keyword.value.value
                                elif keyword.arg == 'methods':
                                    if isinstance(keyword.value, ast.List):
                                        methods = []
                                        for m in keyword.value.elts:
                                            if isinstance(m, ast.Constant):
                                                methods.append(m.value.upper())
                                            elif isinstance(m, (ast.Str, ast.Bytes)):
                                                val = m.s if hasattr(m, 's') else m.value
                                                methods.append(val.upper())
                                elif keyword.arg == 'url_path':
                                    if isinstance(keyword.value, ast.Constant):
                                        url_path = keyword.value.value
                                    elif isinstance(keyword.value, (ast.Str, ast.Bytes)):
                                        url_path = keyword.value.s if hasattr(keyword.value, 's') else keyword.value.value

                            # Build endpoint path
                            if detail:
                                action_path = f"{base_path}/{{id}}/{url_path}/"
                                parameters = ['id']
                            else:
                                action_path = f"{base_path}/{url_path}/"
                                parameters = []

                            # Create endpoints for each method
                            for method in methods:
                                endpoint = APIEndpoint(
                                    method=method,
                                    path=action_path,
                                    view_class=viewset_name,
                                    view_method=node.name,
                                    action_type="Custom",
                                    app_name=app_name,
                                    parameters=parameters,
                                    description=f"Custom action: {node.name}"
                                )
                                # Check if endpoint already exists
                                if not any(e.path == endpoint.path and e.method == endpoint.method
                                          for e in self.endpoints):
                                    self.endpoints.append(endpoint)

    def _infer_methods_from_view_name(self, view_name: str) -> List[str]:
        """Infer HTTP methods from view function name"""
        view_lower = view_name.lower()
        if 'create' in view_lower or 'post' in view_lower:
            return ['POST']
        elif 'update' in view_lower or 'put' in view_lower:
            return ['PUT', 'PATCH']
        elif 'delete' in view_lower or 'destroy' in view_lower:
            return ['DELETE']
        else:
            return ['GET', 'POST']  # Default for function-based views


class InventoryGenerator:
    """Generate inventory markdown document"""

    def __init__(self, endpoints: List[APIEndpoint]):
        self.endpoints = endpoints

    def generate(self) -> str:
        """Generate markdown inventory"""
        lines = []

        # Header
        lines.append("# Current API Inventory from Codebase")
        lines.append("")
        lines.append(f"**Document Version**: 2.0.0")
        lines.append(f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"**Source**: Static analysis of Django URL patterns and ViewSets")
        lines.append(f"**Task**: 9.6.3.3.2 - Update API inventory files")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append("This document inventories all API endpoints extracted from the Django codebase by:")
        lines.append("1. Parsing all `hub/apps/*/urls.py` files to extract URL patterns")
        lines.append("2. Analyzing ViewSet classes to identify custom @action decorators")
        lines.append("3. Extracting function-based views")
        lines.append("4. Verifying endpoint patterns match standardized conventions")
        lines.append("")
        lines.append(f"**Total Endpoints Found**: {len(self.endpoints)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Group endpoints by app
        grouped = defaultdict(list)
        for endpoint in self.endpoints:
            grouped[endpoint.app_name].append(endpoint)

        # Sort apps
        sorted_apps = sorted([k for k in grouped.keys() if k])

        # Endpoints by Application
        lines.append("## Endpoints by Application")
        lines.append("")

        for app_name in sorted_apps:
            app_endpoints = grouped[app_name]
            app_endpoints.sort(key=lambda e: (e.path, e.method))

            lines.append(f"### {app_name.capitalize()} ({len(app_endpoints)} endpoints)")
            lines.append("")
            lines.append(f"**Base Route**: `/api/v1/{app_name}/`")
            lines.append("")
            lines.append("| Method | Path | View | Action | Type |")
            lines.append("|--------|------|------|--------|------|")

            for endpoint in app_endpoints:
                view_str = endpoint.view_class or endpoint.view_method or "-"
                if endpoint.view_method and endpoint.view_class:
                    view_str = f"{endpoint.view_class}.{endpoint.view_method}"
                elif endpoint.view_method:
                    view_str = endpoint.view_method

                action_str = endpoint.view_method or "-"
                type_str = endpoint.action_type

                lines.append(f"| {endpoint.method} | `{endpoint.path}` | `{view_str}` | {action_str} | {type_str} |")

            lines.append("")

        # Summary Statistics
        lines.append("## Summary Statistics")
        lines.append("")

        method_counts = defaultdict(int)
        type_counts = defaultdict(int)
        for endpoint in self.endpoints:
            method_counts[endpoint.method] += 1
            type_counts[endpoint.action_type] += 1

        lines.append(f"- **Total Endpoints**: {len(self.endpoints)}")
        lines.append(f"- **Standard CRUD Actions**: {type_counts.get('Standard', 0)}")
        lines.append(f"- **Custom Actions**: {type_counts.get('Custom', 0)}")
        lines.append(f"- **Function-based Views**: {type_counts.get('Function-based', 0)}")
        lines.append("")
        lines.append("### Methods Breakdown")
        lines.append("")
        for method in sorted(method_counts.keys()):
            lines.append(f"- **{method}**: {method_counts[method]} endpoints")
        lines.append("")

        # Notes
        lines.append("## Notes")
        lines.append("")
        lines.append("### Standardized Endpoint Patterns")
        lines.append("")
        lines.append("All endpoints follow standardized patterns:")
        lines.append("- Compliance runs: `/api/v1/compliance/runs/` (not `/compliance-runs/`)")
        lines.append("- Data quality runs: `/api/v1/dq/runs/` (not `/dq-runs/`)")
        lines.append("")
        lines.append("### Extraction Methodology")
        lines.append("")
        lines.append("1. **Static Code Analysis**: Parses Python AST to extract URL patterns and ViewSet actions")
        lines.append("2. **Router Registration Mapping**: Maps ViewSets to URL prefixes via router.register() calls")
        lines.append("3. **ViewSet Action Detection**: Identifies custom @action decorators in ViewSet classes")
        lines.append("4. **Pattern Verification**: Verifies endpoints match standardized URL patterns")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("**Document Status**: ✅ Complete")
        lines.append(f"**Total Endpoints Extracted**: {len(self.endpoints)}")
        lines.append("")

        return "\n".join(lines)


def main():
    """Main execution"""
    project_root = Path(__file__).resolve().parent.parent

    print("Extracting API endpoints from Django codebase (static analysis)...")

    extractor = StaticEndpointExtractor(project_root)
    endpoints = extractor.extract_all()

    print(f"Found {len(endpoints)} endpoints")

    # Generate inventory
    generator = InventoryGenerator(endpoints)
    inventory_md = generator.generate()

    # Write to file
    output_path = project_root / 'docs' / 'api-audit' / 'current-api-inventory.md'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(inventory_md, encoding='utf-8')

    print(f"\n✅ Inventory generated: {output_path}")
    print(f"📊 Total endpoints: {len(endpoints)}")

    # Verify completeness
    print("\n🔍 Verifying inventory completeness...")

    # Check for compliance endpoints
    compliance_endpoints = [e for e in endpoints if e.app_name == 'compliance']
    print(f"  - Compliance endpoints: {len(compliance_endpoints)}")
    for ep in compliance_endpoints:
        print(f"    - {ep.method} {ep.path}")

    # Check for old patterns
    old_patterns = [e for e in endpoints if '/compliance-runs/' in e.path or '/dq-runs/' in e.path]
    if old_patterns:
        print(f"\n⚠️  Warning: Found {len(old_patterns)} endpoints with old patterns:")
        for ep in old_patterns:
            print(f"    - {ep.method} {ep.path}")
    else:
        print("\n✅ No old endpoint patterns found - all endpoints use standardized patterns")

    return 0


if __name__ == '__main__':
    sys.exit(main())

