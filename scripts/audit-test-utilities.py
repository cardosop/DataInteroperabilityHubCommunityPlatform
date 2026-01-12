#!/usr/bin/env python3
"""
Test Utilities and Helpers Audit Script

Comprehensive audit tool for analyzing test utility modules and helper functions.
Searches for utility modules, helper functions, and endpoint URL construction in utilities.

Usage:
    python audit-test-utilities.py [options]

Options:
    --output-format          Output format: json, markdown (default: json)
    --output-file PATH       Output file path (default: docs/api-audit/test-utilities-report.json)
    --project-root PATH      Project root directory (default: auto-detect)
    --verbose                Verbose output
    --help                   Show this help message
"""
import os
import sys
import re
import json
import ast
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class UtilityModule:
    """Represents a test utility module"""
    path: str
    type: str  # 'utility', 'helper', 'conftest', 'base_class'
    functions: List[str]
    classes: List[str]
    line_count: int
    has_endpoint_urls: bool


@dataclass
class HelperFunction:
    """Represents a helper function"""
    name: str
    file: str
    line_number: int
    type: str  # 'function', 'method', 'fixture'
    signature: str
    docstring: Optional[str]


@dataclass
class EndpointURL:
    """Represents an endpoint URL found in utilities"""
    endpoint_path: str
    file: str
    line_number: int
    context: str
    function_name: Optional[str]
    is_dynamic: bool


class TestUtilitiesAuditor:
    """Audit test utilities and helpers for endpoint URL references"""

    # Patterns to identify utility modules
    UTILITY_PATTERNS = [
        r'.*utils?/.*\.py$',
        r'.*helper.*\.py$',
        r'.*conftest\.py$',
        r'.*test.*base.*\.py$',
        r'.*test.*util.*\.py$',
    ]

    # Patterns to match endpoint URLs
    ENDPOINT_PATTERNS = [
        # Direct path strings: '/api/v1/...'
        r'["\'](/api/v1/[^"\']+)["\']',
        # f-strings: f'/api/v1/...'
        r'f["\'](/api/v1/[^"\']+)["\']',
        # Full URLs: 'http://.../api/v1/...'
        r'["\'](https?://[^"\']*?/api/v1/[^"\']+)["\']',
        # URL construction: urljoin, urlparse, etc.
        r'urljoin\([^,]+,\s*["\'](/api/v1/[^"\']+)["\']',
        # Format strings with /api/v1/
        r'["\'].*?/api/v1/.*?["\']',
    ]

    # Helper function name patterns
    HELPER_NAME_PATTERNS = [
        r'^get_.*',
        r'^create_.*',
        r'^build_.*',
        r'^make_.*',
        r'^helper_.*',
        r'^.*_helper$',
        r'^.*_util$',
        r'^.*_client$',
        r'^.*_api$',
    ]

    def __init__(
        self,
        project_root: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Initialize the test utilities auditor.

        Args:
            project_root: Project root directory (default: auto-detect)
            verbose: Enable verbose output
        """
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            self.project_root = self._find_project_root()
        self.verbose = verbose
        self.utility_modules: List[Dict[str, Any]] = []
        self.helper_functions: List[Dict[str, Any]] = []
        self.endpoint_urls: List[Dict[str, Any]] = []
        self.compiled_endpoint_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ENDPOINT_PATTERNS]
        self.compiled_helper_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.HELPER_NAME_PATTERNS]

    def _find_project_root(self) -> Path:
        """Find project root directory"""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / 'manage.py').exists() or \
               (current / 'pyproject.toml').exists() or \
               (current / 'setup.py').exists() or \
               (current / '.git').exists():
                return current
            current = current.parent
        return Path.cwd()

    def _find_utility_modules(self) -> List[Dict[str, Any]]:
        """
        Find test utility modules.

        Returns:
            List of utility module information
        """
        utilities = []
        seen_files = set()

        # Search in tests/utils/ directory
        utils_dir = self.project_root / 'tests' / 'utils'
        if utils_dir.exists():
            for py_file in utils_dir.rglob('*.py'):
                if py_file.name == '__init__.py':
                    continue
                if py_file not in seen_files:
                    utilities.append(self._analyze_utility_file(py_file))
                    seen_files.add(py_file)

        # Search for conftest.py files (exclude venv and virtual environments)
        for conftest_file in self.project_root.rglob('**/conftest.py'):
            conftest_str = str(conftest_file)
            if '__pycache__' not in conftest_str and \
               'venv' not in conftest_str and \
               '.venv' not in conftest_str and \
               'virtualenv' not in conftest_str and \
               conftest_file not in seen_files:
                utilities.append(self._analyze_utility_file(conftest_file, 'conftest'))
                seen_files.add(conftest_file)

        # Search for helper/utility files in tests directory (exclude venv)
        for pattern in ['*helper*.py', '*util*.py', '*test*base*.py']:
            for py_file in (self.project_root / 'tests').rglob(pattern):
                py_file_str = str(py_file)
                if '__pycache__' not in py_file_str and \
                   'venv' not in py_file_str and \
                   '.venv' not in py_file_str and \
                   'virtualenv' not in py_file_str and \
                   py_file not in seen_files:
                    if py_file.name != '__init__.py':
                        utilities.append(self._analyze_utility_file(py_file, 'helper'))
                        seen_files.add(py_file)

        return utilities

    def _analyze_utility_file(self, file_path: Path, file_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a utility file to extract functions, classes, and endpoint URLs.

        Args:
            file_path: Path to the utility file
            file_type: Type of file ('utility', 'conftest', 'helper', None for auto-detect)

        Returns:
            Dictionary with utility file information
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not read {file_path}: {e}")
            return {
                'path': str(file_path.relative_to(self.project_root)),
                'type': file_type or 'utility',
                'functions': [],
                'classes': [],
                'line_count': 0,
                'has_endpoint_urls': False
            }

        # Detect file type if not provided
        if not file_type:
            if 'conftest' in file_path.name:
                file_type = 'conftest'
            elif 'helper' in file_path.name.lower():
                file_type = 'helper'
            elif 'base' in file_path.name.lower():
                file_type = 'base_class'
            else:
                file_type = 'utility'

        # Parse AST to find functions and classes
        functions = []
        classes = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
        except SyntaxError:
            # File has syntax errors, skip AST parsing
            pass

        # Check for endpoint URLs
        endpoint_urls = self._extract_endpoint_urls(content, file_path)
        has_endpoint_urls = len(endpoint_urls) > 0

        return {
            'path': str(file_path.relative_to(self.project_root)),
            'type': file_type,
            'functions': functions,
            'classes': classes,
            'line_count': len(content.split('\n')),
            'has_endpoint_urls': has_endpoint_urls
        }

    def _find_helper_functions(self) -> List[Dict[str, Any]]:
        """
        Find helper functions in test files.

        Returns:
            List of helper function information
        """
        helpers = []

        # Search in utility modules (exclude venv and virtual environments)
        for util_file_path in self.project_root.rglob('**/tests/**/*.py'):
            util_file_str = str(util_file_path)
            if '__pycache__' in util_file_str or \
               'venv' in util_file_str or \
               '.venv' in util_file_str or \
               'virtualenv' in util_file_str:
                continue

            # Skip if it's a test file (test_*.py)
            if util_file_path.name.startswith('test_') and util_file_path.name != 'test_utils.py':
                continue

            try:
                content = util_file_path.read_text(encoding='utf-8')
            except Exception:
                continue

            # Parse AST to find helper functions
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check if function name matches helper patterns
                        is_helper = any(pattern.match(node.name) for pattern in self.compiled_helper_patterns)

                        # Also check if it's in a utility file
                        is_in_utility = 'utils' in str(util_file_path) or 'conftest' in util_file_path.name or \
                                       'helper' in util_file_path.name.lower()

                        if is_helper or is_in_utility:
                            # Extract function signature
                            signature = node.name
                            if node.args.args:
                                args = [arg.arg for arg in node.args.args]
                                signature = f"{node.name}({', '.join(args)})"

                            # Extract docstring
                            docstring = ast.get_docstring(node)

                            # Check if function is a pytest fixture
                            is_fixture = False
                            if hasattr(node, 'decorator_list'):
                                for decorator in node.decorator_list:
                                    # Check for @pytest.fixture or @fixture
                                    if isinstance(decorator, ast.Name):
                                        if decorator.id == 'fixture':
                                            is_fixture = True
                                            break
                                    elif isinstance(decorator, ast.Attribute):
                                        if decorator.attr == 'fixture':
                                            is_fixture = True
                                            break
                                    elif isinstance(decorator, ast.Call):
                                        # Handle @pytest.fixture() or @fixture()
                                        if isinstance(decorator.func, ast.Name) and decorator.func.id == 'fixture':
                                            is_fixture = True
                                            break
                                        elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'fixture':
                                            is_fixture = True
                                            break

                            helpers.append({
                                'name': node.name,
                                'file': str(util_file_path.relative_to(self.project_root)),
                                'line_number': node.lineno,
                                'type': 'fixture' if is_fixture else 'function',
                                'signature': signature,
                                'docstring': docstring
                            })
            except SyntaxError:
                # Skip files with syntax errors
                continue

        return helpers

    def _extract_endpoint_urls(
        self,
        content: str,
        file_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Extract endpoint URLs from file content.

        Args:
            content: File content to search
            file_path: Path to the file being searched

        Returns:
            List of endpoint URL information
        """
        endpoints = []
        lines = content.split('\n')

        # Try to find function context for each endpoint
        function_context = {}
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Constant):
                            value = child.value
                            if isinstance(value, str) and '/api/v1/' in value:
                                function_context[child.lineno] = node.name
        except SyntaxError:
            pass

        for line_num, line in enumerate(lines, start=1):
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Search for endpoint patterns
            for pattern in self.compiled_endpoint_patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group(0)
                    endpoint_path = None
                    is_dynamic = False

                    # Extract endpoint path
                    if '/api/v1/' in matched_text:
                        path_match = re.search(r'/api/v1/[^"\']+', matched_text)
                        if path_match:
                            endpoint_path = path_match.group(0)
                            if 'f"' in matched_text or "f'" in matched_text:
                                is_dynamic = True

                    if endpoint_path:
                        # Find function context
                        func_name = function_context.get(line_num)
                        if not func_name:
                            # Try to find function name from AST
                            try:
                                tree = ast.parse(content)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.FunctionDef):
                                        if node.lineno <= line_num <= (node.lineno + len(node.body) if hasattr(node, 'body') else node.lineno + 10):
                                            func_name = node.name
                                            break
                            except SyntaxError:
                                pass

                        endpoints.append({
                            'endpoint_path': endpoint_path,
                            'file': str(file_path.relative_to(self.project_root)),
                            'line_number': line_num,
                            'context': line.strip()[:100],  # First 100 chars
                            'function_name': func_name,
                            'is_dynamic': is_dynamic
                        })

        return endpoints

    def audit(self) -> Dict[str, Any]:
        """
        Perform comprehensive audit of test utilities and helpers.

        Returns:
            Dictionary with audit results
        """
        if self.verbose:
            print("Searching for utility modules...")
        self.utility_modules = self._find_utility_modules()
        if self.verbose:
            print(f"  Found {len(self.utility_modules)} utility modules")

        if self.verbose:
            print("Searching for helper functions...")
        self.helper_functions = self._find_helper_functions()
        if self.verbose:
            print(f"  Found {len(self.helper_functions)} helper functions")

        if self.verbose:
            print("Extracting endpoint URLs from utilities...")
        # Extract endpoint URLs from all utility modules
        for util in self.utility_modules:
            util_path = self.project_root / util['path']
            if util_path.exists():
                try:
                    content = util_path.read_text(encoding='utf-8')
                    endpoints = self._extract_endpoint_urls(content, util_path)
                    self.endpoint_urls.extend(endpoints)
                except Exception:
                    pass

        # Also extract from helper functions' files
        seen_files = set()
        for helper in self.helper_functions:
            helper_file = self.project_root / helper['file']
            if helper_file.exists() and helper_file not in seen_files:
                try:
                    content = helper_file.read_text(encoding='utf-8')
                    endpoints = self._extract_endpoint_urls(content, helper_file)
                    self.endpoint_urls.extend(endpoints)
                    seen_files.add(helper_file)
                except Exception:
                    pass

        if self.verbose:
            print(f"  Found {len(self.endpoint_urls)} endpoint URLs in utilities")

        # Generate summary
        summary = self._generate_summary()

        return {
            'summary': summary,
            'utility_modules': self.utility_modules,
            'helper_functions': self.helper_functions,
            'endpoint_urls': self.endpoint_urls
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        # Count utilities by type
        by_type = defaultdict(int)
        for util in self.utility_modules:
            by_type[util['type']] += 1

        # Count helpers by type
        helpers_by_type = defaultdict(int)
        for helper in self.helper_functions:
            helpers_by_type[helper['type']] += 1

        # Count utilities with endpoint URLs
        utilities_with_endpoints = sum(1 for util in self.utility_modules if util.get('has_endpoint_urls', False))

        # Count unique endpoint paths
        unique_endpoints = set(e['endpoint_path'] for e in self.endpoint_urls)

        # Count dynamic vs static
        dynamic_count = sum(1 for e in self.endpoint_urls if e.get('is_dynamic', False))
        static_count = len(self.endpoint_urls) - dynamic_count

        return {
            'total_utility_modules': len(self.utility_modules),
            'total_helper_functions': len(self.helper_functions),
            'total_endpoint_urls': len(self.endpoint_urls),
            'utilities_by_type': dict(by_type),
            'helpers_by_type': dict(helpers_by_type),
            'utilities_with_endpoint_urls': utilities_with_endpoints,
            'unique_endpoint_paths': len(unique_endpoints),
            'dynamic_endpoint_urls': dynamic_count,
            'static_endpoint_urls': static_count
        }

    def _generate_json_report(self, output_file: Path):
        """Generate JSON report"""
        result = {
            'summary': self._generate_summary(),
            'utility_modules': self.utility_modules,
            'helper_functions': self.helper_functions,
            'endpoint_urls': self.endpoint_urls
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        if self.verbose:
            print(f"JSON report written to {output_file}")

    def _generate_markdown_report(self, output_file: Path):
        """Generate Markdown report"""
        summary = self._generate_summary()

        lines = [
            '# Test Utilities and Helpers Impact Analysis',
            '',
            '## Summary',
            '',
            f'- **Total Utility Modules**: {summary["total_utility_modules"]}',
            f'- **Total Helper Functions**: {summary["total_helper_functions"]}',
            f'- **Total Endpoint URLs**: {summary["total_endpoint_urls"]}',
            f'- **Utilities with Endpoint URLs**: {summary["utilities_with_endpoint_urls"]}',
            f'- **Unique Endpoint Paths**: {summary["unique_endpoint_paths"]}',
            '',
            '### Utilities by Type',
            '',
        ]

        for util_type, count in sorted(summary['utilities_by_type'].items()):
            lines.append(f'- **{util_type}**: {count}')

        lines.extend([
            '',
            '### Helpers by Type',
            '',
        ])

        for helper_type, count in sorted(summary['helpers_by_type'].items()):
            lines.append(f'- **{helper_type}**: {count}')

        lines.extend([
            '',
            '## Utility Modules',
            '',
            '| Path | Type | Functions | Classes | Has Endpoints |',
            '|------|------|----------|--------|---------------|',
        ])

        for util in self.utility_modules:
            lines.append(
                f'| {util["path"]} | {util["type"]} | '
                f'{len(util["functions"])} | {len(util["classes"])} | '
                f'{"Yes" if util["has_endpoint_urls"] else "No"} |'
            )

        lines.extend([
            '',
            '## Helper Functions',
            '',
            '| Name | File | Line | Type |',
            '|------|------|------|------|',
        ])

        for helper in self.helper_functions[:50]:  # Limit to first 50
            lines.append(
                f'| {helper["name"]} | {helper["file"]} | '
                f'{helper["line_number"]} | {helper["type"]} |'
            )

        if len(self.helper_functions) > 50:
            lines.append(f'\n... and {len(self.helper_functions) - 50} more helper functions')

        lines.extend([
            '',
            '## Endpoint URLs in Utilities',
            '',
            '| Endpoint | File | Line | Function |',
            '|----------|------|------|---------|',
        ])

        for endpoint in self.endpoint_urls[:50]:  # Limit to first 50
            lines.append(
                f'| {endpoint["endpoint_path"]} | {endpoint["file"]} | '
                f'{endpoint["line_number"]} | {endpoint["function_name"] or "N/A"} |'
            )

        if len(self.endpoint_urls) > 50:
            lines.append(f'\n... and {len(self.endpoint_urls) - 50} more endpoint URLs')

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))

        if self.verbose:
            print(f"Markdown report written to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Audit test utilities and helpers for endpoint URL references',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
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
        default='docs/api-audit/test-utilities-report.json',
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
    auditor = TestUtilitiesAuditor(
        project_root=args.project_root,
        verbose=args.verbose
    )

    # Perform audit
    print("Auditing test utilities and helpers...")
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
    print(f"Total Utility Modules: {summary['total_utility_modules']}")
    print(f"Total Helper Functions: {summary['total_helper_functions']}")
    print(f"Total Endpoint URLs: {summary['total_endpoint_urls']}")
    print(f"Utilities with Endpoint URLs: {summary['utilities_with_endpoint_urls']}")
    print("\nUtilities by Type:")
    for util_type, count in sorted(summary['utilities_by_type'].items()):
        print(f"  {util_type}: {count}")
    print("\nHelpers by Type:")
    for helper_type, count in sorted(summary['helpers_by_type'].items()):
        print(f"  {helper_type}: {count}")
    print("="*60)


if __name__ == '__main__':
    main()

