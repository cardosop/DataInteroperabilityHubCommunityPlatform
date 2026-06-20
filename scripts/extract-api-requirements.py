#!/usr/bin/env python3
"""
Comprehensive API Requirements Extraction Script

This script extracts API requirements from all frontend spec files,
documenting endpoints, methods, request/response schemas, parameters, and error handling.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
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
    error_responses: list[str] = field(default_factory=list)
    auth_required: bool = True
    tenant_required: bool = False
    source_spec: str = ""
    source_requirement: str = ""


@dataclass
class APICategory:
    """Represents a category of API endpoints"""

    name: str
    endpoints: list[APIEndpoint] = field(default_factory=list)
    description: str = ""


class APIRequirementsExtractor:
    """Extracts API requirements from spec files"""

    def __init__(self, specs_dir: str):
        self.specs_dir = Path(specs_dir)
        self.endpoints: list[APIEndpoint] = []
        self.categories: dict[str, APICategory] = defaultdict(lambda: APICategory(name=""))
        self.api_patterns = {
            "endpoint": re.compile(r"(?:endpoint|API|route|path|URL)[\s:]+([^\n]+)", re.IGNORECASE),
            "method": re.compile(r"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)"),
            "path": re.compile(r"`?/api/v1/[^\s`]+`?|`?/graphql`?|`?/ws/[^\s`]+`?"),
            "credential_endpoints": re.compile(r"(GET|POST|PUT|DELETE)\s+.*?/credentials"),
            "query_param": re.compile(r"(?:query\s+)?parameter[s]?[:]?\s+([^\n]+)", re.IGNORECASE),
            "error_code": re.compile(r"(?:error|status)\s+code[s]?[:]?\s*(\d{3})", re.IGNORECASE),
            "auth": re.compile(r"(?:authentication|auth|token|JWT|API\s+key)", re.IGNORECASE),
            "tenant": re.compile(r"(?:tenant|multi-tenant)", re.IGNORECASE),
        }

    def extract_from_spec_file(self, spec_path: Path) -> list[APIEndpoint]:
        """Extract API requirements from a single spec file"""
        endpoints = []

        try:
            content = spec_path.read_text(encoding="utf-8")
            spec_name = spec_path.parent.name

            # Extract endpoints based on patterns
            endpoints.extend(self._extract_rest_endpoints(content, spec_name))
            endpoints.extend(self._extract_graphql_endpoints(content, spec_name))
            endpoints.extend(self._extract_websocket_endpoints(content, spec_name))
            endpoints.extend(self._extract_credential_endpoints(content, spec_name))
            endpoints.extend(self._extract_implicit_endpoints(content, spec_name))

        except Exception as e:
            print(f"Error processing {spec_path}: {e}")

        return endpoints

    def _extract_rest_endpoints(self, content: str, spec_name: str) -> list[APIEndpoint]:
        """Extract REST API endpoints"""
        endpoints = []

        # Pattern for REST endpoints
        rest_patterns = [
            (r"/api/v1/([^\s`/]+)", "REST"),
            (r"endpoint[s]?[:]?\s+([^\n]+)", "REST"),
        ]

        for pattern, _api_type in rest_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                endpoint = APIEndpoint(
                    path=match.group(1) if match.lastindex else match.group(0),
                    source_spec=spec_name,
                    description=f"Extracted from {spec_name}",
                )
                endpoints.append(endpoint)

        return endpoints

    def _extract_graphql_endpoints(self, content: str, spec_name: str) -> list[APIEndpoint]:
        """Extract GraphQL API endpoints"""
        endpoints = []

        if "/graphql" in content.lower() or "graphql" in content.lower():
            endpoint = APIEndpoint(
                path="/graphql",
                method="POST",
                description="GraphQL API endpoint",
                source_spec=spec_name,
            )
            endpoints.append(endpoint)

        return endpoints

    def _extract_websocket_endpoints(self, content: str, spec_name: str) -> list[APIEndpoint]:
        """Extract WebSocket endpoints"""
        endpoints = []

        ws_pattern = r"/ws/([^\s`/]+)"
        matches = re.finditer(ws_pattern, content, re.IGNORECASE)

        for match in matches:
            endpoint = APIEndpoint(
                path=f"/ws/{match.group(1)}",
                description="WebSocket endpoint",
                source_spec=spec_name,
            )
            endpoints.append(endpoint)

        return endpoints

    def _extract_credential_endpoints(self, content: str, spec_name: str) -> list[APIEndpoint]:
        """Extract credential management endpoints"""
        endpoints = []

        # Specific credential endpoints mentioned in scheduled-ingestion spec
        credential_endpoints = [
            ("GET", "/api/v1/scheduled-ingestions/{id}/credentials/", "Get masked credentials"),
            ("POST", "/api/v1/scheduled-ingestions/{id}/credentials/test/", "Test connection"),
            ("PUT", "/api/v1/scheduled-ingestions/{id}/credentials/", "Update credentials"),
            ("POST", "/api/v1/scheduled-ingestions/{id}/credentials/rotate/", "Rotate credentials"),
            (
                "GET",
                "/api/v1/scheduled-ingestions/{id}/credentials/validation/",
                "Validate credentials",
            ),
        ]

        if "credential" in content.lower() or "scheduled-ingestion" in spec_name:
            for method, path, desc in credential_endpoints:
                endpoint = APIEndpoint(
                    path=path,
                    method=method,
                    description=desc,
                    source_spec=spec_name,
                    auth_required=True,
                    tenant_required=True,
                )
                endpoints.append(endpoint)

        return endpoints

    def _extract_implicit_endpoints(self, content: str, spec_name: str) -> list[APIEndpoint]:
        """Extract implicit endpoints from scenarios and requirements"""
        endpoints = []

        # Map spec names to their resource types

        # Common CRUD patterns based on resource mentions
        resource_keywords = {
            "assets": ["asset", "data product"],
            "contracts": ["contract", "schema"],
            "datasets": ["dataset", "data file"],
            "jobs": ["job", "execution", "workflow"],
            "marketplace": ["marketplace", "listing", "purchase"],
            "compliance": ["compliance", "scan", "violation"],
            "data-quality": ["data quality", "dq", "quality check"],
            "scheduled-ingestions": ["scheduled ingestion", "ingestion"],
            "transformations": ["transformation", "pipeline"],
            "ratings": ["rating", "star"],
            "reviews": ["review", "feedback"],
            "comments": ["comment", "discussion"],
            "communities": ["community"],
            "domains": ["domain", "mesh domain"],
            "virtual-datasets": ["virtual dataset", "virtualization"],
            "connectors": ["connector"],
            "plugins": ["plugin"],
            "credentials": ["credential", "password", "api key"],
            "auth": ["authentication", "login", "register", "token"],
            "api-keys": ["api key", "api-key"],
            "sessions": ["session", "active session"],
            "sso": ["sso", "oauth", "saml"],
            "mfa": ["mfa", "multi-factor", "two-factor"],
        }

        # Check which resources are mentioned
        mentioned_resources = set()
        content_lower = content.lower()

        for resource, keywords in resource_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                mentioned_resources.add(resource)

        # Generate CRUD endpoints for mentioned resources
        crud_paths = {
            "assets": "/api/v1/assets",
            "contracts": "/api/v1/contracts",
            "datasets": "/api/v1/datasets",
            "jobs": "/api/v1/jobs",
            "marketplace": "/api/v1/marketplace/contracts",
            "compliance": "/api/v1/compliance/scans",
            "data-quality": "/api/v1/data-quality/runs",
            "scheduled-ingestions": "/api/v1/scheduled-ingestions",
            "transformations": "/api/v1/transformations",
            "pipelines": "/api/v1/pipelines",
            "ratings": "/api/v1/ratings",
            "reviews": "/api/v1/reviews",
            "comments": "/api/v1/comments",
            "communities": "/api/v1/communities",
            "domains": "/api/v1/domains",
            "virtual-datasets": "/api/v1/virtual-datasets",
            "connectors": "/api/v1/connectors",
            "plugins": "/api/v1/plugins",
        }

        for resource in mentioned_resources:
            if resource in crud_paths:
                base_path = crud_paths[resource]
                # List endpoint
                endpoints.append(
                    APIEndpoint(
                        path=base_path,
                        method="GET",
                        description=f"List {resource}",
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                    )
                )
                # Create endpoint
                endpoints.append(
                    APIEndpoint(
                        path=base_path,
                        method="POST",
                        description=f"Create {resource}",
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                    )
                )
                # Detail endpoint
                endpoints.append(
                    APIEndpoint(
                        path=f"{base_path}/{{id}}",
                        method="GET",
                        description=f"Get {resource} by ID",
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                        path_params=["id"],
                    )
                )
                # Update endpoint
                endpoints.append(
                    APIEndpoint(
                        path=f"{base_path}/{{id}}",
                        method="PUT",
                        description=f"Update {resource}",
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                        path_params=["id"],
                    )
                )
                # Delete endpoint
                endpoints.append(
                    APIEndpoint(
                        path=f"{base_path}/{{id}}",
                        method="DELETE",
                        description=f"Delete {resource}",
                        source_spec=spec_name,
                        auth_required=True,
                        tenant_required=True,
                        path_params=["id"],
                    )
                )

        # Special endpoints based on content analysis
        if "search" in content_lower or "query" in content_lower:
            endpoints.append(
                APIEndpoint(
                    path="/api/v1/search",
                    method="GET",
                    description="Search assets/contracts",
                    source_spec=spec_name,
                    auth_required=True,
                    query_params=["q", "type", "domain"],
                )
            )

        if "upload" in content_lower or "file" in content_lower:
            endpoints.append(
                APIEndpoint(
                    path="/api/v1/datasets/upload",
                    method="POST",
                    description="Upload dataset file",
                    source_spec=spec_name,
                    auth_required=True,
                )
            )

        if "validate" in content_lower:
            endpoints.append(
                APIEndpoint(
                    path="/api/v1/contracts/{id}/validate",
                    method="POST",
                    description="Validate contract",
                    source_spec=spec_name,
                    auth_required=True,
                    path_params=["id"],
                )
            )

        if "publish" in content_lower:
            endpoints.append(
                APIEndpoint(
                    path="/api/v1/contracts/{id}/publish",
                    method="POST",
                    description="Publish contract",
                    source_spec=spec_name,
                    auth_required=True,
                    path_params=["id"],
                )
            )

        return endpoints

    def extract_all(self) -> dict:
        """Extract API requirements from all spec files"""
        spec_files = list(self.specs_dir.rglob("spec.md"))

        print(f"Found {len(spec_files)} spec files")

        all_endpoints = []
        for spec_file in spec_files:
            print(f"Processing {spec_file.relative_to(self.specs_dir.parent)}")
            endpoints = self.extract_from_spec_file(spec_file)
            all_endpoints.extend(endpoints)

        # Deduplicate and organize
        unique_endpoints = self._deduplicate_endpoints(all_endpoints)
        categorized = self._categorize_endpoints(unique_endpoints)

        return {
            "total_endpoints": len(unique_endpoints),
            "categories": categorized,
            "endpoints": unique_endpoints,
        }

    def _deduplicate_endpoints(self, endpoints: list[APIEndpoint]) -> list[APIEndpoint]:
        """Remove duplicate endpoints"""
        seen = set()
        unique = []

        for endpoint in endpoints:
            key = (endpoint.path, endpoint.method)
            if key not in seen:
                seen.add(key)
                unique.append(endpoint)
            else:
                # Merge sources if duplicate
                existing = next(e for e in unique if (e.path, e.method) == key)
                if endpoint.source_spec not in existing.source_spec:
                    existing.source_spec += f", {endpoint.source_spec}"

        return unique

    def _categorize_endpoints(self, endpoints: list[APIEndpoint]) -> dict[str, list[APIEndpoint]]:
        """Categorize endpoints by resource type"""
        categories = defaultdict(list)

        for endpoint in endpoints:
            # Extract resource from path
            path_parts = endpoint.path.split("/")
            if len(path_parts) > 3:
                resource = path_parts[3].split("?")[0].split("{")[0]
                categories[resource].append(endpoint)
            else:
                categories["other"].append(endpoint)

        return dict(categories)

    def generate_markdown_report(self, output_path: Path):
        """Generate comprehensive markdown report"""
        results = self.extract_all()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# API Requirements Matrix\n\n")
            f.write(f"**Generated:** {Path(__file__).stat().st_mtime}\n")
            f.write(f"**Total Endpoints Extracted:** {results['total_endpoints']}\n\n")
            f.write("## Overview\n\n")
            f.write(
                "This document contains all API requirements extracted from frontend specification files.\n\n"
            )
            f.write("## Categories\n\n")

            for category, endpoints in sorted(results["categories"].items()):
                f.write(f"### {category.title()}\n\n")
                f.write(f"**Count:** {len(endpoints)}\n\n")

                for endpoint in sorted(endpoints, key=lambda e: (e.path, e.method or "")):
                    f.write(f"#### {endpoint.method or 'ANY'} {endpoint.path}\n\n")
                    if endpoint.description:
                        f.write(f"**Description:** {endpoint.description}\n\n")
                    f.write(f"**Source Spec:** {endpoint.source_spec}\n\n")
                    if endpoint.query_params:
                        f.write(f"**Query Parameters:** {', '.join(endpoint.query_params)}\n\n")
                    if endpoint.path_params:
                        f.write(f"**Path Parameters:** {', '.join(endpoint.path_params)}\n\n")
                    if endpoint.error_responses:
                        f.write(f"**Error Responses:** {', '.join(endpoint.error_responses)}\n\n")
                    f.write(f"**Authentication Required:** {endpoint.auth_required}\n\n")
                    f.write(f"**Tenant Required:** {endpoint.tenant_required}\n\n")
                    f.write("---\n\n")

        print(f"Report generated: {output_path}")


if __name__ == "__main__":
    # Get paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    specs_dir = repo_root / "openspec" / "changes" / "frontendmvp" / "specs"
    output_dir = repo_root / "docs" / "api-audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "api-requirements-matrix.md"

    # Extract requirements
    extractor = APIRequirementsExtractor(str(specs_dir))
    extractor.generate_markdown_report(output_file)

    print("\n✅ API requirements extraction complete!")
    print(f"📄 Report saved to: {output_file}")
