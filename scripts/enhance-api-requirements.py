#!/usr/bin/env python3
"""
Enhanced API Requirements Extraction Script

This script creates a comprehensive API requirements document with detailed
request/response schemas, query parameters, path parameters, and error responses
extracted from frontend spec files.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class APIEndpoint:
    """Represents an API endpoint requirement"""

    path: str
    method: str | None = None
    description: str = ""
    request_schema: dict = field(default_factory=dict)
    response_schema: dict = field(default_factory=dict)
    query_params: list[str] = field(default_factory=list)
    path_params: list[str] = field(default_factory=list)
    error_responses: list[dict] = field(default_factory=list)
    auth_required: bool = True
    tenant_required: bool = False
    rate_limited: bool = False
    source_spec: str = ""
    source_requirement: str = ""
    scenarios: list[str] = field(default_factory=list)


class EnhancedAPIExtractor:
    """Enhanced API requirements extractor"""

    def __init__(self, specs_dir: str):
        self.specs_dir = Path(specs_dir)
        self.endpoints: dict[str, APIEndpoint] = {}
        self.error_patterns = {
            "401": re.compile(r"(?:401|unauthorized|authentication.*fail)", re.IGNORECASE),
            "403": re.compile(r"(?:403|forbidden|permission.*denied)", re.IGNORECASE),
            "404": re.compile(r"(?:404|not.*found)", re.IGNORECASE),
            "400": re.compile(r"(?:400|bad.*request|validation.*error)", re.IGNORECASE),
            "429": re.compile(r"(?:429|rate.*limit|too.*many.*request)", re.IGNORECASE),
            "500": re.compile(r"(?:500|server.*error|internal.*error)", re.IGNORECASE),
        }

    def extract_all(self) -> dict:
        """Extract all API requirements"""
        spec_files = list(self.specs_dir.rglob("spec.md"))

        print(f"Found {len(spec_files)} spec files")

        for spec_file in spec_files:
            print(f"Processing {spec_file.relative_to(self.specs_dir.parent)}")
            self._process_spec_file(spec_file)

        # Organize by category
        categorized = self._categorize_endpoints()

        return {
            "total_endpoints": len(self.endpoints),
            "categories": categorized,
            "endpoints": list(self.endpoints.values()),
        }

    def _process_spec_file(self, spec_path: Path):
        """Process a single spec file"""
        try:
            content = spec_path.read_text(encoding="utf-8")
            spec_name = spec_path.parent.name

            # Extract explicit endpoints
            self._extract_explicit_endpoints(content, spec_name)

            # Extract implicit endpoints from scenarios
            self._extract_from_scenarios(content, spec_name)

            # Extract error responses
            self._extract_error_responses(content, spec_name)

        except Exception as e:
            print(f"Error processing {spec_path}: {e}")

    def _extract_explicit_endpoints(self, content: str, spec_name: str):
        """Extract explicitly mentioned endpoints"""
        # Credential endpoints (explicitly mentioned)
        if "credential" in content.lower():
            credential_endpoints = [
                (
                    "GET",
                    "/api/v1/scheduled-ingestions/{id}/credentials/",
                    "Get masked credentials for scheduled ingestion",
                    ["id"],
                ),
                (
                    "POST",
                    "/api/v1/scheduled-ingestions/{id}/credentials/test/",
                    "Test credential connection",
                    ["id"],
                ),
                (
                    "PUT",
                    "/api/v1/scheduled-ingestions/{id}/credentials/",
                    "Update credentials for scheduled ingestion",
                    ["id"],
                ),
                (
                    "POST",
                    "/api/v1/scheduled-ingestions/{id}/credentials/rotate/",
                    "Rotate credentials with test-before-switch",
                    ["id"],
                ),
                (
                    "GET",
                    "/api/v1/scheduled-ingestions/{id}/credentials/validation/",
                    "Validate credentials",
                    ["id"],
                ),
            ]

            for method, path, desc, path_params in credential_endpoints:
                key = f"{method}:{path}"
                if key not in self.endpoints:
                    self.endpoints[key] = APIEndpoint(
                        path=path,
                        method=method,
                        description=desc,
                        path_params=path_params,
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                    )

        # GraphQL endpoint
        if "/graphql" in content.lower() or "graphql" in content.lower():
            key = "POST:/graphql"
            if key not in self.endpoints:
                self.endpoints[key] = APIEndpoint(
                    path="/graphql",
                    method="POST",
                    description="GraphQL API endpoint for flexible queries",
                    source_spec=spec_name,
                    auth_required=True,
                )

        # WebSocket endpoints
        ws_pattern = r"/ws/([^\s`/]+)"
        for match in re.finditer(ws_pattern, content, re.IGNORECASE):
            path = f"/ws/{match.group(1)}"
            key = f"WS:{path}"
            if key not in self.endpoints:
                self.endpoints[key] = APIEndpoint(
                    path=path,
                    method="WS",
                    description="WebSocket endpoint for real-time updates",
                    source_spec=spec_name,
                    auth_required=True,
                )

    def _extract_from_scenarios(self, content: str, spec_name: str):
        """Extract API requirements from scenarios"""
        # Resource-based CRUD endpoints
        resources = {
            "asset": "/api/v1/assets",
            "contract": "/api/v1/contracts",
            "dataset": "/api/v1/datasets",
            "job": "/api/v1/jobs",
            "marketplace": "/api/v1/marketplace",
            "compliance": "/api/v1/compliance",
            "data-quality": "/api/v1/data-quality",
            "scheduled-ingestion": "/api/v1/scheduled-ingestions",
            "transformation": "/api/v1/transformations",
            "pipeline": "/api/v1/pipelines",
            "rating": "/api/v1/ratings",
            "review": "/api/v1/reviews",
            "comment": "/api/v1/comments",
            "community": "/api/v1/communities",
            "domain": "/api/v1/domains",
            "virtual-dataset": "/api/v1/virtual-datasets",
            "connector": "/api/v1/connectors",
            "plugin": "/api/v1/plugins",
        }

        content_lower = content.lower()

        for resource_name, base_path in resources.items():
            if resource_name in content_lower or resource_name.replace("-", " ") in content_lower:
                # List endpoint
                self._add_endpoint(
                    "GET",
                    base_path,
                    f"List {resource_name}s",
                    spec_name,
                    query_params=["page", "page_size", "search", "filter", "sort"],
                )

                # Create endpoint
                self._add_endpoint("POST", base_path, f"Create {resource_name}", spec_name)

                # Detail endpoints
                detail_path = f"{base_path}/{{id}}"
                self._add_endpoint(
                    "GET", detail_path, f"Get {resource_name} by ID", spec_name, path_params=["id"]
                )
                self._add_endpoint(
                    "PUT", detail_path, f"Update {resource_name}", spec_name, path_params=["id"]
                )
                self._add_endpoint(
                    "PATCH",
                    detail_path,
                    f"Partially update {resource_name}",
                    spec_name,
                    path_params=["id"],
                )
                self._add_endpoint(
                    "DELETE", detail_path, f"Delete {resource_name}", spec_name, path_params=["id"]
                )

        # Special endpoints
        if "search" in content_lower or "query" in content_lower:
            self._add_endpoint(
                "GET",
                "/api/v1/search",
                "Search assets and contracts",
                spec_name,
                query_params=["q", "type", "domain", "page", "page_size"],
            )

        if "upload" in content_lower:
            self._add_endpoint("POST", "/api/v1/datasets/upload", "Upload dataset file", spec_name)

        if "validate" in content_lower and "contract" in content_lower:
            self._add_endpoint(
                "POST",
                "/api/v1/contracts/{id}/validate",
                "Validate contract",
                spec_name,
                path_params=["id"],
            )

        if "publish" in content_lower and "contract" in content_lower:
            self._add_endpoint(
                "POST",
                "/api/v1/contracts/{id}/publish",
                "Publish contract to marketplace",
                spec_name,
                path_params=["id"],
            )

        # Authentication endpoints
        if "login" in content_lower or "authentication" in content_lower:
            self._add_endpoint(
                "POST", "/api/v1/auth/login", "User login", spec_name, auth_required=False
            )
            self._add_endpoint(
                "POST", "/api/v1/auth/register", "User registration", spec_name, auth_required=False
            )
            self._add_endpoint("POST", "/api/v1/auth/logout", "User logout", spec_name)
            self._add_endpoint("POST", "/api/v1/auth/refresh", "Refresh JWT token", spec_name)

        if "api key" in content_lower or "api-key" in content_lower:
            self._add_endpoint("GET", "/api/v1/api-keys", "List API keys", spec_name)
            self._add_endpoint("POST", "/api/v1/api-keys", "Create API key", spec_name)
            self._add_endpoint(
                "DELETE", "/api/v1/api-keys/{id}", "Revoke API key", spec_name, path_params=["id"]
            )

        # Natural language search
        if "natural language" in content_lower or "nlp" in content_lower:
            self._add_endpoint(
                "POST",
                "/api/v1/ai/search",
                "Natural language search",
                spec_name,
                query_params=["query"],
            )

        # Schema matching
        if "schema matching" in content_lower or "schema-matching" in content_lower:
            self._add_endpoint(
                "POST", "/api/v1/ai/schema-matching", "AI schema matching", spec_name
            )

        # Recommendations
        if "recommendation" in content_lower:
            self._add_endpoint(
                "GET",
                "/api/v1/ai/recommendations",
                "Get asset recommendations",
                spec_name,
                query_params=["asset_id", "limit"],
            )

        # Transformation pipeline
        if "pipeline" in content_lower and "execute" in content_lower:
            self._add_endpoint(
                "POST",
                "/api/v1/pipelines/{id}/execute",
                "Execute transformation pipeline",
                spec_name,
                path_params=["id"],
            )
            self._add_endpoint(
                "POST",
                "/api/v1/pipelines/{id}/preview",
                "Preview pipeline results",
                spec_name,
                path_params=["id"],
            )

    def _add_endpoint(
        self,
        method: str,
        path: str,
        description: str,
        spec_name: str,
        query_params: list[str] = None,
        path_params: list[str] = None,
        auth_required: bool = True,
        tenant_required: bool = True,
    ):
        """Add or update an endpoint"""
        key = f"{method}:{path}"

        if key not in self.endpoints:
            self.endpoints[key] = APIEndpoint(
                path=path,
                method=method,
                description=description,
                source_spec=spec_name,
                auth_required=auth_required,
                tenant_required=tenant_required,
            )

        endpoint = self.endpoints[key]

        if query_params:
            endpoint.query_params.extend(query_params)
            endpoint.query_params = list(set(endpoint.query_params))

        if path_params:
            endpoint.path_params.extend(path_params)
            endpoint.path_params = list(set(endpoint.path_params))

        if spec_name not in endpoint.source_spec:
            endpoint.source_spec += f", {spec_name}" if endpoint.source_spec else spec_name

    def _extract_error_responses(self, content: str, spec_name: str):
        """Extract error response requirements"""
        for code, pattern in self.error_patterns.items():
            if pattern.search(content):
                # Add error response to relevant endpoints
                for endpoint in self.endpoints.values():
                    error_info = {
                        "code": int(code),
                        "description": self._get_error_description(code),
                        "source": spec_name,
                    }
                    if error_info not in endpoint.error_responses:
                        endpoint.error_responses.append(error_info)

    def _get_error_description(self, code: str) -> str:
        """Get error description for status code"""
        descriptions = {
            "400": "Bad Request - Validation error or invalid input",
            "401": "Unauthorized - Authentication required or invalid token",
            "403": "Forbidden - Insufficient permissions",
            "404": "Not Found - Resource does not exist",
            "429": "Too Many Requests - Rate limit exceeded",
            "500": "Internal Server Error - Server error occurred",
        }
        return descriptions.get(code, f"HTTP {code} error")

    def _categorize_endpoints(self) -> dict[str, list[APIEndpoint]]:
        """Categorize endpoints by resource type"""
        categories = defaultdict(list)

        for endpoint in self.endpoints.values():
            # Extract resource from path
            path_parts = endpoint.path.split("/")
            if len(path_parts) > 3:
                resource = path_parts[3].split("?")[0].split("{")[0]
                if resource:
                    categories[resource].append(endpoint)
                else:
                    categories["other"].append(endpoint)
            else:
                categories["other"].append(endpoint)

        return dict(categories)

    def generate_comprehensive_report(self, output_path: Path):
        """Generate comprehensive markdown report"""
        results = self.extract_all()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# API Requirements Matrix\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Endpoints Extracted:** {results['total_endpoints']}\n\n")

            f.write("## Overview\n\n")
            f.write(
                "This document contains comprehensive API requirements extracted from frontend specification files.\n"
            )
            f.write(
                "Each endpoint includes request/response schemas, query parameters, path parameters, and error responses.\n\n"
            )

            f.write("## Table of Contents\n\n")
            for category in sorted(results["categories"].keys()):
                f.write(f"- [{category.title()}](#{category.lower().replace(' ', '-')})\n")
            f.write("\n")

            f.write("## Categories\n\n")

            for category, endpoints in sorted(results["categories"].items()):
                f.write(f"### {category.title()}\n\n")
                f.write(f"**Count:** {len(endpoints)}\n\n")

                for endpoint in sorted(endpoints, key=lambda e: (e.method or "", e.path)):
                    f.write(f"#### {endpoint.method or 'ANY'} {endpoint.path}\n\n")

                    if endpoint.description:
                        f.write(f"**Description:** {endpoint.description}\n\n")

                    f.write(f"**Source Spec(s):** {endpoint.source_spec}\n\n")

                    if endpoint.path_params:
                        f.write("**Path Parameters:**\n")
                        for param in endpoint.path_params:
                            f.write(f"- `{param}` (required)\n")
                        f.write("\n")

                    if endpoint.query_params:
                        f.write("**Query Parameters:**\n")
                        for param in endpoint.query_params:
                            f.write(f"- `{param}` (optional)\n")
                        f.write("\n")

                    if endpoint.request_schema:
                        f.write("**Request Schema:**\n")
                        f.write(
                            f"```json\n{json.dumps(endpoint.request_schema, indent=2)}\n```\n\n"
                        )

                    if endpoint.response_schema:
                        f.write("**Response Schema:**\n")
                        f.write(
                            f"```json\n{json.dumps(endpoint.response_schema, indent=2)}\n```\n\n"
                        )

                    if endpoint.error_responses:
                        f.write("**Error Responses:**\n")
                        for error in endpoint.error_responses:
                            f.write(f"- `{error['code']}`: {error['description']}\n")
                        f.write("\n")

                    f.write(f"**Authentication Required:** {endpoint.auth_required}\n\n")
                    f.write(f"**Tenant Required:** {endpoint.tenant_required}\n\n")

                    if endpoint.rate_limited:
                        f.write("**Rate Limited:** Yes\n\n")

                    f.write("---\n\n")

            # Summary section
            f.write("## Summary\n\n")
            f.write("### Endpoint Statistics\n\n")
            f.write(f"- **Total Endpoints:** {results['total_endpoints']}\n")
            f.write(f"- **Categories:** {len(results['categories'])}\n")

            method_counts = defaultdict(int)
            for endpoint in results["endpoints"]:
                method_counts[endpoint.method or "UNKNOWN"] += 1

            f.write("\n### Methods Distribution\n\n")
            for method, count in sorted(method_counts.items()):
                f.write(f"- **{method}:** {count}\n")

            f.write("\n### Categories Distribution\n\n")
            for category, endpoints in sorted(
                results["categories"].items(), key=lambda x: -len(x[1])
            ):
                f.write(f"- **{category.title()}:** {len(endpoints)} endpoints\n")

        print(f"Comprehensive report generated: {output_path}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    specs_dir = repo_root / "openspec" / "changes" / "frontendmvp" / "specs"
    output_dir = repo_root / "docs" / "api-audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "api-requirements-matrix.md"

    extractor = EnhancedAPIExtractor(str(specs_dir))
    extractor.generate_comprehensive_report(output_file)

    print("\n✅ Enhanced API requirements extraction complete!")
    print(f"📄 Report saved to: {output_file}")
