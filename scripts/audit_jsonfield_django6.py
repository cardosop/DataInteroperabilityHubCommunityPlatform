#!/usr/bin/env python3
"""
Audit JSONField usages for Django 6 compatibility.

This script audits all JSONField declarations in the codebase to:
1. Identify all JSONField usages
2. Check for Django 6 compatibility
3. Identify optimization opportunities
4. Generate a comprehensive report
"""
import os
import re
import ast
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Django 6 JSONField improvements to check for:
# - Better performance with native JSONB operations
# - Improved query syntax
# - Better type hints
# - Support for JSONField(db_index=True) for GIN indexes


class JSONFieldAuditor(ast.NodeVisitor):
    """AST visitor to find JSONField usages."""
    
    def __init__(self):
        self.jsonfields = []
        self.current_file = None
        self.current_class = None
        
    def visit_ClassDef(self, node):
        """Track current class name."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_Assign(self, node):
        """Find JSONField field assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                field_name = target.id
                # Check if assignment is a JSONField
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == 'JSONField':
                            self.jsonfields.append({
                                'file': self.current_file,
                                'class': self.current_class,
                                'field': field_name,
                                'line': node.lineno,
                                'args': len(node.value.args),
                                'keywords': {kw.arg: kw.value for kw in node.value.keywords if kw.arg},
                            })
        self.generic_visit(node)


def find_jsonfield_files(root_dir: str) -> List[Path]:
    """Find all Python files that might contain JSONField."""
    root = Path(root_dir)
    files = []
    
    # Find all models.py files
    for models_file in root.rglob('models.py'):
        if 'migrations' not in str(models_file):
            files.append(models_file)
    
    # Find all files that import JSONField
    for py_file in root.rglob('*.py'):
        if 'migrations' in str(py_file) or '__pycache__' in str(py_file):
            continue
        try:
            content = py_file.read_text()
            if 'JSONField' in content:
                if py_file not in files:
                    files.append(py_file)
        except Exception:
            pass
    
    return files


def audit_jsonfield_usage(file_path: Path) -> List[Dict]:
    """Audit a single file for JSONField usages."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
        
        auditor = JSONFieldAuditor()
        auditor.current_file = str(file_path)
        auditor.visit(tree)
        
        return auditor.jsonfields
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
        return []


def check_django6_optimizations(jsonfield: Dict) -> List[str]:
    """Check for Django 6 optimization opportunities."""
    issues = []
    recommendations = []
    
    keywords = jsonfield.get('keywords', {})
    
    # Check for db_index (Django 6 supports GIN indexes on JSONField)
    if 'db_index' not in keywords:
        recommendations.append("Consider adding db_index=True for GIN index support (Django 6)")
    
    # Check for encoder/decoder (Django 6 has better defaults)
    if 'encoder' in keywords or 'decoder' in keywords:
        recommendations.append("Review encoder/decoder usage - Django 6 has improved defaults")
    
    # Check for default (Django 6 handles None defaults better)
    if 'default' in keywords:
        default_val = keywords['default']
        if isinstance(default_val, ast.Constant) and default_val.value is None:
            recommendations.append("Consider using default=dict for mutable defaults (Django 6 best practice)")
    
    return recommendations


def generate_report(all_jsonfields: List[Dict], output_file: str = None):
    """Generate comprehensive audit report."""
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("JSONField Django 6 Compatibility Audit Report")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Summary
    report_lines.append(f"Total JSONField declarations found: {len(all_jsonfields)}")
    report_lines.append("")
    
    # Group by file
    by_file = defaultdict(list)
    for jf in all_jsonfields:
        by_file[jf['file']].append(jf)
    
    report_lines.append("=" * 80)
    report_lines.append("JSONField Declarations by File")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for file_path, fields in sorted(by_file.items()):
        report_lines.append(f"\nFile: {file_path}")
        report_lines.append(f"  Total JSONFields: {len(fields)}")
        for field in fields:
            report_lines.append(f"    - {field['class']}.{field['field']} (line {field['line']})")
            recommendations = check_django6_optimizations(field)
            if recommendations:
                for rec in recommendations:
                    report_lines.append(f"      → {rec}")
    
    # Statistics
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("Statistics")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    total_files = len(by_file)
    total_fields = len(all_jsonfields)
    
    report_lines.append(f"Files with JSONField: {total_files}")
    report_lines.append(f"Total JSONField declarations: {total_fields}")
    
    # Django 6 recommendations
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("Django 6 Optimization Recommendations")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append("1. Consider adding db_index=True for frequently queried JSONFields")
    report_lines.append("2. Review default values - use callable defaults for mutable types")
    report_lines.append("3. Use JSONField(db_index=True) for GIN indexes on PostgreSQL")
    report_lines.append("4. Leverage Django 6's improved JSONField query syntax")
    report_lines.append("5. Review encoder/decoder usage - Django 6 has better defaults")
    
    report_text = "\n".join(report_lines)
    
    if output_file:
        Path(output_file).write_text(report_text)
        print(f"Report written to: {output_file}")
    else:
        print(report_text)
    
    return report_text


def main():
    """Main audit function."""
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = "hub"
    
    if not os.path.exists(root_dir):
        print(f"Error: Directory not found: {root_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Auditing JSONField usages in: {root_dir}")
    print("This may take a few moments...")
    print()
    
    files = find_jsonfield_files(root_dir)
    print(f"Found {len(files)} files to audit")
    
    all_jsonfields = []
    for file_path in files:
        jsonfields = audit_jsonfield_usage(file_path)
        all_jsonfields.extend(jsonfields)
    
    output_file = "JSONFIELD_DJANGO6_AUDIT_REPORT.md"
    generate_report(all_jsonfields, output_file)
    
    print(f"\nAudit complete! Found {len(all_jsonfields)} JSONField declarations.")
    print(f"Report saved to: {output_file}")


if __name__ == "__main__":
    main()

