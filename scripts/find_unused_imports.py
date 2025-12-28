#!/usr/bin/env python3
"""
Script to find unused imports in Python files.
Uses AST analysis to detect imports that are not used in the code.
"""
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ImportVisitor(ast.NodeVisitor):
    """Visitor to collect all imports and their usage."""

    def __init__(self):
        self.imports: Dict[str, Tuple[int, str]] = {}  # name -> (line, full_import)
        self.used_names: Set[str] = set()
        self.import_star: List[int] = []  # lines with "from X import *"

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name.split('.')[0]
            self.imports[name] = (node.lineno, f"import {alias.name}")
            self.used_names.add(name)  # Import statement itself uses the name

    def visit_ImportFrom(self, node):
        if node.module:
            module_name = node.module.split('.')[0]
            if node.names[0].name == '*':
                self.import_star.append(node.lineno)
                return
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                full_import = f"from {node.module} import {alias.name}"
                self.imports[name] = (node.lineno, full_import)
        else:
            # Relative import
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                full_import = f"from . import {alias.name}"
                self.imports[name] = (node.lineno, full_import)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            # For "module.attr", we use the module name
            if isinstance(node.value, ast.Name):
                self.used_names.add(node.value.id)


def analyze_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Analyze a Python file for unused imports."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [(0, str(e), "")]

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return []  # Skip files with syntax errors

    visitor = ImportVisitor()
    visitor.visit(tree)

    unused = []
    for name, (line, full_import) in visitor.imports.items():
        if name not in visitor.used_names and line not in visitor.import_star:
            # Check if it's a type-only import (used in type hints)
            # This is a simplified check - might have false positives
            if name.startswith('_') or name in ['TYPE_CHECKING', 'typing']:
                continue
            unused.append((line, name, full_import))

    return unused


def main():
    """Main function to scan for unused imports."""
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path("hub/apps/contracts")

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    files = []
    if target.is_file():
        files = [target]
    else:
        files = list(target.rglob("*.py"))
        # Exclude migrations and __pycache__
        files = [f for f in files if "migrations" not in str(f) and "__pycache__" not in str(f)]

    total_unused = 0
    files_with_unused = []

    for file_path in sorted(files):
        unused = analyze_file(file_path)
        if unused:
            files_with_unused.append((file_path, unused))
            total_unused += len(unused)

    if files_with_unused:
        print(f"Found {total_unused} unused import(s) in {len(files_with_unused)} file(s):\n")
        cwd = Path.cwd()
        for file_path, unused_list in files_with_unused:
            try:
                rel_path = file_path.relative_to(cwd)
            except ValueError:
                rel_path = file_path
            print(f"{rel_path}:")
            for line, name, full_import in unused_list:
                print(f"  Line {line}: {full_import} (unused: {name})")
            print()
        sys.exit(1)
    else:
        print("No unused imports found.")
        sys.exit(0)


if __name__ == "__main__":
    main()

