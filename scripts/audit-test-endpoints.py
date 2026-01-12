#!/usr/bin/env python3
"""
Test Endpoint Audit Script

Comprehensive audit tool for analyzing test files that reference API endpoints.
Searches through unit tests, integration tests, E2E tests, and regression tests
to identify which tests reference which endpoints.

Usage:
    python audit-test-endpoints.py [options]

Options:
    --inventory-file PATH    Path to endpoint inventory JSON (default: docs/api-audit/endpoint-inventory-current.json)
    --output-format          Output format: json, markdown (default: json)
    --output-file PATH       Output file path (default: docs/api-audit/test-impact-analysis.json)
    --project-root PATH       Project root directory (default: auto-detect)
    --verbose                Verbose output
    --help                   Show this help message
"""
import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class TestEndpointMapping:
    """Represents a mapping between a test file and an endpoint"""
    test_file: str
    test_type: str  # 'unit', 'integration', 'e2e', 'regression', 'other'
    endpoint_path: str
    endpoint_name: str
    service: str
    method: str
    line_number: int
    context: str
    is_dynamic: bool  # True if endpoint uses f-strings or variables


class TestEndpointAuditor:
    """Audit test files for endpoint URL references"""

    # Test directory patterns
    TEST_DIR_PATTERNS = {
        'unit': [
            'tests/unit',
            '**/tests/unit',
            '**/test_*.py',
        ],
        'integration': [
            'tests/integration',
            '**/tests/integration',
            '**/test_*_integration.py',
            '**/test_*integration*.py',
        ],
        'e2e': [
            'tests/e2e',
            '**/tests/e2e',
            '**/test_*_e2e.py',
            '**/test_*e2e*.py',
        ],
        'regression': [
            'tests/regression',
            '**/tests/regression',
            '**/test_*_regression.py',
            '**/test_*regression*.py',
        ],
    }

    # Patterns to match endpoint URLs in test files
    ENDPOINT_PATTERNS = [
        # Direct path strings: '/api/v1/...'
        r'["\'](/api/v1/[^"\']+)["\']',
        # f-strings: f'/api/v1/...'
        r'f["\'](/api/v1/[^"\']+)["\']',
        # Full URLs: 'http://.../api/v1/...'
        r'["\'](https?://[^"\']*?/api/v1/[^"\']+)["\']',
        # Client method calls: client.get('/api/v1/...')
        r'\.(get|post|put|patch|delete|head|options)\(["\'](/api/v1/[^"\']+)["\']',
        # Reverse URL patterns: reverse('endpoint-name')
        r'reverse\(["\']([^"\']+)["\']',
    ]

    def __init__(
        self,
        inventory_file: str,
        project_root: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Initialize the test endpoint auditor.

        Args:
            inventory_file: Path to endpoint inventory JSON file
            project_root: Project root directory (default: auto-detect)
            verbose: Enable verbose output
        """
        self.inventory_file = Path(inventory_file)
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            # Auto-detect project root
            self.project_root = self._find_project_root()
        self.verbose = verbose
        self.endpoints: List[Dict[str, Any]] = []
        self.test_mappings: List[TestEndpointMapping] = []
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ENDPOINT_PATTERNS]

    def _find_project_root(self) -> Path:
        """Find project root directory"""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            # Look for common project root indicators
            if (current / 'manage.py').exists() or \
               (current / 'pyproject.toml').exists() or \
               (current / 'setup.py').exists() or \
               (current / '.git').exists():
                return current
            current = current.parent
        # Fallback to current directory
        return Path.cwd()

    def load_endpoints(self) -> List[Dict[str, Any]]:
        """Load endpoints from inventory file"""
        if not self.inventory_file.exists():
            raise FileNotFoundError(f"Inventory file not found: {self.inventory_file}")

        with open(self.inventory_file, 'r') as f:
            data = json.load(f)

        # Handle different inventory file structures
        if 'inventory' in data:
            endpoints = data['inventory'].get('endpoints', [])
        elif 'endpoints' in data:
            endpoints = data['endpoints']
        else:
            endpoints = []

        self.endpoints = endpoints
        if self.verbose:
            print(f"Loaded {len(endpoints)} endpoints from inventory")
        return endpoints

    def _find_test_files(self, test_type: str) -> List[Path]:
        """
        Find test files of a specific type.

        Args:
            test_type: Type of tests to find ('unit', 'integration', 'e2e', 'regression')

        Returns:
            List of test file paths
        """
        patterns = self.TEST_DIR_PATTERNS.get(test_type, [])
        test_files = []
        seen_files = set()

        for pattern in patterns:
            if '**' in pattern:
                # Glob pattern - only match test files
                for path in self.project_root.glob(pattern):
                    if path.is_file() and path.suffix == '.py' and \
                       (path.name.startswith('test_') or path.name.endswith('_test.py')):
                        if path not in seen_files:
                            test_files.append(path)
                            seen_files.add(path)
            else:
                # Directory pattern - only search in specific test directories
                test_dir = self.project_root / pattern
                if test_dir.exists() and test_dir.is_dir():
                    # Only search in the specific directory, not recursively through all subdirs
                    # unless it's explicitly a test directory
                    for path in test_dir.rglob('test_*.py'):
                        if path.is_file() and path not in seen_files:
                            test_files.append(path)
                            seen_files.add(path)
                    for path in test_dir.rglob('*_test.py'):
                        if path.is_file() and path not in seen_files:
                            test_files.append(path)
                            seen_files.add(path)

        # Also search in hub/apps/*/tests/ for app-specific tests
        if test_type == 'unit':
            apps_tests_dir = self.project_root / 'hub' / 'apps'
            if apps_tests_dir.exists():
                for app_dir in apps_tests_dir.iterdir():
                    if app_dir.is_dir():
                        tests_dir = app_dir / 'tests'
                        if tests_dir.exists() and tests_dir.is_dir():
                            for path in tests_dir.rglob('test_*.py'):
                                if path.is_file() and path not in seen_files:
                                    test_files.append(path)
                                    seen_files.add(path)
                            for path in tests_dir.rglob('*_test.py'):
                                if path.is_file() and path not in seen_files:
                                    test_files.append(path)
                                    seen_files.add(path)

        # Remove duplicates and sort
        test_files = sorted(set(test_files))
        return test_files

    def _extract_endpoint_references(
        self,
        content: str,
        endpoints: List[Dict[str, Any]],
        file_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Extract endpoint references from file content.

        Args:
            content: File content to search
            endpoints: List of endpoint definitions
            file_path: Path to the file being searched

        Returns:
            List of endpoint references found
        """
        references = []
        lines = content.split('\n')

        # Build endpoint lookup maps
        endpoint_paths = {ep['full_path']: ep for ep in endpoints}
        endpoint_names = {ep.get('name', ''): ep for ep in endpoints if ep.get('name')}

        # Also create pattern-based matches for dynamic endpoints
        endpoint_patterns = {}
        for ep in endpoints:
            path = ep['full_path']
            # Convert path parameters to regex pattern
            pattern_path = re.escape(path).replace(r'\{id\}', r'[^/]+').replace(r'\{pk\}', r'[^/]+')
            pattern_path = pattern_path.replace(r'\{', r'\{').replace(r'\}', r'\}')
            # Handle common path parameter patterns
            pattern_path = re.sub(r'\\\{[^}]+\}', r'[^/]+', pattern_path)
            endpoint_patterns[pattern_path] = ep

        for line_num, line in enumerate(lines, start=1):
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Search for endpoint patterns
            for pattern in self.compiled_patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group(0)
                    endpoint_path = None
                    is_dynamic = False

                    # Extract endpoint path from match
                    if '/api/v1/' in matched_text:
                        # Extract the path from quotes
                        path_match = re.search(r'/api/v1/[^"\']+', matched_text)
                        if path_match:
                            endpoint_path = path_match.group(0)
                            # Check if it's an f-string (dynamic)
                            if 'f"' in matched_text or "f'" in matched_text:
                                is_dynamic = True
                    elif 'reverse(' in matched_text:
                        # Extract endpoint name from reverse() call
                        name_match = re.search(r'reverse\(["\']([^"\']+)["\']', matched_text)
                        if name_match:
                            endpoint_name = name_match.group(1)
                            if endpoint_name in endpoint_names:
                                endpoint_path = endpoint_names[endpoint_name]['full_path']

                    if endpoint_path:
                        # Try exact match first
                        endpoint = endpoint_paths.get(endpoint_path)
                        if not endpoint:
                            # Try pattern matching for dynamic endpoints
                            for pattern_path, ep in endpoint_patterns.items():
                                if re.match(pattern_path + r'/?$', endpoint_path):
                                    endpoint = ep
                                    break

                        if endpoint:
                            # Extract HTTP method if available
                            method = 'GET'  # default
                            method_match = re.search(r'\.(get|post|put|patch|delete|head|options)\(', line.lower())
                            if method_match:
                                method = method_match.group(1).upper()

                            references.append({
                                'endpoint_path': endpoint_path,
                                'endpoint_name': endpoint.get('name', ''),
                                'service': endpoint.get('service', ''),
                                'method': method,
                                'line_number': line_num,
                                'context': line.strip(),
                                'is_dynamic': is_dynamic
                            })

        return references

    def _detect_test_type(self, test_file: Path) -> str:
        """
        Detect test type from file path.

        Args:
            test_file: Path to test file

        Returns:
            Test type ('unit', 'integration', 'e2e', 'regression', 'other')
        """
        file_str = str(test_file).lower()

        # Check for explicit test type in path
        if '/e2e/' in file_str or 'test_e2e' in file_str or '_e2e_test' in file_str:
            return 'e2e'
        elif '/integration/' in file_str or 'test_integration' in file_str or '_integration_test' in file_str:
            return 'integration'
        elif '/regression/' in file_str or 'test_regression' in file_str or '_regression_test' in file_str:
            return 'regression'
        elif '/unit/' in file_str:
            return 'unit'
        else:
            # Default to unit for app-specific tests
            return 'unit'

    def _map_tests_to_endpoints(
        self,
        test_files: List[Path],
        endpoints: List[Dict[str, Any]],
        test_type: str
    ) -> List[TestEndpointMapping]:
        """
        Map test files to endpoints they reference.

        Args:
            test_files: List of test file paths
            endpoints: List of endpoint definitions
            test_type: Type of tests ('unit', 'integration', 'e2e', 'regression')

        Returns:
            List of test-endpoint mappings
        """
        mappings = []

        for test_file in test_files:
            try:
                content = test_file.read_text(encoding='utf-8')
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Could not read {test_file}: {e}")
                continue

            # Detect actual test type from file path
            actual_test_type = self._detect_test_type(test_file)
            # Use detected type if it's more specific than the search type
            if actual_test_type != 'unit' or test_type == 'unit':
                final_test_type = actual_test_type
            else:
                final_test_type = test_type

            references = self._extract_endpoint_references(content, endpoints, test_file)

            for ref in references:
                mapping = TestEndpointMapping(
                    test_file=str(test_file.relative_to(self.project_root)),
                    test_type=final_test_type,
                    endpoint_path=ref['endpoint_path'],
                    endpoint_name=ref['endpoint_name'],
                    service=ref['service'],
                    method=ref['method'],
                    line_number=ref['line_number'],
                    context=ref['context'],
                    is_dynamic=ref['is_dynamic']
                )
                mappings.append(mapping)

        return mappings

    def audit(self) -> Dict[str, Any]:
        """
        Perform comprehensive audit of test files.

        Returns:
            Dictionary with audit results
        """
        if not self.endpoints:
            self.load_endpoints()

        all_mappings = []

        # Audit each test type
        for test_type in ['unit', 'integration', 'e2e', 'regression']:
            if self.verbose:
                print(f"Searching {test_type} tests...")
            test_files = self._find_test_files(test_type)
            if self.verbose:
                print(f"  Found {len(test_files)} {test_type} test files")

            mappings = self._map_tests_to_endpoints(test_files, self.endpoints, test_type)
            all_mappings.extend(mappings)
            if self.verbose:
                print(f"  Found {len(mappings)} endpoint references in {test_type} tests")

        self.test_mappings = all_mappings

        # Generate summary statistics
        summary = self._generate_summary(all_mappings)

        return {
            'summary': summary,
            'test_mappings': [asdict(m) for m in all_mappings]
        }

    def _generate_summary(self, mappings: List[TestEndpointMapping]) -> Dict[str, Any]:
        """Generate summary statistics"""
        # Count unique test files
        test_files = set(m.test_file for m in mappings)

        # Count unique endpoints
        endpoints = set(m.endpoint_path for m in mappings)

        # Count by test type
        by_test_type = defaultdict(int)
        for m in mappings:
            by_test_type[m.test_type] += 1

        # Count by service
        by_service = defaultdict(int)
        for m in mappings:
            by_service[m.service] += 1

        # Count by HTTP method
        by_method = defaultdict(int)
        for m in mappings:
            by_method[m.method] += 1

        # Count dynamic vs static references
        dynamic_count = sum(1 for m in mappings if m.is_dynamic)
        static_count = len(mappings) - dynamic_count

        return {
            'total_test_files': len(test_files),
            'total_endpoints_referenced': len(endpoints),
            'total_references': len(mappings),
            'by_test_type': dict(by_test_type),
            'by_service': dict(by_service),
            'by_method': dict(by_method),
            'dynamic_references': dynamic_count,
            'static_references': static_count
        }

    def _generate_json_report(self, output_file: Path):
        """Generate JSON report"""
        result = {
            'summary': self._generate_summary(self.test_mappings),
            'test_mappings': [asdict(m) for m in self.test_mappings]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        if self.verbose:
            print(f"JSON report written to {output_file}")

    def _generate_markdown_report(self, output_file: Path):
        """Generate Markdown report"""
        summary = self._generate_summary(self.test_mappings)

        lines = [
            '# Test Endpoint Impact Analysis',
            '',
            '## Summary',
            '',
            f'- **Total Test Files**: {summary["total_test_files"]}',
            f'- **Total Endpoints Referenced**: {summary["total_endpoints_referenced"]}',
            f'- **Total References**: {summary["total_references"]}',
            '',
            '### By Test Type',
            '',
        ]

        for test_type, count in sorted(summary['by_test_type'].items()):
            lines.append(f'- **{test_type}**: {count}')

        lines.extend([
            '',
            '### By Service',
            '',
        ])

        for service, count in sorted(summary['by_service'].items()):
            lines.append(f'- **{service}**: {count}')

        lines.extend([
            '',
            '### By HTTP Method',
            '',
        ])

        for method, count in sorted(summary['by_method'].items()):
            lines.append(f'- **{method}**: {count}')

        lines.extend([
            '',
            '## Test Mappings',
            '',
            '| Test File | Test Type | Endpoint | Service | Method | Line |',
            '|-----------|-----------|----------|---------|--------|------|',
        ])

        # Group by test file for better readability
        by_test_file = defaultdict(list)
        for m in self.test_mappings:
            by_test_file[m.test_file].append(m)

        for test_file in sorted(by_test_file.keys()):
            for mapping in by_test_file[test_file]:
                lines.append(
                    f'| {mapping.test_file} | {mapping.test_type} | '
                    f'{mapping.endpoint_path} | {mapping.service} | '
                    f'{mapping.method} | {mapping.line_number} |'
                )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))

        if self.verbose:
            print(f"Markdown report written to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Audit test files for endpoint URL references',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--inventory-file',
        type=str,
        default='docs/api-audit/endpoint-inventory-current.json',
        help='Path to endpoint inventory JSON file'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'markdown'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        default='docs/api-audit/test-impact-analysis.json',
        help='Output file path'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        help='Project root directory (default: auto-detect)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Initialize auditor
    auditor = TestEndpointAuditor(
        inventory_file=args.inventory_file,
        project_root=args.project_root,
        verbose=args.verbose
    )

    # Perform audit
    print("Loading endpoints from inventory...")
    auditor.load_endpoints()

    print("Auditing test files...")
    result = auditor.audit()

    # Generate report
    output_file = Path(args.output_file)
    if args.output_format == 'json':
        auditor._generate_json_report(output_file)
    else:
        markdown_file = output_file.with_suffix('.md')
        auditor._generate_markdown_report(markdown_file)

    # Print summary
    summary = result['summary']
    print("\n" + "="*60)
    print("Audit Summary")
    print("="*60)
    print(f"Total Test Files: {summary['total_test_files']}")
    print(f"Total Endpoints Referenced: {summary['total_endpoints_referenced']}")
    print(f"Total References: {summary['total_references']}")
    print("\nBy Test Type:")
    for test_type, count in sorted(summary['by_test_type'].items()):
        print(f"  {test_type}: {count}")
    print("\nBy Service:")
    for service, count in sorted(summary['by_service'].items()):
        print(f"  {service}: {count}")
    print("="*60)


if __name__ == '__main__':
    main()

