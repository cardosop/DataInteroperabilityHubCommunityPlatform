#!/usr/bin/env python3
"""
Comprehensive Service Client Audit Script

Audits all service client implementations to identify HTTP client usage,
map methods to endpoints, and identify service-to-service API calls.
This script implements task 9.6.1.3.1 from the ODPS integration tasks.
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
class ServiceClientInfo:
    """Information about a service client class"""
    file_path: str
    class_name: str
    service_name: str
    base_url: str
    http_client_type: str  # httpx.Client, requests, etc.
    methods: List[Dict[str, Any]]


@dataclass
class ServiceClientMethod:
    """Information about a service client method"""
    method_name: str
    http_method: str  # GET, POST, PUT, DELETE, etc.
    endpoint: str
    line_number: int
    parameters: List[str]
    return_type: Optional[str]
    docstring: Optional[str]


class ServiceClientAuditor:
    """Audits service client implementations"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.service_clients: List[ServiceClientInfo] = []
        self.service_to_service_calls: List[Dict[str, Any]] = []

    def find_service_client_files(self) -> List[Path]:
        """Find all service client files"""
        service_client_files = []

        # Search for files matching the pattern *_service_client.py
        for file_path in self.root_dir.rglob("*_service_client.py"):
            # Skip test files
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            service_client_files.append(file_path)

        # Search for files named service_client.py (without prefix)
        for file_path in self.root_dir.rglob("service_client.py"):
            # Skip test files and __pycache__
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            # Skip if already added
            if file_path not in service_client_files:
                service_client_files.append(file_path)

        # Also search for cli_client.py files (like DataContractCLIClient)
        for file_path in self.root_dir.rglob("*cli_client.py"):
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            if file_path not in service_client_files:
                service_client_files.append(file_path)

        return service_client_files

    def extract_base_url(self, node: ast.AST, file_path: Path) -> str:
        """Extract base URL from service client initialization"""
        base_url = "unknown"

        # Look for base_url assignments
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name) and target.id == "base_url":
                        if isinstance(child.value, ast.Call):
                            # getattr(settings, 'SEMANTIC_SERVICE_URL', default_url)
                            if isinstance(child.value.func, ast.Name) and child.value.func.id == "getattr":
                                if len(child.value.args) >= 2:
                                    if isinstance(child.value.args[1], ast.Constant):
                                        value = child.value.args[1].value
                                        base_url = str(value) if value is not None else "unknown"
                        elif isinstance(child.value, ast.Constant):
                            value = child.value.value
                            base_url = str(value) if value is not None else "unknown"
                        elif isinstance(child.value, ast.Name):
                            # Variable reference
                            base_url = f"<{child.value.id}>"

        # Also check for default_url patterns
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name) and target.id == "default_url":
                        if isinstance(child.value, ast.Constant):
                            value = child.value.value
                            base_url = str(value) if value is not None else "unknown"

        return base_url

    def extract_http_client_type(self, node: ast.AST) -> str:
        """Extract HTTP client type (httpx.Client, requests, etc.)"""
        http_client_type = "unknown"

        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name) and target.id == "client":
                        if isinstance(child.value, ast.Call):
                            if isinstance(child.value.func, ast.Attribute):
                                # httpx.Client(...)
                                if isinstance(child.value.func.value, ast.Name):
                                    module = child.value.func.value.id
                                    attr = child.value.func.attr
                                    http_client_type = f"{module}.{attr}"
                                    break
                            elif isinstance(child.value.func, ast.Name):
                                # Client(...)
                                http_client_type = child.value.func.id
                                break

        return http_client_type

    def extract_service_name(self, class_name: str, file_path: Path) -> str:
        """Extract service name from class name or file path"""
        # Remove "ServiceClient" or "Client" suffix
        service_name = class_name.replace("ServiceClient", "").replace("Client", "")

        # If empty, try to extract from file path
        if not service_name:
            file_name = file_path.stem
            service_name = file_name.replace("_service_client", "").replace("_cli_client", "")

        # Convert to lowercase with hyphens
        service_name = re.sub(r'([A-Z])', r'-\1', service_name).lower().lstrip('-')

        return service_name or "unknown"

    def extract_endpoint_from_call(self, call_node: ast.Call, method_name: str) -> Optional[str]:
        """Extract endpoint from HTTP method call"""
        endpoint = None

        # Look for endpoint parameter
        for keyword in call_node.keywords:
            if keyword.arg == "endpoint":
                if isinstance(keyword.value, ast.Constant):
                    endpoint = keyword.value.value
                elif hasattr(ast, 'Str') and isinstance(keyword.value, ast.Str):  # Python < 3.8
                    endpoint = keyword.value.s
                elif isinstance(keyword.value, ast.JoinedStr):  # f-string
                    # Try to extract static parts
                    parts = []
                    for part in keyword.value.values:
                        if isinstance(part, ast.Constant):
                            parts.append(str(part.value))
                        elif hasattr(ast, 'Str') and isinstance(part, ast.Str):  # Python < 3.8
                            parts.append(part.s)
                    if parts:
                        endpoint = "".join(parts)
                elif isinstance(keyword.value, (ast.BinOp, ast.Call, ast.Attribute)):
                    # Dynamic endpoint construction
                    endpoint = f"<dynamic:{method_name}>"

        # Check positional arguments
        # For _request_with_retry(method, endpoint, ...), endpoint is second arg
        # For client.request(method, endpoint, ...), endpoint is second arg
        # For client.get(endpoint, ...), endpoint is first arg
        if not endpoint:
            if len(call_node.args) >= 2:
                # Second arg is usually endpoint for _request_with_retry and client.request
                arg = call_node.args[1]
                endpoint = self._extract_string_from_ast(arg, method_name)
            elif len(call_node.args) >= 1:
                # First arg might be endpoint for client.get/post/etc
                arg = call_node.args[0]
                endpoint = self._extract_string_from_ast(arg, method_name)

        return endpoint

    def _extract_string_from_ast(self, arg: ast.AST, method_name: str) -> Optional[str]:
        """Extract string value from AST node"""
        if isinstance(arg, ast.Constant):
            value = arg.value
            return str(value) if isinstance(value, str) else None
        # Python < 3.8 compatibility
        elif hasattr(ast, 'Str') and isinstance(arg, getattr(ast, 'Str', type(None))):
            return getattr(arg, 's', None)
        elif isinstance(arg, ast.JoinedStr):  # f-string
            parts = []
            for part in arg.values:
                if isinstance(part, ast.Constant):
                    value = part.value
                    if isinstance(value, str):
                        parts.append(value)
                # Python < 3.8 compatibility
                elif hasattr(ast, 'Str') and isinstance(part, getattr(ast, 'Str', type(None))):
                    s_value = getattr(part, 's', None)
                    if s_value:
                        parts.append(s_value)
            if parts:
                return "".join(parts)
        elif isinstance(arg, (ast.BinOp, ast.Call, ast.Attribute)):
            return f"<dynamic:{method_name}>"
        return None

    def extract_http_method_from_call(self, call_node: ast.Call) -> str:
        """Extract HTTP method from call"""
        # Check if it's a method call like client.get(), client.post()
        if isinstance(call_node.func, ast.Attribute):
            method_name = call_node.func.attr.upper()
            if method_name in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                return method_name

        # Check if it's client.request(method, ...) or _request_with_retry(method, ...)
        if isinstance(call_node.func, ast.Attribute):
            if call_node.func.attr in ["request", "_request_with_retry"]:
                if len(call_node.args) > 0:
                    arg = call_node.args[0]
                    if isinstance(arg, ast.Constant):
                        value = arg.value
                        return str(value).upper() if value is not None else "UNKNOWN"
                    # Python < 3.8 compatibility
                    elif hasattr(ast, 'Str') and isinstance(arg, getattr(ast, 'Str', type(None))):
                        s_value = getattr(arg, 'value', None)
                        return s_value.upper() if s_value else "UNKNOWN"

        return "UNKNOWN"

    def extract_methods(self, class_node: ast.ClassDef, file_path: Path) -> List[Dict[str, Any]]:
        """Extract methods from service client class"""
        methods = []

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_name = node.name

                # Skip private methods and special methods
                if method_name.startswith("_") and method_name != "__init__":
                    continue

                # Extract docstring
                docstring = ast.get_docstring(node)

                # Extract parameters
                parameters = [arg.arg for arg in node.args.args]

                # Extract return type annotation
                return_type = None
                if node.returns:
                    if isinstance(node.returns, ast.Name):
                        return_type = node.returns.id
                    elif isinstance(node.returns, ast.Subscript):
                        return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)

                # Find HTTP calls in method body (including nested functions)
                http_calls = []

                def extract_calls_from_node(node: ast.AST):
                    """Recursively extract HTTP calls from AST node"""
                    if isinstance(node, ast.Call):
                        # Check if it's _request_with_retry(...)
                        if isinstance(node.func, ast.Attribute):
                            if node.func.attr == "_request_with_retry":
                                http_method = self.extract_http_method_from_call(node)
                                endpoint = self.extract_endpoint_from_call(node, method_name)
                                if endpoint:
                                    http_calls.append({
                                        "http_method": http_method,
                                        "endpoint": endpoint,
                                        "line_number": node.lineno
                                    })
                            # Check if it's self.client.request(...) or self.client.get(...)
                            elif isinstance(node.func.value, ast.Attribute):
                                if node.func.value.attr == "client":
                                    http_method = self.extract_http_method_from_call(node)
                                    endpoint = self.extract_endpoint_from_call(node, method_name)
                                    if endpoint:
                                        http_calls.append({
                                            "http_method": http_method,
                                            "endpoint": endpoint,
                                            "line_number": node.lineno
                                        })
                            # Check if it's client.request(...) or client.get(...)
                            elif isinstance(node.func.value, ast.Name) and node.func.value.id == "client":
                                http_method = self.extract_http_method_from_call(node)
                                endpoint = self.extract_endpoint_from_call(node, method_name)
                                if endpoint:
                                    http_calls.append({
                                        "http_method": http_method,
                                        "endpoint": endpoint,
                                        "line_number": node.lineno
                                    })

                    # Recursively process child nodes
                    for child in ast.iter_child_nodes(node):
                        extract_calls_from_node(child)

                # Extract calls from the method node and all nested nodes
                extract_calls_from_node(node)

                if http_calls or method_name != "__init__":
                    methods.append({
                        "method_name": method_name,
                        "parameters": parameters,
                        "return_type": return_type,
                        "docstring": docstring,
                        "line_number": node.lineno,
                        "http_calls": http_calls
                    })

        return methods

    def audit_file(self, file_path: Path) -> Optional[ServiceClientInfo]:
        """Audit a single service client file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a service client class
                    class_name = node.name
                    if "Client" in class_name and not class_name.startswith("Test"):
                        # Extract base URL from __init__
                        base_url = "unknown"
                        http_client_type = "unknown"

                        for child in node.body:
                            if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                                base_url = self.extract_base_url(child, file_path)
                                http_client_type = self.extract_http_client_type(child)
                                break

                        service_name = self.extract_service_name(class_name, file_path)
                        methods = self.extract_methods(node, file_path)

                        return ServiceClientInfo(
                            file_path=str(file_path.relative_to(self.root_dir)),
                            class_name=class_name,
                            service_name=service_name,
                            base_url=base_url,
                            http_client_type=http_client_type,
                            methods=methods
                        )
        except Exception as e:
            print(f"Error auditing {file_path}: {e}")
            return None

        return None

    def identify_service_to_service_calls(self):
        """Identify service-to-service API calls"""
        for client_info in self.service_clients:
            for method in client_info.methods:
                for http_call in method.get("http_calls", []):
                    self.service_to_service_calls.append({
                        "service_client": client_info.class_name,
                        "service_name": client_info.service_name,
                        "method": method["method_name"],
                        "http_method": http_call["http_method"],
                        "endpoint": http_call["endpoint"],
                        "full_url": f"{client_info.base_url}{http_call['endpoint']}",
                        "file_path": client_info.file_path,
                        "line_number": http_call["line_number"]
                    })

    def run(self) -> Dict[str, Any]:
        """Run the audit"""
        print("Searching for service client files...")
        service_client_files = self.find_service_client_files()
        print(f"Found {len(service_client_files)} service client files")

        for file_path in service_client_files:
            print(f"Auditing {file_path}...")
            client_info = self.audit_file(file_path)
            if client_info:
                self.service_clients.append(client_info)

        print(f"Found {len(self.service_clients)} service client classes")

        # Identify service-to-service calls
        self.identify_service_to_service_calls()

        # Generate report
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_service_clients": len(self.service_clients),
                "total_methods": sum(len(client.methods) for client in self.service_clients),
                "total_service_to_service_calls": len(self.service_to_service_calls),
                "services": [client.service_name for client in self.service_clients]
            },
            "service_clients": [asdict(client) for client in self.service_clients],
            "service_to_service_calls": self.service_to_service_calls
        }

        return report


def main():
    """Main entry point"""
    import sys

    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    output_file = sys.argv[2] if len(sys.argv) > 2 else "docs/api-audit/service-client-audit.json"

    auditor = ServiceClientAuditor(root_dir)
    report = auditor.run()

    # Save report
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to {output_path}")
    print(f"Summary:")
    print(f"  Total service clients: {report['summary']['total_service_clients']}")
    print(f"  Total methods: {report['summary']['total_methods']}")
    print(f"  Total service-to-service calls: {report['summary']['total_service_to_service_calls']}")


if __name__ == "__main__":
    main()

