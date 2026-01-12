#!/usr/bin/env python
"""
Comprehensive script to analyze Django URL reverse lookups.

This script:
1. Searches for all reverse() calls in Python code
2. Searches for {% url %} template tags in HTML/template files
3. Maps reverse lookups to URL patterns in urls.py files
4. Identifies reverse lookup dependencies
5. Generates a comprehensive report

Usage:
    python scripts/analyze_reverse_lookups.py
"""
import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import sys


class ReverseLookupAnalyzer:
    """Analyzer for Django reverse lookups"""

    def __init__(self, base_path: str = "hub"):
        self.base_path = Path(base_path)
        self.reverse_calls: List[Dict] = []
        self.template_url_tags: List[Dict] = []
        self.url_patterns: Dict[str, Dict] = {}
        self.reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)

    def find_reverse_calls(self) -> List[Dict]:
        """Find all reverse() calls in Python files"""
        reverse_calls = []

        for py_file in self.base_path.rglob("*.py"):
            if "migrations" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.split("\n")

                # Parse AST to find reverse() calls
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == "reverse":
                                # Found reverse() call
                                reverse_call = self._extract_reverse_call(node, py_file, lines)
                                if reverse_call:
                                    reverse_calls.append(reverse_call)
                            elif isinstance(node.func, ast.Attribute) and node.func.attr == "reverse":
                                # Found reverse() call via import (e.g., django.urls.reverse)
                                reverse_call = self._extract_reverse_call(node, py_file, lines)
                                if reverse_call:
                                    reverse_calls.append(reverse_call)
                except SyntaxError:
                    # Skip files with syntax errors
                    continue

                # Also use regex to catch dynamic reverse calls
                for line_num, line in enumerate(lines, 1):
                    # Match reverse('name') or reverse("name")
                    matches = re.finditer(r'reverse\s*\(\s*["\']([^"\']+)["\']', line)
                    for match in matches:
                        url_name = match.group(1)
                        reverse_calls.append({
                            "type": "reverse_call",
                            "url_name": url_name,
                            "file": str(py_file.relative_to(self.base_path)),
                            "line": line_num,
                            "code": line.strip(),
                            "kwargs": self._extract_kwargs_from_line(line),
                        })

            except Exception as e:
                print(f"Error processing {py_file}: {e}", file=sys.stderr)
                continue

        self.reverse_calls = reverse_calls
        return reverse_calls

    def _extract_reverse_call(self, node: ast.Call, file_path: Path, lines: List[str]) -> Optional[Dict]:
        """Extract reverse call information from AST node"""
        if not node.args:
            return None

        # Get URL name (first argument)
        url_name = None
        if isinstance(node.args[0], ast.Constant):
            url_name = node.args[0].value
        elif hasattr(ast, 'Str') and isinstance(node.args[0], ast.Str):  # Python < 3.8
            url_name = node.args[0].s
        elif isinstance(node.args[0], ast.JoinedStr):  # f-strings
            # Try to extract string parts
            parts = []
            for value in node.args[0].values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif hasattr(ast, 'Str') and isinstance(value, ast.Str):
                    parts.append(value.s)
            if parts:
                url_name = ''.join(parts)

        if not url_name:
            return None

        # Get kwargs (second argument or keyword arguments)
        kwargs = {}

        # Check keyword arguments first (most common: kwargs={'key': 'value'})
        for keyword in node.keywords:
            if keyword.arg == "kwargs":
                if isinstance(keyword.value, ast.Dict):
                    for key_node, value_node in zip(keyword.value.keys, keyword.value.values):
                        if isinstance(key_node, ast.Constant):
                            key = key_node.value
                        elif hasattr(ast, 'Str') and isinstance(key_node, ast.Str):
                            key = key_node.s
                        else:
                            continue
                        # Extract value - handle both constants and expressions
                        if isinstance(value_node, ast.Constant):
                            value = value_node.value
                        elif hasattr(ast, 'Str') and isinstance(value_node, ast.Str):
                            value = value_node.s
                        elif isinstance(value_node, ast.Call):
                            # Handle function calls like str(self.domain1.id)
                            # Convert to string representation for analysis
                            if isinstance(value_node.func, ast.Name) and value_node.func.id == "str":
                                if value_node.args and isinstance(value_node.args[0], ast.Attribute):
                                    # str(self.domain1.id) -> 'str(self.domain1.id)'
                                    attr = value_node.args[0]
                                    if isinstance(attr.value, ast.Attribute):
                                        value = f"str({attr.value.attr}.{attr.attr})"
                                    elif isinstance(attr.value, ast.Name):
                                        value = f"str({attr.value.id}.{attr.attr})"
                                    else:
                                        value = "str(...)"
                                else:
                                    value = "str(...)"
                            else:
                                value = f"{value_node.func.id if isinstance(value_node.func, ast.Name) else '...'}(...)"
                        elif isinstance(value_node, ast.Attribute):
                            # Handle attribute access like self.domain1.id
                            if isinstance(value_node.value, ast.Attribute):
                                value = f"{value_node.value.attr}.{value_node.attr}"
                            elif isinstance(value_node.value, ast.Name):
                                value = f"{value_node.value.id}.{value_node.attr}"
                            else:
                                value = "..."
                        else:
                            # For other expressions, use string representation from source
                            continue
                        kwargs[key] = value

        # Also check if second argument is a dict (less common: reverse('name', {'key': 'value'}))
        if len(node.args) > 1 and isinstance(node.args[1], ast.Dict) and not kwargs:
            # Extract kwargs from dict
            for key_node, value_node in zip(node.args[1].keys, node.args[1].values):
                if isinstance(key_node, ast.Constant):
                    key = key_node.value
                elif hasattr(ast, 'Str') and isinstance(key_node, ast.Str):
                    key = key_node.s
                else:
                    continue
                if isinstance(value_node, ast.Constant):
                    value = value_node.value
                elif hasattr(ast, 'Str') and isinstance(value_node, ast.Str):
                    value = value_node.s
                else:
                    continue
                kwargs[key] = value

        line_num = node.lineno
        return {
            "type": "reverse_call",
            "url_name": url_name,
            "file": str(file_path.relative_to(self.base_path)),
            "line": line_num,
            "code": lines[line_num - 1].strip() if line_num <= len(lines) else "",
            "kwargs": kwargs,
        }

    def _extract_kwargs_from_line(self, line: str) -> Dict[str, str]:
        """Extract kwargs from reverse() call line"""
        kwargs = {}
        # Match kwargs={'key': 'value'} or kwargs={"key": "value"}
        kwargs_match = re.search(r'kwargs\s*=\s*\{([^}]+)\}', line)
        if kwargs_match:
            kwargs_str = kwargs_match.group(1)
            # Extract key-value pairs
            pairs = re.findall(r"['\"](\w+)['\"]\s*:\s*['\"]?([^,'\"]+)['\"]?", kwargs_str)
            for key, value in pairs:
                kwargs[key] = value.strip()
        return kwargs

    def find_template_url_tags(self) -> List[Dict]:
        """Find all {% url %} template tags in HTML/template files"""
        template_tags = []

        # Search in templates directories
        template_dirs = [
            self.base_path / "templates",
            self.base_path / "apps" / "**" / "templates",
        ]

        for template_dir_pattern in template_dirs:
            for template_file in self.base_path.rglob("*.html"):
                if "migrations" in str(template_file) or "__pycache__" in str(template_file):
                    continue

                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        lines = content.split("\n")

                    # Match {% url 'name' %} or {% url 'name' arg1 arg2 %}
                    pattern = r'{%\s*url\s+["\']([^"\']+)["\']'
                    for line_num, line in enumerate(lines, 1):
                        matches = re.finditer(pattern, line)
                        for match in matches:
                            url_name = match.group(1)
                            # Extract arguments
                            args_match = re.search(r'{%\s*url\s+["\'][^"\']+["\']\s+([^%]+)%}', line)
                            args = []
                            if args_match:
                                args_str = args_match.group(1).strip()
                                args = [arg.strip() for arg in args_str.split() if arg.strip()]

                            template_tags.append({
                                "type": "template_url_tag",
                                "url_name": url_name,
                                "file": str(template_file.relative_to(self.base_path)),
                                "line": line_num,
                                "code": line.strip(),
                                "args": args,
                            })

                except Exception as e:
                    print(f"Error processing {template_file}: {e}", file=sys.stderr)
                    continue

        self.template_url_tags = template_tags
        return template_tags

    def find_url_patterns(self) -> Dict[str, Dict]:
        """Find all URL patterns in urls.py files"""
        url_patterns = {}

        for urls_file in self.base_path.rglob("urls.py"):
            if "migrations" in str(urls_file) or "__pycache__" in str(urls_file):
                continue

            try:
                with open(urls_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse URL patterns
                patterns = self._parse_url_patterns(content, urls_file)
                for pattern in patterns:
                    if pattern.get("name"):
                        url_patterns[pattern["name"]] = {
                            **pattern,
                            "urls_file": str(urls_file.relative_to(self.base_path)),
                        }

            except Exception as e:
                print(f"Error processing {urls_file}: {e}", file=sys.stderr)
                continue

        self.url_patterns = url_patterns
        return url_patterns

    def _parse_url_patterns(self, content: str, file_path: Path) -> List[Dict]:
        """Parse URL patterns from urls.py content"""
        patterns = []

        # Match path('pattern', view, name='name')
        path_pattern = re.compile(
            r'path\s*\(\s*["\']([^"\']+)["\']\s*,\s*[^,]+,\s*name\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in path_pattern.finditer(content):
            patterns.append({
                "pattern": match.group(1),
                "name": match.group(2),
                "type": "path",
            })

        # Match re_path('pattern', view, name='name')
        re_path_pattern = re.compile(
            r're_path\s*\(\s*["\']([^"\']+)["\']\s*,\s*[^,]+,\s*name\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in re_path_pattern.finditer(content):
            patterns.append({
                "pattern": match.group(1),
                "name": match.group(2),
                "type": "re_path",
            })

        # Also parse custom actions from views.py files
        # Find corresponding views.py file (could be in same directory or parent)
        views_files = [
            file_path.parent / "views.py",
            file_path.parent.parent / "views.py",  # Sometimes views.py is one level up
        ]
        for views_file in views_files:
            if views_file.exists():
                try:
                    with open(views_file, "r", encoding="utf-8") as f:
                        views_content = f.read()
                    custom_actions = self._parse_custom_viewset_actions(views_content, file_path)
                    patterns.extend(custom_actions)
                    break  # Only parse once
                except Exception as e:
                    continue

        # Match router.register() calls (DRF routers)
        # Pattern 1: router.register(r'prefix', ViewSet, basename='basename')
        router_pattern1 = re.compile(
            r'router\.register\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*\w+ViewSet\s*,\s*basename\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        # Pattern 2: router.register(r'prefix', ViewSet, basename="basename")
        router_pattern2 = re.compile(
            r'router\.register\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*\w+ViewSet\s*,\s*basename\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        # Pattern 3: router.register('prefix', ViewSet, basename='basename')
        router_pattern3 = re.compile(
            r'router\.register\s*\(\s*["\']([^"\']+)["\']\s*,\s*\w+ViewSet\s*,\s*basename\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )

        for pattern in [router_pattern1, router_pattern2, router_pattern3]:
            for match in pattern.finditer(content):
                basename = match.group(2)
                prefix = match.group(1)
                # DRF routers create multiple URLs with suffixes
                # Standard actions: list, detail, create, update, partial_update, destroy
                for action in ["list", "detail"]:
                    patterns.append({
                        "pattern": f"{prefix}/" if prefix else "",
                        "name": f"{basename}-{action}",
                        "type": "router",
                        "basename": basename,
                        "action": action,
                    })

        # Also check for custom router names (runs_router, etc.)
        custom_router_pattern = re.compile(
            r'(\w+router)\.register\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*\w+ViewSet\s*,\s*basename\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in custom_router_pattern.finditer(content):
            basename = match.group(3)
            prefix = match.group(2)
            for action in ["list", "detail"]:
                patterns.append({
                    "pattern": f"{prefix}/" if prefix else "",
                    "name": f"{basename}-{action}",
                    "type": "router",
                    "basename": basename,
                    "action": action,
                })

        return patterns

    def _parse_custom_viewset_actions(self, content: str, urls_file: Path) -> List[Dict]:
        """Parse custom viewset actions from views.py to generate URL names"""
        patterns = []

        # Find router.register() calls in corresponding urls.py to get basenames
        urls_content = ""
        try:
            with open(urls_file, "r", encoding="utf-8") as f:
                urls_content = f.read()
        except Exception:
            return patterns

        # Extract basenames from router.register() calls
        basenames = {}
        router_pattern = re.compile(
            r'router\.register\s*\(\s*r?["\']([^"\']+)["\']\s*,\s*(\w+ViewSet)\s*,\s*basename\s*=\s*["\']([^"\']+)["\']',
            re.MULTILINE
        )
        for match in router_pattern.finditer(urls_content):
            viewset_name = match.group(2)
            basename = match.group(3)
            basenames[viewset_name] = basename

        # Find @action decorators and their methods
        # Pattern: @action(...) followed by def method_name(...)
        # Need to handle multi-line decorators and find the method definition
        # Use a more sophisticated approach to handle nested parentheses
        action_decorator_pattern = re.compile(
            r'@action\s*\(',
            re.MULTILINE
        )

        for match in action_decorator_pattern.finditer(content):
            decorator_start = match.start()
            # Find matching closing parenthesis
            paren_count = 1
            pos = match.end()
            decorator_end = pos
            while pos < len(content) and paren_count > 0:
                if content[pos] == '(':
                    paren_count += 1
                elif content[pos] == ')':
                    paren_count -= 1
                pos += 1
            if paren_count == 0:
                decorator_end = pos - 1
                decorator_content = content[match.end():decorator_end]
            else:
                continue  # Unmatched parentheses, skip

            # Find the method name after this decorator (skip any intermediate decorators)
            # Look for def method_name( within next 500 characters after decorator ends
            method_match = re.search(r'def\s+(\w+)\s*\(', content[decorator_end+1:decorator_end+501])
            if not method_match:
                continue

            method_name = method_match.group(1)

            # Extract url_path, url_name, and detail from decorator
            url_path_match = re.search(r'url_path\s*=\s*["\']([^"\']+)["\']', decorator_content)
            url_name_match = re.search(r'url_name\s*=\s*["\']([^"\']+)["\']', decorator_content)
            detail_match = re.search(r'detail\s*=\s*(True|False)', decorator_content)

            url_path = url_path_match.group(1) if url_path_match else method_name.replace('_', '-')
            is_detail = detail_match.group(1) == "True" if detail_match else True

            # Find which ViewSet this method belongs to
            # Look backwards for class definition (find the most recent class before this decorator)
            class_matches = list(re.finditer(r'class\s+(\w+ViewSet)', content[:decorator_start]))
            if not class_matches:
                continue

            # Get the last (most recent) class match
            class_match = class_matches[-1]
            viewset_name = class_match.group(1)

            if viewset_name in basenames:
                basename = basenames[viewset_name]
                # Use custom url_name if provided, otherwise generate from method name
                if url_name_match:
                    custom_url_name = url_name_match.group(1)
                    # If url_name is provided, DRF uses it directly (not prefixed with basename)
                    # But in practice, DRF still prefixes with basename, so we need to check both
                    url_name_options = [
                        f"{basename}-{custom_url_name}",  # Most common: basename-url_name
                        custom_url_name,  # Sometimes just the url_name itself
                    ]
                else:
                    # DRF generates URL name as: {basename}-{method_name}
                    # Convert method_name from snake_case to kebab-case
                    method_kebab = method_name.replace('_', '-')
                    url_name_options = [f"{basename}-{method_kebab}"]

                # Add all possible URL name variations
                for url_name in url_name_options:
                    # Only add if url_name is valid (not empty or just a dash)
                    if url_name and url_name.strip() and url_name != "-":
                        patterns.append({
                            "pattern": url_path,
                            "name": url_name,
                            "type": "custom_action",
                            "basename": basename,
                            "method": method_name,
                            "detail": is_detail,
                        })

        return patterns

    def map_reverse_to_patterns(self) -> Dict[str, List[Dict]]:
        """Map reverse lookups to URL patterns"""
        mapping = defaultdict(list)

        # Map reverse calls
        for reverse_call in self.reverse_calls:
            url_name = reverse_call["url_name"]
            if url_name in self.url_patterns:
                mapping[url_name].append({
                    "type": "reverse_call",
                    "source": reverse_call,
                    "pattern": self.url_patterns[url_name],
                })
            else:
                mapping[url_name].append({
                    "type": "reverse_call",
                    "source": reverse_call,
                    "pattern": None,  # Pattern not found
                })

        # Map template tags
        for template_tag in self.template_url_tags:
            url_name = template_tag["url_name"]
            if url_name in self.url_patterns:
                mapping[url_name].append({
                    "type": "template_url_tag",
                    "source": template_tag,
                    "pattern": self.url_patterns[url_name],
                })
            else:
                mapping[url_name].append({
                    "type": "template_url_tag",
                    "source": template_tag,
                    "pattern": None,  # Pattern not found
                })

        return dict(mapping)

    def identify_dependencies(self) -> Dict[str, Set[str]]:
        """Identify dependencies between reverse lookups"""
        dependencies = defaultdict(set)

        # Analyze reverse calls to find dependencies
        for reverse_call in self.reverse_calls:
            url_name = reverse_call["url_name"]
            file_path = reverse_call["file"]

            # Find other reverse calls in the same file
            for other_call in self.reverse_calls:
                if other_call["file"] == file_path and other_call["url_name"] != url_name:
                    dependencies[url_name].add(other_call["url_name"])

        self.reverse_dependencies = dependencies
        return dependencies

    def generate_report(self) -> Dict:
        """Generate comprehensive report"""
        mapping = self.map_reverse_to_patterns()
        dependencies = self.identify_dependencies()

        # Find unmapped reverse lookups
        unmapped = []
        for url_name, mappings in mapping.items():
            if any(m["pattern"] is None for m in mappings):
                unmapped.append({
                    "url_name": url_name,
                    "sources": [m["source"] for m in mappings],
                })

        return {
            "summary": {
                "total_reverse_calls": len(self.reverse_calls),
                "total_template_tags": len(self.template_url_tags),
                "total_url_patterns": len(self.url_patterns),
                "mapped_lookups": len([m for m in mapping.values() if any(p["pattern"] is not None for p in m)]),
                "unmapped_lookups": len(unmapped),
                "dependencies": len(dependencies),
            },
            "reverse_calls": self.reverse_calls,
            "template_tags": self.template_url_tags,
            "url_patterns": self.url_patterns,
            "mapping": mapping,
            "unmapped": unmapped,
            "dependencies": {k: list(v) for k, v in dependencies.items()},
        }

    def run(self) -> Dict:
        """Run complete analysis"""
        print("Searching for reverse() calls...")
        self.find_reverse_calls()
        print(f"Found {len(self.reverse_calls)} reverse() calls")

        print("Searching for {% url %} template tags...")
        self.find_template_url_tags()
        print(f"Found {len(self.template_url_tags)} template URL tags")

        print("Finding URL patterns...")
        self.find_url_patterns()
        print(f"Found {len(self.url_patterns)} URL patterns")

        print("Mapping reverse lookups to patterns...")
        mapping = self.map_reverse_to_patterns()

        print("Identifying dependencies...")
        dependencies = self.identify_dependencies()

        print("Generating report...")
        report = self.generate_report()

        return report


def main():
    """Main entry point"""
    analyzer = ReverseLookupAnalyzer(base_path="hub")
    report = analyzer.run()

    # Save report to JSON
    output_file = "reverse_lookup_analysis.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nAnalysis complete! Report saved to {output_file}")
    print(f"\nSummary:")
    print(f"  Reverse calls: {report['summary']['total_reverse_calls']}")
    print(f"  Template tags: {report['summary']['total_template_tags']}")
    print(f"  URL patterns: {report['summary']['total_url_patterns']}")
    print(f"  Mapped lookups: {report['summary']['mapped_lookups']}")
    print(f"  Unmapped lookups: {report['summary']['unmapped_lookups']}")

    if report['summary']['unmapped_lookups'] > 0:
        print(f"\n⚠️  Warning: {report['summary']['unmapped_lookups']} reverse lookups could not be mapped to URL patterns")
        print("Unmapped lookups:")
        for unmapped in report['unmapped'][:10]:  # Show first 10
            print(f"  - {unmapped['url_name']} (used in {len(unmapped['sources'])} places)")


if __name__ == "__main__":
    main()

