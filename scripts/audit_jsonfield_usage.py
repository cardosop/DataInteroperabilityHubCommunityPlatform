#!/usr/bin/env python3
"""
Audit JSONField Usage Across Codebase

This script audits all JSONField usages to identify:
- All JSONField fields in models
- JSONField queries
- JSONField usage patterns
- Optimization opportunities for Django 6
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple
import ast
import json

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def find_python_files(project_root: Path) -> List[Path]:
    """Find all Python files in the project."""
    python_files = []
    
    # Search in hub/apps
    apps_dir = project_root / 'hub' / 'apps'
    if apps_dir.exists():
        for py_file in apps_dir.rglob('*.py'):
            if py_file.name != '__init__.py':
                python_files.append(py_file)
    
    return sorted(python_files)


def find_jsonfield_fields(filepath: Path) -> List[Dict]:
    """Find JSONField field definitions in a Python file."""
    fields = []
    
    try:
        content = filepath.read_text()
        tree = ast.parse(content, filename=str(filepath))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Check if this is a JSONField assignment
                        if isinstance(node.value, ast.Call):
                            if isinstance(node.value.func, ast.Attribute):
                                if node.value.func.attr == 'JSONField':
                                    field_name = target.id
                                    # Extract field arguments
                                    field_info = {
                                        'name': field_name,
                                        'file': str(filepath.relative_to(filepath.parent.parent.parent)),
                                        'line': node.lineno,
                                        'args': {},
                                    }
                                    
                                    # Extract keyword arguments
                                    for kw in node.value.keywords:
                                        if isinstance(kw.value, ast.Constant):
                                            field_info['args'][kw.arg] = kw.value.value
                                        elif isinstance(kw.value, ast.NameConstant):
                                            field_info['args'][kw.arg] = kw.value.value
                                    
                                    fields.append(field_info)
    except Exception as e:
        # Skip files that can't be parsed
        pass
    
    return fields


def find_jsonfield_queries(filepath: Path) -> List[Dict]:
    """Find JSONField queries in a Python file."""
    queries = []
    
    try:
        content = filepath.read_text()
        
        # Look for common JSONField query patterns
        patterns = [
            (r'\.filter\([^)]*__jsonb__', 'JSONB filter'),
            (r'\.filter\([^)]*__json__', 'JSON filter'),
            (r'\.annotate\([^)]*jsonb', 'JSONB annotate'),
            (r'\.annotate\([^)]*json', 'JSON annotate'),
            (r'JSONField', 'JSONField usage'),
            (r'jsonb', 'JSONB usage'),
        ]
        
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, query_type in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    queries.append({
                        'type': query_type,
                        'file': str(filepath.relative_to(filepath.parent.parent.parent)),
                        'line': line_num,
                        'content': line.strip()[:100],  # First 100 chars
                    })
                    break
    except Exception as e:
        pass
    
    return queries


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    
    print_header("JSONField Usage Audit")
    
    # Find all Python files
    python_files = find_python_files(project_root)
    print_success(f"Found {len(python_files)} Python files to analyze")
    
    # Find all JSONField fields
    all_fields = []
    all_queries = []
    
    for py_file in python_files:
        fields = find_jsonfield_fields(py_file)
        queries = find_jsonfield_queries(py_file)
        all_fields.extend(fields)
        all_queries.extend(queries)
    
    # Summary
    print_header("JSONField Fields Found")
    print_success(f"Total JSONField fields: {len(all_fields)}")
    
    # Group by file
    fields_by_file = {}
    for field in all_fields:
        file = field['file']
        if file not in fields_by_file:
            fields_by_file[file] = []
        fields_by_file[file].append(field)
    
    print(f"\n{BOLD}JSONField Fields by File:{RESET}")
    for file, fields in sorted(fields_by_file.items()):
        print(f"  {file}: {len(fields)} fields")
        for field in fields:
            print(f"    - {field['name']} (line {field['line']})")
    
    # Queries
    print_header("JSONField Queries Found")
    print_success(f"Total JSONField queries: {len(all_queries)}")
    
    # Group by type
    queries_by_type = {}
    for query in all_queries:
        qtype = query['type']
        if qtype not in queries_by_type:
            queries_by_type[qtype] = []
        queries_by_type[qtype].append(query)
    
    print(f"\n{BOLD}JSONField Queries by Type:{RESET}")
    for qtype, queries in sorted(queries_by_type.items()):
        print(f"  {qtype}: {len(queries)} queries")
    
    # Generate report
    report = {
        'summary': {
            'total_fields': len(all_fields),
            'total_queries': len(all_queries),
            'files_with_fields': len(fields_by_file),
        },
        'fields': all_fields,
        'queries': all_queries,
    }
    
    report_path = project_root / 'openspec' / 'changes' / 'fullcontract' / 'JSONFIELD_AUDIT_REPORT.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print_success(f"Report saved to: {report_path}")
    
    # Django 6 optimization notes
    print_header("Django 6 JSONField Optimization Notes")
    print_success("Django 6 includes enhanced JSONField support:")
    print("  - Improved query performance")
    print("  - Better JSONB index support")
    print("  - Enhanced JSON path queries")
    print("  - Optimized JSON serialization")
    
    print(f"\n{BOLD}Recommendations:{RESET}")
    print("  1. Review all JSONField queries for optimization opportunities")
    print("  2. Add JSONB GIN indexes for frequently queried JSONField fields")
    print("  3. Use Django 6's enhanced JSON path query syntax")
    print("  4. Consider JSONField validators for data integrity")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

