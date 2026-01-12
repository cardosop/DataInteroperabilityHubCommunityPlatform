#!/usr/bin/env python3
"""
Check OpenAPI spec references against actual URL patterns

This script:
1. Parses OpenAPI specification files
2. Extracts all endpoint paths
3. Compares with actual URL patterns from endpoint audit
4. Identifies discrepancies
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import argparse
import urllib.parse


@dataclass
class OpenAPIPath:
    """Represents an OpenAPI path definition"""
    path: str
    methods: List[str]
    operation_ids: List[str]
    tags: List[str]
    summary: Optional[str] = None


@dataclass
class Discrepancy:
    """Represents a discrepancy between OpenAPI spec and actual URLs"""
    type: str  # 'missing_in_spec', 'missing_in_urls', 'path_mismatch', 'method_mismatch'
    openapi_path: Optional[str] = None
    actual_path: Optional[str] = None
    openapi_methods: Optional[List[str]] = None
    actual_methods: Optional[List[str]] = None
    details: Optional[str] = None


class OpenAPISpecParser:
    """Parser for OpenAPI specification files"""

    def __init__(self, spec_data: Dict[str, Any]):
        self.spec = spec_data
        self.paths: List[OpenAPIPath] = []
        self._parse_paths()

    def _parse_paths(self):
        """Parse paths from OpenAPI spec"""
        paths_section = self.spec.get('paths', {})

        for path_str, path_item in paths_section.items():
            methods = []
            operation_ids = []
            tags = []
            summary = None

            # OpenAPI methods
            http_methods = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']

            for method in http_methods:
                if method in path_item:
                    operation = path_item[method]
                    methods.append(method.upper())

                    # Extract operation ID
                    if 'operationId' in operation:
                        operation_ids.append(operation['operationId'])

                    # Extract tags
                    if 'tags' in operation:
                        tags.extend(operation['tags'])

                    # Extract summary
                    if not summary and 'summary' in operation:
                        summary = operation['summary']

            # If no methods found, might be a reference or parameter definition
            if not methods:
                continue

            self.paths.append(OpenAPIPath(
                path=path_str,
                methods=methods,
                operation_ids=operation_ids,
                tags=list(set(tags)) if tags else [],
                summary=summary
            ))

    def normalize_path(self, path: str) -> str:
        """Normalize OpenAPI path for comparison"""
        # Remove trailing slashes for comparison
        normalized = path.rstrip('/')
        # Normalize parameter formats
        # OpenAPI: /api/v1/users/{id}
        # Django: /api/v1/users/<id>/
        normalized = re.sub(r'\{([^}]+)\}', r'<{\1}>', normalized)
        return normalized

    def get_all_paths(self) -> List[OpenAPIPath]:
        """Get all parsed paths"""
        return self.paths


class URLPatternComparator:
    """Compares OpenAPI paths with actual URL patterns"""

    def __init__(self, openapi_paths: List[OpenAPIPath], actual_endpoints: List[Dict[str, Any]]):
        self.openapi_paths = openapi_paths
        self.actual_endpoints = actual_endpoints
        self.discrepancies: List[Discrepancy] = []

    def normalize_django_path(self, path: str) -> str:
        """Normalize Django URL pattern for comparison"""
        # Remove trailing slashes
        normalized = path.rstrip('/')
        # Normalize parameter formats
        # Django: /api/v1/users/<id>/
        # OpenAPI: /api/v1/users/{id}
        normalized = re.sub(r'<([^>]+)>', r'<{\1}>', normalized)
        # Remove regex patterns
        normalized = re.sub(r'\^|\$', '', normalized)
        return normalized

    def extract_base_path(self, full_path: str) -> str:
        """Extract base path (remove /api/v1 prefix if present)"""
        # Remove /api/v1 prefix for comparison
        if full_path.startswith('/api/v1/'):
            return full_path[7:]  # Remove '/api/v1/'
        elif full_path.startswith('/api/v1'):
            return full_path[7:]  # Remove '/api/v1'
        return full_path

    def paths_match(self, openapi_path: str, actual_path: str) -> bool:
        """Check if paths match (accounting for parameter differences)"""
        # Normalize both paths
        openapi_norm = self.normalize_django_path(openapi_path)
        actual_norm = self.normalize_django_path(actual_path)

        # Direct match
        if openapi_norm == actual_norm:
            return True

        # Try removing /api/v1 prefix
        openapi_base = self.extract_base_path(openapi_norm)
        actual_base = self.extract_base_path(actual_norm)

        if openapi_base == actual_base:
            return True

        # Try parameter normalization
        # Replace {param} with <param> and vice versa
        openapi_param = re.sub(r'\{([^}]+)\}', r'<{\1}>', openapi_base)
        actual_param = re.sub(r'<([^>]+)>', r'<{\1}>', actual_base)

        if openapi_param == actual_param:
            return True

        # Try more flexible matching (ignore parameter names)
        openapi_pattern = re.sub(r'\{[^}]+\}', r'<{param}>', openapi_base)
        actual_pattern = re.sub(r'<[^>]+>', r'<{param}>', actual_base)

        return openapi_pattern == actual_pattern

    def compare(self) -> List[Discrepancy]:
        """Compare OpenAPI paths with actual endpoints"""
        discrepancies = []

        # Build maps for comparison
        openapi_path_map = {}
        for path_obj in self.openapi_paths:
            normalized = self.normalize_django_path(path_obj.path)
            if normalized not in openapi_path_map:
                openapi_path_map[normalized] = []
            openapi_path_map[normalized].append(path_obj)

        actual_path_map = defaultdict(list)
        for endpoint in self.actual_endpoints:
            full_path = endpoint.get('full_path', endpoint.get('pattern', ''))
            normalized = self.normalize_django_path(full_path)
            actual_path_map[normalized].append(endpoint)

        # Find paths in OpenAPI but not in actual URLs
        for openapi_path, path_objs in openapi_path_map.items():
            found = False
            for actual_path, endpoints in actual_path_map.items():
                if self.paths_match(openapi_path, actual_path):
                    found = True
                    # Check methods
                    openapi_methods = set()
                    for path_obj in path_objs:
                        openapi_methods.update(path_obj.methods)

                    actual_methods = set()
                    for endpoint in endpoints:
                        actual_methods.update(endpoint.get('methods', ['GET']))

                    if openapi_methods != actual_methods:
                        discrepancies.append(Discrepancy(
                            type='method_mismatch',
                            openapi_path=openapi_path,
                            actual_path=actual_path,
                            openapi_methods=list(openapi_methods),
                            actual_methods=list(actual_methods),
                            details=f"Methods differ: OpenAPI has {openapi_methods}, actual has {actual_methods}"
                        ))
                    break

            if not found:
                discrepancies.append(Discrepancy(
                    type='missing_in_urls',
                    openapi_path=openapi_path,
                    details=f"Path in OpenAPI spec but not found in actual URL patterns"
                ))

        # Find paths in actual URLs but not in OpenAPI
        for actual_path, endpoints in actual_path_map.items():
            found = False
            for openapi_path in openapi_path_map.keys():
                if self.paths_match(openapi_path, actual_path):
                    found = True
                    break

            if not found:
                # Skip common patterns that might not be in OpenAPI
                if any(skip in actual_path for skip in ['openapi.json', 'openapi.yaml', 'swagger', 'redoc']):
                    continue

                discrepancies.append(Discrepancy(
                    type='missing_in_spec',
                    actual_path=actual_path,
                    actual_methods=list(set(m for e in endpoints for m in e.get('methods', ['GET']))),
                    details=f"Path in actual URLs but not found in OpenAPI spec"
                ))

        return discrepancies


class OpenAPISpecChecker:
    """Main checker class"""

    def __init__(self, spec_file: Optional[str] = None, spec_data: Optional[Dict[str, Any]] = None):
        if spec_data:
            self.spec_data = spec_data
        elif spec_file:
            self.spec_data = self._load_spec_file(spec_file)
        else:
            raise ValueError("Either spec_file or spec_data must be provided")

        self.parser = OpenAPISpecParser(self.spec_data)

    def _load_spec_file(self, spec_file: str) -> Dict[str, Any]:
        """Load OpenAPI spec from file"""
        spec_path = Path(spec_file)

        if not spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec file not found: {spec_file}")

        with open(spec_path, 'r') as f:
            if spec_path.suffix in ['.yaml', '.yml']:
                import yaml
                return yaml.safe_load(f)
            else:
                return json.load(f)

    @staticmethod
    def fetch_from_api(base_url: str = 'http://localhost:8000') -> Dict[str, Any]:
        """Fetch OpenAPI spec from API endpoint"""
        import urllib.request

        urls = [
            f"{base_url}/api/v1/openapi.json",
            f"{base_url}/api/v1/openapi.yaml",
            f"{base_url}/api-docs/openapi.json",
        ]

        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    content_type = response.headers.get('Content-Type', '')
                    content = response.read().decode('utf-8')

                    if 'yaml' in content_type or url.endswith('.yaml'):
                        import yaml
                        return yaml.safe_load(content)
                    else:
                        return json.loads(content)
            except Exception as e:
                continue

        raise RuntimeError(f"Could not fetch OpenAPI spec from any of: {urls}")

    def compare_with_audit_results(self, audit_file: str) -> Dict[str, Any]:
        """Compare OpenAPI spec with endpoint audit results"""
        # Load audit results
        with open(audit_file, 'r') as f:
            audit_data = json.load(f)

        # Extract endpoints from audit
        endpoints = audit_data.get('inventory', {}).get('endpoints', [])

        # Compare
        comparator = URLPatternComparator(self.parser.get_all_paths(), endpoints)
        discrepancies = comparator.compare()

        return {
            'openapi_paths': len(self.parser.get_all_paths()),
            'actual_endpoints': len(endpoints),
            'discrepancies': [asdict(d) for d in discrepancies],
            'discrepancy_count': len(discrepancies),
            'summary': self._generate_summary(discrepancies),
        }

    def _generate_summary(self, discrepancies: List[Discrepancy]) -> Dict[str, Any]:
        """Generate summary statistics"""
        by_type = defaultdict(int)
        for disc in discrepancies:
            by_type[disc.type] += 1

        return {
            'total_discrepancies': len(discrepancies),
            'by_type': dict(by_type),
        }

    def output_json(self, comparison_result: Dict[str, Any]) -> str:
        """Output comparison result as JSON"""
        return json.dumps(comparison_result, indent=2, default=str)

    def output_markdown(self, comparison_result: Dict[str, Any]) -> str:
        """Output comparison result as Markdown"""
        lines = ['# OpenAPI Spec Reference Check\n']

        lines.append('## Summary\n')
        lines.append(f"- OpenAPI Paths: {comparison_result['openapi_paths']}")
        lines.append(f"- Actual Endpoints: {comparison_result['actual_endpoints']}")
        lines.append(f"- Discrepancies: {comparison_result['discrepancy_count']}\n")

        summary = comparison_result['summary']
        lines.append('### Discrepancy Breakdown\n')
        for disc_type, count in summary['by_type'].items():
            lines.append(f"- **{disc_type}**: {count}")
        lines.append('')

        if comparison_result['discrepancies']:
            lines.append('## Discrepancies\n')

            # Group by type
            by_type = defaultdict(list)
            for disc in comparison_result['discrepancies']:
                by_type[disc['type']].append(disc)

            for disc_type, discs in sorted(by_type.items()):
                lines.append(f"### {disc_type.replace('_', ' ').title()}\n")
                for disc in discs[:50]:  # Limit to first 50 per type
                    lines.append(f"- **OpenAPI**: {disc.get('openapi_path', 'N/A')}")
                    if disc.get('actual_path'):
                        lines.append(f"  - **Actual**: {disc['actual_path']}")
                    if disc.get('openapi_methods'):
                        lines.append(f"  - **OpenAPI Methods**: {', '.join(disc['openapi_methods'])}")
                    if disc.get('actual_methods'):
                        lines.append(f"  - **Actual Methods**: {', '.join(disc['actual_methods'])}")
                    if disc.get('details'):
                        lines.append(f"  - **Details**: {disc['details']}")
                    lines.append('')
                if len(discs) > 50:
                    lines.append(f"- ... and {len(discs) - 50} more discrepancies\n")

        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Check OpenAPI spec references against actual URL patterns')
    parser.add_argument('--spec-file', help='Path to OpenAPI spec file (JSON or YAML)')
    parser.add_argument('--spec-url', help='URL to fetch OpenAPI spec from')
    parser.add_argument('--audit-file', required=True, help='Path to endpoint audit JSON file')
    parser.add_argument('--output-format', choices=['json', 'markdown'], default='json',
                       help='Output format')
    parser.add_argument('--output-file', help='Output file path')

    args = parser.parse_args()

    # Load or fetch OpenAPI spec
    if args.spec_file:
        checker = OpenAPISpecChecker(spec_file=args.spec_file)
    elif args.spec_url:
        # Fetch directly from the provided URL
        import urllib.request
        try:
            with urllib.request.urlopen(args.spec_url, timeout=10) as response:
                content = response.read().decode('utf-8')
                if 'yaml' in response.headers.get('Content-Type', '') or args.spec_url.endswith(('.yaml', '.yml')):
                    import yaml
                    spec_data = yaml.safe_load(content)
                else:
                    spec_data = json.loads(content)
            checker = OpenAPISpecChecker(spec_data=spec_data)
        except Exception as e:
            print(f"Error fetching OpenAPI spec from {args.spec_url}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Try to fetch from default API endpoint
        try:
            spec_data = OpenAPISpecChecker.fetch_from_api()
            checker = OpenAPISpecChecker(spec_data=spec_data)
        except Exception as e:
            print(f"Error: Could not load OpenAPI spec. Use --spec-file or --spec-url. {e}", file=sys.stderr)
            sys.exit(1)

    # Compare with audit results
    try:
        result = checker.compare_with_audit_results(args.audit_file)
    except Exception as e:
        print(f"Error comparing specs: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Output results
    if args.output_format == 'json':
        output = checker.output_json(result)
    else:
        output = checker.output_markdown(result)

    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"Results written to {args.output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()

