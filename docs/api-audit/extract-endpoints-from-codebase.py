#!/usr/bin/env python3
"""
Extract API Endpoints from Codebase

This script systematically extracts all API endpoints from:
1. All hub/apps/*/urls.py files
2. ViewSet classes and their @action decorators
3. Custom function-based views

Usage:
    python extract-endpoints-from-codebase.py > docs/api-audit/codebase-endpoints-inventory.md
"""

import os
import re
import ast
import importlib.util
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class APIEndpoint:
    """Represents an API endpoint"""
    method: str
    path: str
    view_class: str
    view_method: str
    app_name: str
    description: str = ""
    is_custom_action: bool = False
    is_deprecated: bool = False
    parameters: List[str] = field(default_factory=list)
    in_openapi: bool = False


class EndpointExtractor:
    """Extract endpoints from Django URL configuration"""
    
    def __init__(self, base_path: str = "hub/apps"):
        self.base_path = Path(base_path)
        self.endpoints: List[APIEndpoint] = []
        self.app_routes: Dict[str, str] = {}  # app_name -> base_route
        
    def extract_all_endpoints(self) -> List[APIEndpoint]:
        """Extract all endpoints from codebase"""
        # First, map app names to their routes from api/urls.py
        self._extract_app_routes()
        
        # Then extract endpoints from each app
        urls_files = list(self.base_path.glob("*/urls.py"))
        urls_files.extend(list(self.base_path.glob("*/*/urls.py")))  # For nested apps
        
        for urls_file in sorted(urls_files):
            if "api/urls.py" in str(urls_file):
                continue  # Skip main API urls.py
            self._extract_from_urls_file(urls_file)
        
        return self.endpoints
    
    def _extract_app_routes(self):
        """Extract app routes from hub/apps/api/urls.py"""
        api_urls = self.base_path / "api" / "urls.py"
        if not api_urls.exists():
            return
        
        with open(api_urls, 'r') as f:
            content = f.read()
        
        # Extract path('app-name/', include('hub.apps.app_name.urls'))
        pattern = r"path\('([^']+)',\s*include\('hub\.apps\.([^']+)\.urls'\)\)"
        matches = re.findall(pattern, content)
        
        for route, app_name in matches:
            # Handle nested apps like 'api/analytics'
            if '/' in route:
                app_name = route.replace('/', '_')
            self.app_routes[app_name] = route.rstrip('/')
    
    def _extract_from_urls_file(self, urls_file: Path):
        """Extract endpoints from a urls.py file"""
        app_name = urls_file.parent.name
        if urls_file.parent.parent.name != "apps":
            # Nested app like api/analytics
            app_name = f"{urls_file.parent.parent.name}_{urls_file.parent.name}"
        
        base_route = self.app_routes.get(app_name, app_name.replace('_', '-'))
        
        with open(urls_file, 'r') as f:
            content = f.read()
        
        # Extract router registrations
        router_pattern = r'router\.register\(r["\']([^"\']+)["\'],\s*(\w+ViewSet|(\w+)),\s*basename=["\']([^"\']+)["\']\)'
        router_matches = re.findall(router_pattern, content)
        
        for match in router_matches:
            resource_path = match[0]
            viewset_name = match[1]
            basename = match[3] if match[3] else resource_path.rstrip('s')  # Plural to singular
        
            # Extract ViewSet actions
            viewset_file = urls_file.parent / "views.py"
            if viewset_file.exists():
                actions = self._extract_viewset_actions(viewset_file, viewset_name, resource_path, base_route)
                self.endpoints.extend(actions)
        
        # Extract custom path() routes
        path_pattern = r"path\(['\"]([^'\"]+)['\"],\s*([^,]+),\s*name=['\"]([^'\"]+)['\"]\)"
        path_matches = re.findall(path_pattern, content)
        
        for path_match in path_matches:
            route_path = path_match[0]
            view = path_match[1].strip()
            name = path_match[2]
            
            # Determine HTTP method from view
            method = self._infer_method_from_view(view, urls_file.parent)
            
            endpoint = APIEndpoint(
                method=method,
                path=f"/api/v1/{base_route}/{route_path}".rstrip('/'),
                view_class=view,
                view_method="",
                app_name=app_name,
                description=f"Custom endpoint: {name}",
                is_custom_action=True
            )
            self.endpoints.append(endpoint)
    
    def _extract_viewset_actions(self, views_file: Path, viewset_name: str, resource_path: str, base_route: str) -> List[APIEndpoint]:
        """Extract all actions from a ViewSet"""
        actions = []
        
        with open(views_file, 'r') as f:
            content = f.read()
        
        # Find ViewSet class
        viewset_pattern = f'class {viewset_name}\\([^:]+:'
        if not re.search(viewset_pattern, content):
            return actions
        
        # Standard CRUD actions
        standard_actions = [
            ('list', 'GET', f'/{resource_path}/'),
            ('create', 'POST', f'/{resource_path}/'),
            ('retrieve', 'GET', f'/{resource_path}/{{id}}/'),
            ('update', 'PUT', f'/{resource_path}/{{id}}/'),
            ('partial_update', 'PATCH', f'/{resource_path}/{{id}}/'),
            ('destroy', 'DELETE', f'/{resource_path}/{{id}}/'),
        ]
        
        for action_name, method, path_template in standard_actions:
            # Check if method exists in ViewSet
            method_pattern = f'def {action_name}\\(self'
            if re.search(method_pattern, content):
                # Fix path: remove duplicate resource names
                full_path = f"/api/v1/{base_route}{path_template}"
                # Remove duplicate resource segments
                parts = full_path.split('/')
                cleaned_parts = []
                prev = None
                for part in parts:
                    if part != prev or not part:
                        cleaned_parts.append(part)
                    prev = part
                full_path = '/'.join(cleaned_parts)
                
                endpoint = APIEndpoint(
                    method=method,
                    path=full_path,
                    view_class=viewset_name,
                    view_method=action_name,
                    app_name=views_file.parent.name,
                    description=f"Standard {action_name} action"
                )
                actions.append(endpoint)
        
        # Extract @action decorators
        action_pattern = r'@action\([^)]+\)\s+def\s+(\w+)\(self'
        action_matches = re.findall(action_pattern, content)
        
        for action_method in action_matches:
            # Get action decorator details
            action_decorator_pattern = f'@action\\([^)]+\\)\\s+def\\s+{action_method}'
            decorator_match = re.search(action_decorator_pattern, content)
            if decorator_match:
                decorator_start = decorator_match.start()
                # Find the full decorator
                decorator_end = content.find(')', decorator_start) + 1
                decorator = content[decorator_start:decorator_end]
                
                # Extract detail, methods, url_path
                detail = 'detail=True' in decorator
                methods_match = re.search(r"methods=\[['\"]([^'\"]+)['\"]", decorator)
                method = methods_match.group(1).upper() if methods_match else 'GET'
                url_path_match = re.search(r"url_path=['\"]([^'\"]+)['\"]", decorator)
                url_path = url_path_match.group(1) if url_path_match else action_method.replace('_', '-')
                
                if detail:
                    path_template = f'/{resource_path}/{{id}}/{url_path}/'
                else:
                    path_template = f'/{resource_path}/{url_path}/'
                
                # Fix path: remove duplicate resource names (e.g., /assets/assets/ -> /assets/)
                full_path = f"/api/v1/{base_route}{path_template}"
                # Remove duplicate resource segments
                parts = full_path.split('/')
                cleaned_parts = []
                prev = None
                for part in parts:
                    if part != prev or not part:
                        cleaned_parts.append(part)
                    prev = part
                full_path = '/'.join(cleaned_parts)
                
                endpoint = APIEndpoint(
                    method=method,
                    path=full_path,
                    view_class=viewset_name,
                    view_method=action_method,
                    app_name=views_file.parent.name,
                    description=f"Custom action: {action_method}",
                    is_custom_action=True
                )
                actions.append(endpoint)
        
        return actions
    
    def _infer_method_from_view(self, view: str, app_dir: Path) -> str:
        """Infer HTTP method from view function/class"""
        # Default to GET for function-based views
        if 'as_view' in view:
            # Extract methods from as_view({'get': 'method', 'post': 'method'})
            methods_match = re.search(r"as_view\({\s*['\"](\w+)['\"]", view)
            if methods_match:
                return methods_match.group(1).upper()
        return 'GET'


def generate_markdown_report(endpoints: List[APIEndpoint]) -> str:
    """Generate markdown report from extracted endpoints"""
    report = []
    report.append("# Current API Inventory from Codebase")
    report.append("")
    report.append("**Document Version**: 1.0.0")
    report.append("**Last Updated**: 2025-12-13")
    report.append("**Source**: `hub/apps/*/urls.py` files")
    report.append("**Task**: 0.2.2 - Review codebase for API endpoints")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Overview")
    report.append("")
    report.append(f"This document inventories all API endpoints extracted from the codebase.")
    report.append(f"**Total Endpoints Found**: {len(endpoints)}")
    report.append("")
    
    # Group by app
    by_app = defaultdict(list)
    for endpoint in endpoints:
        by_app[endpoint.app_name].append(endpoint)
    
    report.append("## Endpoints by Application")
    report.append("")
    
    for app_name in sorted(by_app.keys()):
        app_endpoints = by_app[app_name]
        report.append(f"### {app_name.title().replace('_', ' ')} ({len(app_endpoints)} endpoints)")
        report.append("")
        
        # Group by resource
        by_resource = defaultdict(list)
        for endpoint in app_endpoints:
            # Extract resource from path (e.g., /api/v1/assets/ -> assets)
            path_parts = endpoint.path.split('/')
            if len(path_parts) >= 4:
                resource = path_parts[3]
                by_resource[resource].append(endpoint)
        
        for resource in sorted(by_resource.keys()):
            resource_endpoints = by_resource[resource]
            report.append(f"#### {resource.title()}")
            report.append("")
            report.append("| Method | Path | View | Action | Description |")
            report.append("|--------|------|------|--------|-------------|")
            
            for endpoint in sorted(resource_endpoints, key=lambda x: (x.method, x.path)):
                view_info = f"{endpoint.view_class}.{endpoint.view_method}" if endpoint.view_method else endpoint.view_class
                custom_marker = " (custom)" if endpoint.is_custom_action else ""
                deprecated_marker = " (deprecated)" if endpoint.is_deprecated else ""
                
                report.append(f"| {endpoint.method} | `{endpoint.path}` | `{view_info}` | {endpoint.view_method or 'N/A'} | {endpoint.description}{custom_marker}{deprecated_marker} |")
            
            report.append("")
    
    # Summary statistics
    report.append("## Summary Statistics")
    report.append("")
    
    methods = defaultdict(int)
    custom_actions = 0
    for endpoint in endpoints:
        methods[endpoint.method] += 1
        if endpoint.is_custom_action:
            custom_actions += 1
    
    report.append(f"- **Total Endpoints**: {len(endpoints)}")
    report.append(f"- **Custom Actions**: {custom_actions}")
    report.append(f"- **Standard CRUD**: {len(endpoints) - custom_actions}")
    report.append("")
    report.append("**Methods Breakdown**:")
    for method in sorted(methods.keys()):
        report.append(f"- {method}: {methods[method]}")
    
    report.append("")
    report.append("---")
    report.append("")
    report.append("**Document Status**: ✅ Complete")
    report.append(f"**Total Endpoints Extracted**: {len(endpoints)}")
    report.append("")
    report.append("**Next Steps**:")
    report.append("1. Compare with OpenAPI schema to identify missing endpoints")
    report.append("2. Identify deprecated endpoints (if any markers exist)")
    report.append("3. Document endpoints not in OpenAPI schema")
    
    return "\n".join(report)


if __name__ == "__main__":
    extractor = EndpointExtractor()
    endpoints = extractor.extract_all_endpoints()
    report = generate_markdown_report(endpoints)
    print(report)

