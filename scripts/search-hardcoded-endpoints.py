#!/usr/bin/env python3
"""
Search codebase for hardcoded endpoint URLs

This script searches for hardcoded API endpoint URLs across the codebase
and generates an impact matrix with categorization by priority.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class EndpointReference:
    """Represents a found endpoint URL reference"""

    file_path: str
    line_number: int
    line_content: str
    endpoint_url: str
    context: str
    category: str  # 'test', 'cli', 'frontend', 'docs', 'workflow', 'service_client', 'other'
    priority: str  # 'Critical', 'High', 'Medium', 'Low'
    is_in_comment: bool
    is_in_string: bool
    is_deprecated: bool


class EndpointURLSearcher:
    """Searches for hardcoded endpoint URLs in codebase"""

    # Patterns to match endpoint URLs
    ENDPOINT_PATTERNS = [
        # Full URLs with /api/v1/
        r'https?://[^\s\'"`]+/api/v1/[^\s\'"`]*',
        # Relative paths /api/v1/
        r'/api/v1/[^\s\'"`\)]+',
        # Base URL patterns
        r"api\.example\.com/api/v1",
        r"localhost:\d+/api/v1",
        r"127\.0\.0\.1:\d+/api/v1",
        # Common endpoint patterns
        r'["\']/api/v1/[^"\']+["\']',
        r"`/api/v1/[^`]+`",
    ]

    # Patterns that indicate comments
    COMMENT_PATTERNS = {
        "python": r"^\s*#",
        "javascript": r"^\s*//",
        "typescript": r"^\s*//",
        "markdown": r"^\s*#",
        "yaml": r"^\s*#",
        "json": None,  # JSON doesn't have comments
    }

    # Patterns that indicate deprecated code
    DEPRECATED_PATTERNS = [
        r"deprecated",
        r"DEPRECATED",
        r"TODO.*remove",
        r"FIXME.*remove",
        r"legacy",
        r"LEGACY",
    ]

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.references: list[EndpointReference] = []
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.ENDPOINT_PATTERNS
        ]

    def get_file_type(self, file_path: Path) -> str:
        """Determine file type from extension"""
        ext = file_path.suffix.lower()
        type_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".sh": "shell",
            ".bash": "shell",
        }
        return type_map.get(ext, "other")

    def is_comment_line(self, line: str, file_type: str) -> bool:
        """Check if line is a comment"""
        pattern = self.COMMENT_PATTERNS.get(file_type)
        if pattern is None:
            return False
        return bool(re.match(pattern, line))

    def is_deprecated_context(self, file_path: Path, line_number: int, lines: list[str]) -> bool:
        """Check if context suggests deprecated code"""
        # Check current line
        line = lines[line_number - 1]
        for pattern in self.DEPRECATED_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        # Check file path
        path_str = str(file_path)
        if "deprecated" in path_str.lower() or "legacy" in path_str.lower():
            return True

        # Check surrounding lines (5 lines before)
        start = max(0, line_number - 6)
        context = "\n".join(lines[start:line_number])
        for pattern in self.DEPRECATED_PATTERNS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def is_in_string(self, line: str, match_start: int, match_end: int) -> bool:
        """Check if match is inside a string literal"""
        # Simple heuristic: check if match is between quotes
        before = line[:match_start]
        after = line[match_end:]

        # Count unescaped quotes before match
        single_quotes_before = len(re.findall(r"(?<!\\)'", before))
        double_quotes_before = len(re.findall(r'(?<!\\)"', before))
        backticks_before = len(re.findall(r"(?<!\\)`", before))

        # Count unescaped quotes after match
        single_quotes_after = len(re.findall(r"(?<!\\)'", after))
        double_quotes_after = len(re.findall(r'(?<!\\)"', after))
        backticks_after = len(re.findall(r"(?<!\\)`", after))

        # If odd number of quotes before and after, likely in string
        in_single = (single_quotes_before % 2 == 1) and (single_quotes_after % 2 == 1)
        in_double = (double_quotes_before % 2 == 1) and (double_quotes_after % 2 == 1)
        in_backtick = (backticks_before % 2 == 1) and (backticks_after % 2 == 1)

        return in_single or in_double or in_backtick

    def determine_category(self, file_path: Path) -> str:
        """Determine category based on file path"""
        path_str = str(file_path)

        if "test" in path_str.lower() or "tests/" in path_str:
            return "test"
        elif "cli/" in path_str or "cli\\" in path_str:
            return "cli"
        elif "frontend/" in path_str or "frontend\\" in path_str:
            return "frontend"
        elif "docs/" in path_str or "docs\\" in path_str:
            return "docs"
        elif "workflow" in path_str.lower():
            return "workflow"
        elif "client" in path_str.lower() or "api_client" in path_str.lower():
            return "service_client"
        else:
            return "other"

    def determine_priority(self, ref: EndpointReference) -> str:
        """Determine priority based on context"""
        # Critical: Production code, core services, not in tests/docs
        if ref.category == "service_client" and not ref.is_in_comment:
            return "Critical"
        if ref.category == "workflow" and not ref.is_in_comment:
            return "Critical"
        if ref.category == "other" and not ref.is_in_comment and not ref.is_deprecated:
            return "Critical"

        # High: Test files, CLI code
        if ref.category == "test" and not ref.is_in_comment:
            return "High"
        if ref.category == "cli" and not ref.is_in_comment:
            return "High"

        # Medium: Documentation, examples
        if ref.category == "docs":
            return "Medium"
        if ref.is_in_comment and ref.category != "test":
            return "Medium"

        # Low: Comments in test files, deprecated code
        if ref.is_deprecated:
            return "Low"
        if ref.is_in_comment and ref.category == "test":
            return "Low"

        return "Medium"

    def extract_endpoint_url(self, match_text: str) -> str:
        """Extract clean endpoint URL from match"""
        # Remove quotes
        cleaned = match_text.strip("'\"`")
        # Extract /api/v1/... part
        api_match = re.search(r'/api/v1/[^\s\'"`\)]*', cleaned)
        if api_match:
            return api_match.group(0)
        return cleaned

    def search_file(self, file_path: Path) -> list[EndpointReference]:
        """Search a single file for endpoint URLs"""
        references = []

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return references

        file_type = self.get_file_type(file_path)
        category = self.determine_category(file_path)

        for line_num, line in enumerate(lines, 1):
            for pattern in self.compiled_patterns:
                for match in pattern.finditer(line):
                    match_start = match.start()
                    match_end = match.end()
                    match_text = match.group(0)

                    # Skip if in comment
                    is_comment = self.is_comment_line(line, file_type)

                    # Check if in string
                    is_string = self.is_in_string(line, match_start, match_end)

                    # Check if deprecated
                    is_deprecated = self.is_deprecated_context(file_path, line_num, lines)

                    # Extract endpoint URL
                    endpoint_url = self.extract_endpoint_url(match_text)

                    # Get context (3 lines before and after)
                    context_start = max(0, line_num - 4)
                    context_end = min(len(lines), line_num + 3)
                    context_lines = lines[context_start:context_end]
                    context = "".join(context_lines)

                    ref = EndpointReference(
                        file_path=str(file_path.relative_to(self.base_dir)),
                        line_number=line_num,
                        line_content=line.rstrip(),
                        endpoint_url=endpoint_url,
                        context=context,
                        category=category,
                        priority="",  # Will be set later
                        is_in_comment=is_comment,
                        is_in_string=is_string,
                        is_deprecated=is_deprecated,
                    )

                    # Set priority
                    ref.priority = self.determine_priority(ref)

                    references.append(ref)

        return references

    def search_directory(
        self,
        directory: Path,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[EndpointReference]:
        """Search directory recursively for endpoint URLs"""
        if include_patterns is None:
            include_patterns = [
                "*.py",
                "*.js",
                "*.ts",
                "*.jsx",
                "*.tsx",
                "*.md",
                "*.yaml",
                "*.yml",
                "*.json",
                "*.sh",
            ]

        if exclude_patterns is None:
            exclude_patterns = [
                "**/node_modules/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/.git/**",
                "**/htmlcov/**",
                "**/coverage/**",
                "**/build/**",
                "**/dist/**",
                "**/*.egg-info/**",
            ]

        references = []

        for pattern in include_patterns:
            for file_path in directory.rglob(pattern):
                # Check if excluded
                excluded = False
                for exclude_pattern in exclude_patterns:
                    if file_path.match(exclude_pattern) or exclude_pattern.replace(
                        "**/", ""
                    ) in str(file_path):
                        excluded = True
                        break

                if excluded:
                    continue

                # Search file
                file_refs = self.search_file(file_path)
                references.extend(file_refs)

        return references

    def search_specific_directories(self, directories: list[str]) -> list[EndpointReference]:
        """Search specific directories"""
        all_references = []

        for dir_path in directories:
            dir_path_obj = self.base_dir / dir_path
            if not dir_path_obj.exists():
                print(f"Warning: Directory not found: {dir_path}", file=sys.stderr)
                continue

            print(f"Searching {dir_path}...", file=sys.stderr)
            refs = self.search_directory(dir_path_obj)
            all_references.extend(refs)
            print(f"  Found {len(refs)} references", file=sys.stderr)

        return all_references


class ImpactMatrixGenerator:
    """Generates impact matrix from endpoint references"""

    def __init__(self, references: list[EndpointReference]):
        self.references = references

    def generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics"""
        total = len(self.references)

        by_priority = defaultdict(int)
        by_category = defaultdict(int)
        by_file = defaultdict(int)

        for ref in self.references:
            by_priority[ref.priority] += 1
            by_category[ref.category] += 1
            by_file[ref.file_path] += 1

        return {
            "total_references": total,
            "by_priority": dict(by_priority),
            "by_category": dict(by_category),
            "unique_files": len(by_file),
            "unique_endpoints": len(set(ref.endpoint_url for ref in self.references)),
        }

    def generate_matrix(self) -> list[dict[str, Any]]:
        """Generate impact matrix"""
        matrix = []

        # Group by file
        by_file = defaultdict(list)
        for ref in self.references:
            by_file[ref.file_path].append(ref)

        for file_path, refs in sorted(by_file.items()):
            # Count by priority
            priority_counts = defaultdict(int)
            for ref in refs:
                priority_counts[ref.priority] += 1

            matrix.append(
                {
                    "file_path": file_path,
                    "total_references": len(refs),
                    "priority_breakdown": dict(priority_counts),
                    "categories": list(set(ref.category for ref in refs)),
                    "references": [
                        {
                            "line_number": ref.line_number,
                            "endpoint_url": ref.endpoint_url,
                            "priority": ref.priority,
                            "category": ref.category,
                            "is_in_comment": ref.is_in_comment,
                            "is_deprecated": ref.is_deprecated,
                        }
                        for ref in sorted(refs, key=lambda x: x.line_number)
                    ],
                }
            )

        return matrix

    def output_json(self) -> str:
        """Output as JSON"""
        summary = self.generate_summary()
        matrix = self.generate_matrix()

        result = {
            "summary": summary,
            "impact_matrix": matrix,
            "all_references": [asdict(ref) for ref in self.references],
        }

        return json.dumps(result, indent=2, default=str)

    def output_markdown(self) -> str:
        """Output as Markdown"""
        lines = ["# Hardcoded Endpoint URL Impact Matrix\n"]

        summary = self.generate_summary()

        lines.append("## Summary\n")
        lines.append(f"- Total References: {summary['total_references']}")
        lines.append(f"- Unique Files: {summary['unique_files']}")
        lines.append(f"- Unique Endpoints: {summary['unique_endpoints']}\n")

        lines.append("### By Priority\n")
        for priority in ["Critical", "High", "Medium", "Low"]:
            count = summary["by_priority"].get(priority, 0)
            lines.append(f"- **{priority}**: {count}")
        lines.append("")

        lines.append("### By Category\n")
        for category, count in sorted(summary["by_category"].items()):
            lines.append(f"- **{category}**: {count}")
        lines.append("")

        lines.append("## Impact Matrix\n")

        matrix = self.generate_matrix()
        for entry in matrix:
            lines.append(f"### {entry['file_path']}\n")
            lines.append(f"- **Total References**: {entry['total_references']}")
            lines.append(f"- **Categories**: {', '.join(entry['categories'])}")
            lines.append("- **Priority Breakdown**:")
            for priority, count in sorted(entry["priority_breakdown"].items()):
                lines.append(f"  - {priority}: {count}")
            lines.append("")
            lines.append("#### References\n")
            for ref in entry["references"][:20]:  # Limit to first 20 per file
                lines.append(
                    f"- Line {ref['line_number']}: `{ref['endpoint_url']}` ({ref['priority']})"
                )
                if ref["is_in_comment"]:
                    lines.append("  - ⚠️ In comment")
                if ref["is_deprecated"]:
                    lines.append("  - ⚠️ Deprecated context")
            if len(entry["references"]) > 20:
                lines.append(f"- ... and {len(entry['references']) - 20} more references")
            lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Search codebase for hardcoded endpoint URLs")
    parser.add_argument("--base-dir", default=".", help="Base directory to search")
    parser.add_argument(
        "--output-format", choices=["json", "markdown"], default="json", help="Output format"
    )
    parser.add_argument("--output-file", help="Output file path")
    parser.add_argument(
        "--search-dirs",
        nargs="+",
        default=[
            "tests/",
            "cli/",
            "frontend/",
            "docs/",
            "hub/apps/orchestration/workflows/",
            "sdk/",
        ],
        help="Directories to search",
    )
    parser.add_argument(
        "--all", action="store_true", help="Search entire codebase (ignores --search-dirs)"
    )

    args = parser.parse_args()

    searcher = EndpointURLSearcher(base_dir=args.base_dir)

    if args.all:
        print("Searching entire codebase...", file=sys.stderr)
        references = searcher.search_directory(Path(args.base_dir))
    else:
        references = searcher.search_specific_directories(args.search_dirs)

    print(f"\nTotal references found: {len(references)}", file=sys.stderr)

    generator = ImpactMatrixGenerator(references)

    if args.output_format == "json":
        output = generator.output_json()
    else:
        output = generator.output_markdown()

    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(output)
        print(f"Output written to {args.output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
