#!/usr/bin/env python3
"""
Extract API Inventory from Django Codebase

This script analyzes Django URL patterns and ViewSets to extract
all API endpoints without requiring Django to be running.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class APIEndpoint:
    """Represents an API endpoint"""

    path: str
    method: str
    view_name: str | None = None
    view_class: str | None = None
    description: str | None = None
    parameters: list[str] = field(default_factory=list)
    file_path: str | None = None


class DjangoAPIExtractor:
    """Extracts API endpoints from Django codebase"""

    def __init__(self, hub_dir: Path):
        self.hub_dir = hub_dir
        self.endpoints: list[APIEndpoint] = []
        self.url_patterns: dict[str, list] = {}

    def extract_all(self):
        """Extract all API endpoints"""
        print("Scanning Django URL patterns...")

        # Find all urls.py files
        urls_files = list(self.hub_dir.rglob("**/urls.py"))
        print(f"Found {len(urls_files)} urls.py files")

        # Process main urls.py first
        main_urls = self.hub_dir / "hub" / "urls.py"
        if main_urls.exists():
            self._process_urls_file(main_urls, is_main=True)

        # Process app urls.py files
        for urls_file in urls_files:
            if urls_file != main_urls:
                self._process_urls_file(urls_file)

        # Extract from ViewSets
        self._extract_from_viewsets()

        return self.endpoints

    def _process_urls_file(self, urls_file: Path, is_main: bool = False):
        """Process a urls.py file to extract URL patterns"""
        try:
            content = urls_file.read_text(encoding="utf-8")
            relative_path = urls_file.relative_to(self.hub_dir)

            print(f"Processing: {relative_path}")

            # Extract urlpatterns
            patterns = self._extract_urlpatterns(content, urls_file)

            for pattern in patterns:
                self.endpoints.append(pattern)

        except Exception as e:
            print(f"Error processing {urls_file}: {e}")

    def _extract_urlpatterns(self, content: str, file_path: Path) -> list[APIEndpoint]:
        """Extract URL patterns from Python code"""
        endpoints = []

        # Pattern for url() or path() calls
        url_pattern = re.compile(
            r"(?:url|path|re_path)\s*\(\s*"
            r'["\']([^"\']+)["\']\s*,\s*'
            r"([^,)]+)",
            re.MULTILINE,
        )

        # Pattern for include() with namespace
        re.compile(r'include\s*\(\s*["\']([^"\']+)["\']\s*\)', re.MULTILINE)

        # Pattern for router registration
        router_pattern = re.compile(
            r"(?:router|DefaultRouter)\s*\.\s*register\s*\(\s*"
            r'["\']([^"\']+)["\']\s*,\s*'
            r"([^,)]+)",
            re.MULTILINE,
        )

        # Extract direct URL patterns
        for match in url_pattern.finditer(content):
            path = match.group(1)
            view = match.group(2).strip()

            # Clean up path (remove regex markers if present)
            clean_path = path.replace("^", "").replace("$", "")

            # Determine HTTP methods from view
            methods = self._extract_methods_from_view(view, file_path)

            for method in methods:
                endpoint = APIEndpoint(
                    path=clean_path,
                    method=method,
                    view_name=view,
                    file_path=str(file_path.relative_to(self.hub_dir)),
                )
                endpoints.append(endpoint)

        # Extract router registrations
        for match in router_pattern.finditer(content):
            prefix = match.group(1)
            viewset = match.group(2).strip()

            # Determine the URL prefix based on file location
            # Check parent URLs to determine full path
            url_prefix = self._determine_url_prefix(file_path, prefix)

            # Generate standard REST endpoints with correct prefix
            rest_endpoints = self._generate_rest_endpoints_with_prefix(
                url_prefix, prefix, viewset, file_path
            )
            endpoints.extend(rest_endpoints)

        return endpoints

    def _extract_methods_from_view(self, view: str, file_path: Path) -> list[str]:
        """Extract HTTP methods from view definition"""
        methods = ["GET"]  # Default

        # Check if it's a ViewSet or APIView
        if "ViewSet" in view or "APIView" in view:
            # Try to find the view class
            view_class_path = self._resolve_view_class(view, file_path)
            if view_class_path:
                methods = self._extract_methods_from_class(view_class_path)

        # Check for explicit method decorators
        if "@" in view or "method" in view.lower():
            # Common patterns
            if "post" in view.lower() or "create" in view.lower():
                methods.append("POST")
            if "put" in view.lower() or "update" in view.lower():
                methods.append("PUT")
            if "delete" in view.lower() or "destroy" in view.lower():
                methods.append("DELETE")
            if "patch" in view.lower():
                methods.append("PATCH")

        return list(set(methods))

    def _resolve_view_class(self, view: str, file_path: Path) -> Path | None:
        """Resolve view class file path"""
        # Extract module path
        if "." in view:
            parts = view.split(".")
            parts[-1]
            module_parts = parts[:-1]
        else:
            module_parts = []

        # Try to find the file
        if module_parts:
            module_path = Path(*module_parts)
            view_file = self.hub_dir / module_path / "views.py"
            if view_file.exists():
                return view_file

        # Try relative to current file
        view_file = file_path.parent / "views.py"
        if view_file.exists():
            return view_file

        return None

    def _extract_methods_from_class(self, view_file: Path) -> list[str]:
        """Extract HTTP methods from ViewSet class"""
        methods = []

        try:
            content = view_file.read_text(encoding="utf-8")

            # Check for standard ViewSet methods
            if "create" in content:
                methods.append("POST")
            if "list" in content or "retrieve" in content:
                methods.append("GET")
            if "update" in content:
                methods.append("PUT")
            if "partial_update" in content:
                methods.append("PATCH")
            if "destroy" in content:
                methods.append("DELETE")

            # Check for @action decorators
            action_pattern = re.compile(
                r"@action\s*\([^)]*methods\s*=\s*\[([^\]]+)\]", re.MULTILINE
            )
            for match in action_pattern.finditer(content):
                action_methods = [m.strip().strip("\"'") for m in match.group(1).split(",")]
                methods.extend(action_methods)

        except Exception as e:
            print(f"Error reading view file {view_file}: {e}")

        return list(set(methods)) if methods else ["GET"]

    def _generate_rest_endpoints(
        self, prefix: str, viewset: str, file_path: Path
    ) -> list[APIEndpoint]:
        """Generate standard REST endpoints for a ViewSet"""
        endpoints = []

        # Determine base path - check if it's under /api/v1/ or root
        # Most apps are under /api/v1/ based on apps/api/urls.py
        if "api" in str(file_path) or any(
            app in str(file_path)
            for app in [
                "assets",
                "contracts",
                "datasets",
                "jobs",
                "marketplace",
                "scheduled_ingestion",
                "users",
                "audit",
                "files",
                "compliance",
                "dq",
                "governance",
                "search",
                "webhooks",
            ]
        ):
            base_path = f"/api/v1/{prefix}"
        else:
            base_path = f"/{prefix}"

        # Standard REST endpoints
        # List/Create
        endpoints.append(
            APIEndpoint(
                path=base_path,
                method="GET",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"List {prefix}",
            )
        )
        endpoints.append(
            APIEndpoint(
                path=base_path,
                method="POST",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Create {prefix}",
            )
        )

        # Detail endpoints
        detail_path = f"{base_path}/{{id}}"
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="GET",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Get {prefix} by ID",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="PUT",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Update {prefix}",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="PATCH",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Partially update {prefix}",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="DELETE",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Delete {prefix}",
                parameters=["id"],
            )
        )

        return endpoints

    def _determine_url_prefix(self, urls_file: Path, router_prefix: str) -> str:
        """Determine the full URL prefix for a router registration"""
        # Check if this is under /api/v1/
        if "apps/api" in str(urls_file) or any(
            app in str(urls_file)
            for app in [
                "assets",
                "contracts",
                "datasets",
                "jobs",
                "marketplace",
                "scheduled_ingestion",
                "users",
                "audit",
                "files",
                "compliance",
                "dq",
                "governance",
                "search",
                "webhooks",
            ]
        ):
            # Check parent urls.py to see the path prefix
            parent_urls = urls_file.parent.parent / "api" / "urls.py"
            if parent_urls.exists():
                content = parent_urls.read_text(encoding="utf-8")
                # Look for include pattern that matches this app
                app_name = urls_file.parent.name
                pattern = re.compile(
                    rf"path\s*\(['\"]([^'\"]+)['\"]\s*,\s*include\s*\(['\"]hub\.apps\.{app_name}\.urls",
                    re.MULTILINE,
                )
                match = pattern.search(content)
                if match:
                    parent_prefix = match.group(1).rstrip("/")
                    return f"/api/v1{parent_prefix}/{router_prefix}"
                return f"/api/v1/{router_prefix}"
            return f"/api/v1/{router_prefix}"
        return f"/{router_prefix}"

    def _generate_rest_endpoints_with_prefix(
        self, url_prefix: str, router_prefix: str, viewset: str, file_path: Path
    ) -> list[APIEndpoint]:
        """Generate REST endpoints with full URL prefix"""
        endpoints = []

        # Standard REST endpoints
        base_path = url_prefix.rstrip("/")

        # List/Create
        endpoints.append(
            APIEndpoint(
                path=base_path,
                method="GET",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"List {router_prefix}",
            )
        )
        endpoints.append(
            APIEndpoint(
                path=base_path,
                method="POST",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Create {router_prefix}",
            )
        )

        # Detail endpoints
        detail_path = f"{base_path}/{{id}}"
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="GET",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Get {router_prefix} by ID",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="PUT",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Update {router_prefix}",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="PATCH",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Partially update {router_prefix}",
                parameters=["id"],
            )
        )
        endpoints.append(
            APIEndpoint(
                path=detail_path,
                method="DELETE",
                view_class=viewset,
                file_path=str(file_path.relative_to(self.hub_dir)),
                description=f"Delete {router_prefix}",
                parameters=["id"],
            )
        )

        return endpoints

    def _extract_from_viewsets(self):
        """Extract custom actions from ViewSets"""
        views_files = list(self.hub_dir.rglob("**/views.py"))

        for views_file in views_files:
            try:
                content = views_file.read_text(encoding="utf-8")
                relative_path = views_file.relative_to(self.hub_dir)

                # Find ViewSet class name
                viewset_match = re.search(r"class\s+(\w+ViewSet)", content)
                if not viewset_match:
                    continue

                viewset_name = viewset_match.group(1)

                # Find @action decorators with more context
                action_pattern = re.compile(
                    r"@action\s*\(([^)]+)\)\s*\n\s*def\s+(\w+)", re.MULTILINE | re.DOTALL
                )

                for match in action_pattern.finditer(content):
                    decorator_content = match.group(1)
                    action_name = match.group(2)

                    # Extract detail flag
                    detail_match = re.search(r"detail\s*=\s*(True|False)", decorator_content)
                    detail = detail_match.group(1) == "True" if detail_match else False

                    # Extract methods from decorator
                    methods_match = re.search(r"methods\s*=\s*\[([^\]]+)\]", decorator_content)
                    methods = ["GET"]  # Default
                    if methods_match:
                        methods = [
                            m.strip().strip("\"'") for m in methods_match.group(1).split(",")
                        ]

                    # Extract URL path if specified
                    url_path_match = re.search(
                        r'url_path\s*=\s*["\']([^"\']+)["\']', decorator_content
                    )
                    url_path = url_path_match.group(1) if url_path_match else action_name

                    # Determine base path from router registration
                    base_path = self._find_viewset_base_path(viewset_name, views_file)

                    if base_path:
                        if detail:
                            action_path = f"{base_path}/{{id}}/{url_path}"
                            params = ["id"]
                        else:
                            action_path = f"{base_path}/{url_path}"
                            params = []

                        for method in methods:
                            endpoint = APIEndpoint(
                                path=action_path,
                                method=method.upper(),
                                view_class=viewset_name,
                                file_path=str(relative_path),
                                description=f"Custom action: {action_name}",
                                parameters=params,
                            )
                            # Check if endpoint already exists (avoid duplicates)
                            if not any(
                                e.path == endpoint.path and e.method == endpoint.method
                                for e in self.endpoints
                            ):
                                self.endpoints.append(endpoint)
                                print(
                                    f"Found custom action: {method.upper()} {action_path} ({action_name})"
                                )

            except Exception as e:
                print(f"Error processing views file {views_file}: {e}")

    def _find_viewset_base_path(self, viewset_name: str, views_file: Path) -> str | None:
        """Find the base URL path for a ViewSet by checking router registrations"""
        # Look for router.register in urls.py files
        urls_files = list(views_file.parent.glob("urls.py"))
        if not urls_files:
            urls_files = list(views_file.parent.parent.glob("*/urls.py"))

        for urls_file in urls_files:
            try:
                content = urls_file.read_text(encoding="utf-8")
                # Look for router.register with this viewset
                pattern = re.compile(
                    rf"router\.register\s*\([^,]+,\s*{viewset_name}[^)]*\)", re.MULTILINE
                )
                match = pattern.search(content)
                if match:
                    # Extract the prefix
                    prefix_match = re.search(
                        r'router\.register\s*\(["\']([^"\']+)["\']', match.group(0)
                    )
                    if prefix_match:
                        router_prefix = prefix_match.group(1)
                        # Determine full path
                        return self._determine_url_prefix(urls_file, router_prefix)
            except Exception:
                continue

        return None

    def generate_inventory(self, output_path: Path):
        """Generate inventory report"""
        endpoints = self.extract_all()

        # Deduplicate
        seen = set()
        unique_endpoints = []
        for endpoint in endpoints:
            key = (endpoint.path, endpoint.method)
            if key not in seen:
                seen.add(key)
                unique_endpoints.append(endpoint)

        # Group by path prefix
        grouped = defaultdict(list)
        for endpoint in unique_endpoints:
            prefix = endpoint.path.split("/")[1] if len(endpoint.path.split("/")) > 1 else "root"
            grouped[prefix].append(endpoint)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Current API Inventory (Extracted from Django Codebase)\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Endpoints:** {len(unique_endpoints)}\n")
            f.write("**Source:** Django URL patterns and ViewSets\n\n")

            f.write("## Summary Statistics\n\n")
            method_counts = defaultdict(int)
            for endpoint in unique_endpoints:
                method_counts[endpoint.method] += 1

            f.write(f"- **Total Endpoints:** {len(unique_endpoints)}\n")
            f.write("- **Methods Distribution:**\n")
            for method, count in sorted(method_counts.items()):
                f.write(f"  - **{method}:** {count}\n")
            f.write(f"- **Path Prefixes:** {len(grouped)}\n")
            f.write("\n")

            f.write("## Endpoints by Path Prefix\n\n")
            for prefix in sorted(grouped.keys()):
                endpoints = grouped[prefix]
                f.write(f"### /{prefix}\n\n")
                f.write(f"**Count:** {len(endpoints)}\n\n")

                for endpoint in sorted(endpoints, key=lambda e: (e.path, e.method)):
                    f.write(f"#### {endpoint.method} {endpoint.path}\n\n")

                    if endpoint.description:
                        f.write(f"**Description:** {endpoint.description}\n\n")

                    if endpoint.view_class:
                        f.write(f"**View Class:** `{endpoint.view_class}`\n\n")

                    if endpoint.view_name:
                        f.write(f"**View Name:** `{endpoint.view_name}`\n\n")

                    if endpoint.parameters:
                        f.write(f"**Parameters:** {', '.join(endpoint.parameters)}\n\n")

                    if endpoint.file_path:
                        f.write(f"**Source File:** `{endpoint.file_path}`\n\n")

                    f.write("---\n\n")

            # Complete list
            f.write("## Complete Endpoint List\n\n")
            f.write("| Method | Path | View Class | Source File |\n")
            f.write("|--------|------|------------|-------------|\n")

            for endpoint in sorted(unique_endpoints, key=lambda e: (e.path, e.method)):
                view_class = endpoint.view_class or endpoint.view_name or ""
                file_path = endpoint.file_path or ""
                f.write(
                    f"| {endpoint.method} | `{endpoint.path}` | `{view_class}` | `{file_path}` |\n"
                )

        print(f"\n✅ Inventory generated: {output_path}")
        print(f"📊 Total endpoints: {len(unique_endpoints)}")


def main():
    """Main execution"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    hub_dir = repo_root / "hub"
    output_dir = repo_root / "docs" / "api-audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "current-api-inventory.md"

    if not hub_dir.exists():
        print(f"Error: hub directory not found at {hub_dir}")
        return 1

    extractor = DjangoAPIExtractor(hub_dir)
    extractor.generate_inventory(output_path)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
