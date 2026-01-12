#!/usr/bin/env python3
"""
Comprehensive API Client Usage Search Script

Searches for all API client usage patterns in the codebase and maps them to endpoints.
This script implements task 9.6.1.2.3 from the ODPS integration tasks.
"""

import os
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class APICall:
    """Represents an API call found in the codebase"""
    file_path: str
    line_number: int
    method: str  # HTTP method (GET, POST, etc.)
    endpoint: str  # Endpoint path
    client_type: str  # Type of client (DataHubClient, APIClient, requests, httpx, axios, fetch)
    context: str  # Code context around the call
    is_direct: bool  # True if direct HTTP call, False if through client wrapper


@dataclass
class ClientUsage:
    """Represents client class usage"""
    file_path: str
    line_number: int
    client_class: str
    method_name: str
    endpoint: Optional[str]
    context: str


class APIClientUsageSearcher:
    """Searches for API client usage patterns in the codebase"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.api_calls: List[APICall] = []
        self.client_usages: List[ClientUsage] = []
        self.endpoint_mappings: Dict[str, List[APICall]] = defaultdict(list)

        # Patterns to search for
        self.client_class_patterns = [
            r'class\s+(\w*Client)\s*[:\(]',
            r'class\s+(\w*API)\s*[:\(]',
            r'class\s+(APIClient)\s*[:\(]',
        ]

        # HTTP method patterns
        self.http_method_patterns = [
            r'\.(get|post|put|patch|delete|request)\s*\(',
            r'\.(GET|POST|PUT|PATCH|DELETE|REQUEST)\s*\(',
        ]

        # Endpoint patterns
        self.endpoint_patterns = [
            r'["\'](/api/v1/[^"\']+)["\']',
            r'["\']([^"\']*api[^"\']*)["\']',
            r'url\s*[:=]\s*["\']([^"\']+)["\']',
            r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',
        ]

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped"""
        skip_patterns = [
            '__pycache__',
            '.pyc',
            '.pyo',
            '.pyd',
            'node_modules',
            '.git',
            'venv',
            'htmlcov',
            'coverage.xml',
            '.egg-info',
            'migrations',
            'backups',
            'deployment_logs',
        ]
        path_str = str(file_path)
        return any(pattern in path_str for pattern in skip_patterns)

    def search_client_classes(self) -> Set[str]:
        """Search for API client class definitions"""
        client_classes = set()

        for py_file in self.root_dir.rglob('*.py'):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                for pattern in self.client_class_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        client_classes.add(match.group(1))
            except Exception as e:
                print(f"Error reading {py_file}: {e}")

        return client_classes

    def extract_endpoint_from_line(self, line: str, context_lines: List[str]) -> Optional[str]:
        """Extract endpoint from a line of code"""
        # Try direct endpoint patterns
        for pattern in self.endpoint_patterns:
            match = re.search(pattern, line)
            if match:
                endpoint = match.group(1)
                # Filter out non-endpoint strings
                if '/api/' in endpoint or endpoint.startswith('/'):
                    return endpoint

        # Try to find endpoint in context (next few lines)
        for ctx_line in context_lines[:5]:
            for pattern in self.endpoint_patterns:
                match = re.search(pattern, ctx_line)
                if match:
                    endpoint = match.group(1)
                    if '/api/' in endpoint or endpoint.startswith('/'):
                        return endpoint

        return None

    def search_python_api_calls(self):
        """Search for API calls in Python files"""
        print("Searching Python files for API calls...")

        for py_file in self.root_dir.rglob('*.py'):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Search for requests library calls
                    if re.search(r'requests\.(get|post|put|patch|delete|request)', line):
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            self.api_calls.append(APICall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=self._extract_method_from_line(line),
                                endpoint=endpoint,
                                client_type='requests',
                                context=self._get_context(lines, i),
                                is_direct=True
                            ))

                    # Search for httpx calls
                    if re.search(r'httpx\.(get|post|put|patch|delete|request)', line):
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            self.api_calls.append(APICall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=self._extract_method_from_line(line),
                                endpoint=endpoint,
                                client_type='httpx',
                                context=self._get_context(lines, i),
                                is_direct=True
                            ))

                    # Search for client method calls (e.g., client.get(), api_client.post())
                    client_method_match = re.search(r'(\w+)\.(get|post|put|patch|delete|request)\s*\(', line)
                    if client_method_match:
                        client_var = client_method_match.group(1)
                        method = client_method_match.group(2).upper()

                        # Check if this looks like an API client call
                        if client_var in ['client', 'api_client', 'http_client', 'sdk_client'] or \
                           client_var.endswith('Client') or client_var.endswith('API'):
                            endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                            if endpoint:
                                self.api_calls.append(APICall(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    method=method,
                                    endpoint=endpoint,
                                    client_type=f'{client_var}',
                                    context=self._get_context(lines, i),
                                    is_direct=False
                                ))

                    # Search for async client calls
                    async_match = re.search(r'await\s+(\w+)\.(get|post|put|patch|delete|request)\s*\(', line)
                    if async_match:
                        client_var = async_match.group(1)
                        method = async_match.group(2).upper()
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            self.api_calls.append(APICall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=method,
                                endpoint=endpoint,
                                client_type=f'{client_var}',
                                context=self._get_context(lines, i),
                                is_direct=False
                            ))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def search_typescript_api_calls(self):
        """Search for API calls in TypeScript/JavaScript files"""
        print("Searching TypeScript/JavaScript files for API calls...")

        for ts_file in self.root_dir.rglob('*.ts'):
            if self.should_skip_file(ts_file):
                continue

            try:
                content = ts_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Search for axios calls
                    if re.search(r'axios\.(get|post|put|patch|delete|request)', line):
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            self.api_calls.append(APICall(
                                file_path=str(ts_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=self._extract_method_from_line(line),
                                endpoint=endpoint,
                                client_type='axios',
                                context=self._get_context(lines, i),
                                is_direct=True
                            ))

                    # Search for fetch calls
                    if re.search(r'fetch\s*\(', line):
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            # Try to extract method from fetch options
                            method = 'GET'
                            if i < len(lines) - 1:
                                next_line = lines[i]
                                if 'method' in next_line.lower():
                                    method_match = re.search(r'method\s*[:=]\s*["\'](\w+)["\']', next_line)
                                    if method_match:
                                        method = method_match.group(1).upper()

                            self.api_calls.append(APICall(
                                file_path=str(ts_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=method,
                                endpoint=endpoint,
                                client_type='fetch',
                                context=self._get_context(lines, i),
                                is_direct=True
                            ))

                    # Search for client method calls
                    client_method_match = re.search(r'(\w+)\.(get|post|put|patch|delete|request)\s*\(', line)
                    if client_method_match:
                        client_var = client_method_match.group(1)
                        method = client_method_match.group(2).upper()
                        endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                        if endpoint:
                            self.api_calls.append(APICall(
                                file_path=str(ts_file.relative_to(self.root_dir)),
                                line_number=i,
                                method=method,
                                endpoint=endpoint,
                                client_type=f'{client_var}',
                                context=self._get_context(lines, i),
                                is_direct=False
                            ))

            except Exception as e:
                print(f"Error processing {ts_file}: {e}")

    def analyze_sdk_modules(self):
        """Analyze SDK modules to map methods to endpoints"""
        print("Analyzing SDK modules for endpoint mappings...")

        sdk_python_dir = self.root_dir / 'sdk' / 'python' / 'datahub_interoperability'
        if not sdk_python_dir.exists():
            return

        for api_file in sdk_python_dir.glob('*.py'):
            if api_file.name == '__init__.py' or api_file.name == 'client.py':
                continue

            try:
                content = api_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                # Find class definition
                class_name = None
                for i, line in enumerate(lines):
                    class_match = re.search(r'class\s+(\w+API)', line)
                    if class_match:
                        class_name = class_match.group(1)
                        break

                if not class_name:
                    continue

                # Find all methods that make API calls
                current_method = None
                method_start_line = 0

                for i, line in enumerate(lines, 1):
                    # Look for async def methods
                    method_match = re.search(r'async\s+def\s+(\w+)\s*\(', line)
                    if method_match:
                        # Save previous method if it had endpoint
                        if current_method:
                            method_body = '\n'.join(lines[method_start_line:i])
                            endpoint = self._extract_endpoint_from_method(method_body)
                            if endpoint:
                                self.client_usages.append(ClientUsage(
                                    file_path=str(api_file.relative_to(self.root_dir)),
                                    line_number=method_start_line,
                                    client_class=class_name,
                                    method_name=current_method,
                                    endpoint=endpoint,
                                    context=self._get_context(lines, method_start_line, context_lines=10)
                                ))

                        current_method = method_match.group(1)
                        method_start_line = i

                    # Look for client method calls within current method
                    if current_method and re.search(r'await\s+self\.client\.(get|post|put|patch|delete)\s*\(', line):
                        # Extract endpoint from this line or next few lines
                        endpoint = self._extract_endpoint_from_client_call(line, lines[i:min(i+5, len(lines))])
                        if endpoint:
                            self.client_usages.append(ClientUsage(
                                file_path=str(api_file.relative_to(self.root_dir)),
                                line_number=i,
                                client_class=class_name,
                                method_name=current_method,
                                endpoint=endpoint,
                                context=self._get_context(lines, i, context_lines=5)
                            ))

                # Handle last method
                if current_method:
                    method_body = '\n'.join(lines[method_start_line:])
                    endpoint = self._extract_endpoint_from_method(method_body)
                    if endpoint:
                        self.client_usages.append(ClientUsage(
                            file_path=str(api_file.relative_to(self.root_dir)),
                            line_number=method_start_line,
                            client_class=class_name,
                            method_name=current_method,
                            endpoint=endpoint,
                            context=self._get_context(lines, method_start_line, context_lines=10)
                        ))

            except Exception as e:
                print(f"Error analyzing {api_file}: {e}")

    def _extract_endpoint_from_method(self, method_body: str) -> Optional[str]:
        """Extract endpoint from method body"""
        # Look for common patterns
        patterns = [
            r'["\'](/api/v1/[^"\']+)["\']',
            r'["\']([^"\']*api[^"\']*)["\']',
            r'url\s*=\s*["\']([^"\']+)["\']',
            r'endpoint\s*=\s*["\']([^"\']+)["\']',
            r'f?["\']([^"\']*api[^"\']*)["\']',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, method_body)
            for match in matches:
                endpoint = match.group(1)
                if '/api/' in endpoint or endpoint.startswith('/'):
                    return endpoint

        return None

    def _extract_endpoint_from_client_call(self, line: str, next_lines: List[str]) -> Optional[str]:
        """Extract endpoint from client call line (e.g., await self.client.get("endpoint"))"""
        # Pattern: await self.client.get("endpoint")
        patterns = [
            r'await\s+self\.client\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
            r'await\s+self\.client\.(get|post|put|patch|delete)\s*\(\s*f["\']([^"\']+)["\']',
            r'self\.client\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                endpoint = match.group(2)
                # SDK endpoints are relative (e.g., "contracts/"), not full paths
                if endpoint and not endpoint.startswith('http'):
                    return endpoint

        # Check next lines for endpoint
        for next_line in next_lines[:3]:
            for pattern in patterns:
                match = re.search(pattern, next_line)
                if match:
                    endpoint = match.group(2)
                    if endpoint and not endpoint.startswith('http'):
                        return endpoint

        return None

    def _extract_method_from_line(self, line: str) -> str:
        """Extract HTTP method from line"""
        method_match = re.search(r'\.(get|post|put|patch|delete|request)', line, re.IGNORECASE)
        if method_match:
            return method_match.group(1).upper()
        return 'UNKNOWN'

    def _get_context(self, lines: List[str], line_num: int, context_lines: int = 3) -> str:
        """Get context around a line"""
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context = lines[start:end]
        return '\n'.join(context)

    def map_endpoints(self):
        """Map all API calls to endpoints"""
        print("Mapping API calls to endpoints...")

        for api_call in self.api_calls:
            self.endpoint_mappings[api_call.endpoint].append(api_call)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_api_calls': len(self.api_calls),
                'total_endpoints': len(self.endpoint_mappings),
                'total_client_usages': len(self.client_usages),
                'client_types': {},
                'methods': {},
            },
            'api_calls': [asdict(call) for call in self.api_calls],
            'client_usages': [asdict(usage) for usage in self.client_usages],
            'endpoint_mappings': {},
        }

        # Count client types
        for call in self.api_calls:
            report['summary']['client_types'][call.client_type] = \
                report['summary']['client_types'].get(call.client_type, 0) + 1
            report['summary']['methods'][call.method] = \
                report['summary']['methods'].get(call.method, 0) + 1

        # Build endpoint mappings
        for endpoint, calls in self.endpoint_mappings.items():
            report['endpoint_mappings'][endpoint] = {
                'endpoint': endpoint,
                'call_count': len(calls),
                'methods': list(set(call.method for call in calls)),
                'client_types': list(set(call.client_type for call in calls)),
                'calls': [asdict(call) for call in calls[:10]]  # Limit to first 10
            }

        return report

    def run(self) -> Dict[str, Any]:
        """Run the complete search"""
        print("Starting API client usage search...")
        print(f"Root directory: {self.root_dir}")

        # Step 1: Search for client classes
        print("\n=== Step 1: Searching for API client classes ===")
        client_classes = self.search_client_classes()
        print(f"Found {len(client_classes)} client classes: {', '.join(sorted(client_classes))}")

        # Step 2: Search Python files
        print("\n=== Step 2: Searching Python files ===")
        self.search_python_api_calls()
        print(f"Found {len(self.api_calls)} API calls in Python files")

        # Step 3: Search TypeScript files
        print("\n=== Step 3: Searching TypeScript/JavaScript files ===")
        self.search_typescript_api_calls()
        print(f"Found {len(self.api_calls)} total API calls")

        # Step 4: Analyze SDK modules
        print("\n=== Step 4: Analyzing SDK modules ===")
        self.analyze_sdk_modules()
        print(f"Found {len(self.client_usages)} SDK client usages")

        # Step 5: Map endpoints
        print("\n=== Step 5: Mapping endpoints ===")
        self.map_endpoints()
        print(f"Mapped {len(self.endpoint_mappings)} unique endpoints")

        # Step 6: Generate report
        print("\n=== Step 6: Generating report ===")
        report = self.generate_report()

        return report


def main():
    """Main entry point"""
    import sys

    # Get root directory from command line or use current directory
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    searcher = APIClientUsageSearcher(root_dir)
    report = searcher.run()

    # Save report
    output_file = Path(root_dir) / 'docs' / 'api-audit' / 'api-client-usage-report.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n=== Report saved to: {output_file} ===")
    print(f"\nSummary:")
    print(f"  Total API calls found: {report['summary']['total_api_calls']}")
    print(f"  Total endpoints: {report['summary']['total_endpoints']}")
    print(f"  Total SDK client usages: {report['summary']['total_client_usages']}")
    print(f"\nClient types:")
    for client_type, count in sorted(report['summary']['client_types'].items()):
        print(f"  {client_type}: {count}")
    print(f"\nHTTP methods:")
    for method, count in sorted(report['summary']['methods'].items()):
        print(f"  {method}: {count}")


if __name__ == '__main__':
    main()

