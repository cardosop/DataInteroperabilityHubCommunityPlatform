#!/usr/bin/env python3
"""
Comprehensive Inter-Service Communication Search Script

Searches for inter-service communication patterns including:
- Worker service → API service calls
- External services → API service calls
- API service → External services calls
- Inter-service dependencies mapping

This script implements task 9.6.1.3.2 from the ODPS integration tasks.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ServiceCall:
    """Represents a service-to-service call"""
    file_path: str
    line_number: int
    source_service: str  # Service making the call
    target_service: str  # Service being called
    endpoint: str  # Endpoint being called
    method: str  # HTTP method
    client_type: str  # Type of client (ServiceClient, httpx, requests)
    context: str  # Code context around the call


@dataclass
class ServiceDependency:
    """Represents a service dependency"""
    source_service: str
    target_service: str
    call_count: int
    endpoints: List[str]
    call_locations: List[Tuple[str, int]]  # (file_path, line_number)


class InterServiceCommunicationSearcher:
    """Searches for inter-service communication patterns"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.service_calls: List[ServiceCall] = []
        self.dependencies: Dict[Tuple[str, str], ServiceDependency] = {}

        # Known service names and their patterns
        self.service_patterns = {
            'api-service': ['api-service', 'localhost:8000', ':8000', 'API_SERVICE_URL'],
            'worker-service': ['worker-service', 'localhost:8080', ':8080', 'WORKER_SERVICE_URL'],
            'datacontract-service': ['datacontract-service', 'localhost:8080', ':8080', 'DATACONTRACT_SERVICE_URL'],
            'dq-service': ['dq-service', 'localhost:8083', ':8083', 'DQ_SERVICE_URL'],
            'compliance-service': ['compliance-service', 'localhost:8082', ':8082', 'COMPLIANCE_SERVICE_URL'],
            'semantic-service': ['semantic-service', 'localhost:8081', ':8081', 'SEMANTIC_SERVICE_URL'],
            'search-service': ['search-service', 'localhost:8085', ':8085', 'SEARCH_SERVICE_URL'],
            'observability-service': ['observability-service', 'localhost:8086', ':8086', 'OBSERVABILITY_SERVICE_URL'],
            'webhook-service': ['webhook-service', 'localhost:8087', ':8087', 'WEBHOOK_SERVICE_URL'],
            'workflow-engine-service': ['workflow-engine-service', 'localhost:8088', ':8088', 'WORKFLOW_ENGINE_SERVICE_URL'],
            'workflow-registry-service': ['workflow-registry-service', 'localhost:8089', ':8089', 'WORKFLOW_REGISTRY_SERVICE_URL'],
            'event-bus-health-service': ['event-bus-health-service', 'localhost:8090', ':8090', 'EVENT_BUS_HEALTH_SERVICE_URL'],
            'event-schema-registry-service': ['event-schema-registry-service', 'localhost:8091', ':8091', 'EVENT_SCHEMA_REGISTRY_SERVICE_URL'],
        }

        # Service client classes mapping
        self.service_client_classes = {
            'ComplianceServiceClient': 'compliance-service',
            'DQServiceClient': 'dq-service',
            'SemanticServiceClient': 'semantic-service',
            'DataContractCLIClient': 'datacontract-service',
            'FusekiClient': 'semantic-service',  # Fuseki is part of semantic service
        }

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

    def identify_source_service(self, file_path: str) -> str:
        """Identify the source service from file path"""
        path_lower = file_path.lower()

        # Check for service directories
        if '/services/worker' in path_lower or '/worker/' in path_lower:
            return 'worker-service'
        elif '/services/api' in path_lower or '/api/' in path_lower:
            return 'api-service'
        elif '/services/datacontract' in path_lower:
            return 'datacontract-service'
        elif '/services/dq' in path_lower:
            return 'dq-service'
        elif '/services/compliance' in path_lower:
            return 'compliance-service'
        elif '/services/semantic' in path_lower:
            return 'semantic-service'
        elif '/services/search' in path_lower:
            return 'search-service'
        elif '/services/observability' in path_lower:
            return 'observability-service'
        elif '/services/webhook' in path_lower:
            return 'webhook-service'
        elif '/services/workflow-engine' in path_lower:
            return 'workflow-engine-service'
        elif '/services/workflow-registry' in path_lower:
            return 'workflow-registry-service'
        elif '/services/event-bus' in path_lower:
            return 'event-bus-health-service'
        elif '/services/event-schema-registry' in path_lower:
            return 'event-schema-registry-service'
        elif '/hub/apps' in path_lower:
            # Hub apps are part of API service
            return 'api-service'
        elif '/cli' in path_lower:
            return 'cli'  # CLI is external
        elif '/sdk' in path_lower:
            return 'sdk'  # SDK is external

        return 'unknown'

    def identify_target_service(self, line: str, context_lines: List[str]) -> Optional[str]:
        """Identify the target service from a line of code"""
        line_lower = line.lower()

        # Check for service URLs
        for service_name, patterns in self.service_patterns.items():
            for pattern in patterns:
                if pattern.lower() in line_lower:
                    return service_name

        # Check for service client class usage
        for client_class, service_name in self.service_client_classes.items():
            if client_class in line:
                return service_name

        # Check context lines
        for ctx_line in context_lines[:5]:
            ctx_lower = ctx_line.lower()
            for service_name, patterns in self.service_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in ctx_lower:
                        return service_name

        return None

    def extract_endpoint_from_line(self, line: str, context_lines: List[str]) -> Optional[str]:
        """Extract endpoint from a line of code"""
        # Look for endpoint patterns
        patterns = [
            r'["\']([^"\']*/(?:health|healthz|ready|metrics|api|scan|run|map|sparql|validate|normalize)[^"\']*)["\']',
            r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',
            r'url\s*[:=]\s*["\']([^"\']+)["\']',
            r'["\'](/[^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                endpoint = match.group(1)
                if endpoint.startswith('/') or 'http' in endpoint:
                    return endpoint

        # Check context lines
        for ctx_line in context_lines[:5]:
            for pattern in patterns:
                match = re.search(pattern, ctx_line)
                if match:
                    endpoint = match.group(1)
                    if endpoint.startswith('/') or 'http' in endpoint:
                        return endpoint

        return None

    def search_worker_to_api_calls(self):
        """Search for worker service → API service calls"""
        print("Searching for worker service → API service calls...")

        worker_files = list(self.root_dir.rglob('services/worker/**/*.py'))
        worker_files.extend(self.root_dir.rglob('hub/apps/jobs/**/*.py'))

        for py_file in worker_files:
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Look for API service calls (HTTP)
                    if re.search(r'api-service|localhost:8000|:8000|API_SERVICE_URL', line, re.IGNORECASE):
                        target_service = self.identify_target_service(line, lines[i:i+5])
                        if target_service == 'api-service':
                            endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                            method = self._extract_method_from_line(line)

                            self.service_calls.append(ServiceCall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                source_service='worker-service',
                                target_service='api-service',
                                endpoint=endpoint or 'unknown',
                                method=method,
                                client_type=self._extract_client_type(line),
                                context=self._get_context(lines, i)
                            ))

                    # Look for Redis queue patterns (worker receives jobs from API via Redis)
                    # This is indirect communication: API → Redis → Worker
                    if re.search(r'enqueue|queue\.enqueue|rq\.enqueue|get_queue', line, re.IGNORECASE):
                        # Check if this is in API service code (API enqueuing jobs for worker)
                        if '/hub/apps' in str(py_file) or '/api/' in str(py_file):
                            # This represents API → Worker communication via Redis
                            self.service_calls.append(ServiceCall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                source_service='api-service',
                                target_service='worker-service',
                                endpoint='redis-queue',
                                method='ENQUEUE',
                                client_type='redis-rq',
                                context=self._get_context(lines, i)
                            ))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def search_external_to_api_calls(self):
        """Search for external services → API service calls"""
        print("Searching for external services → API service calls...")

        # Search CLI and SDK for API calls
        external_dirs = [
            self.root_dir / 'cli',
            self.root_dir / 'sdk',
        ]

        for external_dir in external_dirs:
            if not external_dir.exists():
                continue

            for py_file in external_dir.rglob('*.py'):
                if self.should_skip_file(py_file):
                    continue

                try:
                    content = py_file.read_text(encoding='utf-8')
                    lines = content.split('\n')

                    for i, line in enumerate(lines, 1):
                        # Look for API service calls
                        if re.search(r'api-service|localhost:8000|:8000|/api/v1|base_url|baseURL', line, re.IGNORECASE):
                            target_service = self.identify_target_service(line, lines[i:i+5])
                            if target_service == 'api-service':
                                endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                                method = self._extract_method_from_line(line)

                                source = 'cli' if '/cli' in str(py_file) else 'sdk'

                                self.service_calls.append(ServiceCall(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    source_service=source,
                                    target_service='api-service',
                                    endpoint=endpoint or 'unknown',
                                    method=method,
                                    client_type=self._extract_client_type(line),
                                    context=self._get_context(lines, i)
                                ))

                except Exception as e:
                    print(f"Error processing {py_file}: {e}")

    def search_api_to_external_calls(self):
        """Search for API service → External services calls"""
        print("Searching for API service → External services calls...")

        # Search hub/apps for service client usage
        hub_apps_dir = self.root_dir / 'hub' / 'apps'
        if not hub_apps_dir.exists():
            return

        for py_file in hub_apps_dir.rglob('*.py'):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Look for service client usage
                    for client_class, service_name in self.service_client_classes.items():
                        if client_class in line:
                            endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                            method = self._extract_method_from_line(line)

                            self.service_calls.append(ServiceCall(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=i,
                                source_service='api-service',
                                target_service=service_name,
                                endpoint=endpoint or 'unknown',
                                method=method,
                                client_type=client_class,
                                context=self._get_context(lines, i)
                            ))

                    # Look for service URL patterns
                    for service_name, patterns in self.service_patterns.items():
                        if service_name == 'api-service':
                            continue  # Skip API service itself

                        for pattern in patterns:
                            if pattern in line and ('http' in line.lower() or 'url' in line.lower()):
                                endpoint = self.extract_endpoint_from_line(line, lines[i:i+5])
                                method = self._extract_method_from_line(line)

                                self.service_calls.append(ServiceCall(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    source_service='api-service',
                                    target_service=service_name,
                                    endpoint=endpoint or 'unknown',
                                    method=method,
                                    client_type=self._extract_client_type(line),
                                    context=self._get_context(lines, i)
                                ))
                                break

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def search_service_client_usage(self):
        """Search for service client class usage"""
        print("Searching for service client usage...")

        for py_file in self.root_dir.rglob('*.py'):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                lines = content.split('\n')

                source_service = self.identify_source_service(str(py_file.relative_to(self.root_dir)))

                for i, line in enumerate(lines, 1):
                    # Look for service client instantiation or method calls
                    for client_class, service_name in self.service_client_classes.items():
                        if client_class in line:
                            # Check if it's instantiation or method call
                            if '=' in line or '(' in line:
                                endpoint = self.extract_endpoint_from_line(line, lines[i:i+10])
                                method = self._extract_method_from_line(line)

                                self.service_calls.append(ServiceCall(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    source_service=source_service,
                                    target_service=service_name,
                                    endpoint=endpoint or 'unknown',
                                    method=method,
                                    client_type=client_class,
                                    context=self._get_context(lines, i, context_lines=10)
                                ))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def map_dependencies(self):
        """Map inter-service dependencies"""
        print("Mapping inter-service dependencies...")

        for call in self.service_calls:
            key = (call.source_service, call.target_service)

            if key not in self.dependencies:
                self.dependencies[key] = ServiceDependency(
                    source_service=call.source_service,
                    target_service=call.target_service,
                    call_count=0,
                    endpoints=[],
                    call_locations=[]
                )

            dep = self.dependencies[key]
            dep.call_count += 1

            if call.endpoint not in dep.endpoints:
                dep.endpoints.append(call.endpoint)

            location = (call.file_path, call.line_number)
            if location not in dep.call_locations:
                dep.call_locations.append(location)

    def _extract_method_from_line(self, line: str) -> str:
        """Extract HTTP method from line"""
        method_match = re.search(r'\.(get|post|put|patch|delete|request)', line, re.IGNORECASE)
        if method_match:
            return method_match.group(1).upper()
        return 'UNKNOWN'

    def _extract_client_type(self, line: str) -> str:
        """Extract client type from line"""
        if 'httpx' in line.lower():
            return 'httpx'
        elif 'requests' in line.lower():
            return 'requests'
        elif any(client_class in line for client_class in self.service_client_classes.keys()):
            for client_class in self.service_client_classes.keys():
                if client_class in line:
                    return client_class
        return 'unknown'

    def _get_context(self, lines: List[str], line_num: int, context_lines: int = 5) -> str:
        """Get context around a line"""
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context = lines[start:end]
        return '\n'.join(context)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_service_calls': len(self.service_calls),
                'total_dependencies': len(self.dependencies),
                'worker_to_api_calls': len([c for c in self.service_calls if c.source_service == 'worker-service' and c.target_service == 'api-service']),
                'external_to_api_calls': len([c for c in self.service_calls if c.source_service in ['cli', 'sdk'] and c.target_service == 'api-service']),
                'api_to_external_calls': len([c for c in self.service_calls if c.source_service == 'api-service' and c.target_service != 'api-service']),
                'services_involved': sorted(list(set([c.source_service for c in self.service_calls] + [c.target_service for c in self.service_calls]))),
            },
            'service_calls': [asdict(call) for call in self.service_calls],
            'dependencies': {},
        }

        # Build dependencies dictionary
        for key, dep in self.dependencies.items():
            report['dependencies'][f"{dep.source_service}->{dep.target_service}"] = {
                'source_service': dep.source_service,
                'target_service': dep.target_service,
                'call_count': dep.call_count,
                'endpoints': dep.endpoints[:20],  # Limit to first 20
                'call_locations': dep.call_locations[:20],  # Limit to first 20
            }

        return report

    def run(self) -> Dict[str, Any]:
        """Run the complete search"""
        print("Starting inter-service communication search...")
        print(f"Root directory: {self.root_dir}")

        # Step 1: Search worker → API calls
        print("\n=== Step 1: Searching worker service → API service calls ===")
        self.search_worker_to_api_calls()
        print(f"Found {len([c for c in self.service_calls if c.source_service == 'worker-service'])} worker service calls")

        # Step 2: Search external → API calls
        print("\n=== Step 2: Searching external services → API service calls ===")
        self.search_external_to_api_calls()
        print(f"Found {len([c for c in self.service_calls if c.source_service in ['cli', 'sdk']])} external service calls")

        # Step 3: Search API → External calls
        print("\n=== Step 3: Searching API service → External services calls ===")
        self.search_api_to_external_calls()
        print(f"Found {len([c for c in self.service_calls if c.source_service == 'api-service'])} API service calls")

        # Step 4: Search service client usage
        print("\n=== Step 4: Searching service client usage ===")
        self.search_service_client_usage()
        print(f"Found {len(self.service_calls)} total service calls")

        # Step 5: Map dependencies
        print("\n=== Step 5: Mapping inter-service dependencies ===")
        self.map_dependencies()
        print(f"Mapped {len(self.dependencies)} service dependencies")

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

    searcher = InterServiceCommunicationSearcher(root_dir)
    report = searcher.run()

    # Save report
    output_file = Path(root_dir) / 'docs' / 'api-audit' / 'inter-service-communication-report.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n=== Report saved to: {output_file} ===")
    print(f"\nSummary:")
    print(f"  Total service calls: {report['summary']['total_service_calls']}")
    print(f"  Total dependencies: {report['summary']['total_dependencies']}")
    print(f"  Worker → API calls: {report['summary']['worker_to_api_calls']}")
    print(f"  External → API calls: {report['summary']['external_to_api_calls']}")
    print(f"  API → External calls: {report['summary']['api_to_external_calls']}")
    print(f"\nServices involved:")
    for service in report['summary']['services_involved']:
        print(f"  - {service}")
    print(f"\nDependencies:")
    for dep_key, dep_data in list(report['dependencies'].items())[:10]:
        print(f"  {dep_key}: {dep_data['call_count']} calls, {len(dep_data['endpoints'])} endpoints")
    if len(report['dependencies']) > 10:
        print(f"  ... and {len(report['dependencies']) - 10} more dependencies")


if __name__ == '__main__':
    main()

