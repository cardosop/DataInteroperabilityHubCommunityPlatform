#!/usr/bin/env python3
"""
Comprehensive Code Example Checker Script

This script checks code examples in documentation and example files to:
- Search for code examples in documentation (markdown files)
- Search for code examples in example Python files
- Extract endpoint URLs from examples
- Validate example accuracy (syntax, endpoint existence)

Usage:
    python scripts/check_code_examples.py [--docs-dir DOCS_DIR] [--examples-dir EXAMPLES_DIR]
                                          [--inventory INVENTORY_FILE] [--output OUTPUT_FILE]
"""

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CodeExample:
    """Represents a code example found in documentation or example files"""

    source_file: str
    language: str  # python, bash, shell, curl, http, javascript, typescript, etc.
    code: str
    line_number: int
    context: str = ""  # Surrounding context in markdown


@dataclass
class ExampleValidationResult:
    """Validation result for a code example"""

    example: CodeExample
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    endpoints_found: list[str] = field(default_factory=list)
    endpoints_valid: list[str] = field(default_factory=list)
    endpoints_invalid: list[str] = field(default_factory=list)


class CodeExampleChecker:
    """Checks code examples for accuracy and validity"""

    def __init__(
        self,
        docs_dir: str = "docs",
        examples_dir: str = "examples",
        endpoint_inventory_file: str = "docs/api-audit/endpoint-inventory-current.json",
        base_path: str = ".",
    ):
        self.base_path = Path(base_path)
        self.docs_dir = self.base_path / docs_dir
        self.examples_dir = self.base_path / examples_dir
        self.endpoint_inventory_file = self.base_path / endpoint_inventory_file

        if not self.endpoint_inventory_file.exists():
            raise FileNotFoundError(
                f"Endpoint inventory file not found: {self.endpoint_inventory_file}"
            )

        # Load endpoint inventory
        self.known_endpoints: dict[str, set[str]] = {}  # endpoint_path -> set of methods
        self._load_endpoint_inventory()

        # All code examples found
        self.code_examples: list[CodeExample] = []

        # Patterns for finding endpoints in code
        self.endpoint_patterns = [
            # Full URLs: http://.../api/v1/...
            re.compile(r'(?:https?://[^\s"\'`\)]+)?(/api/v\d+/[^\s"\'`\)]+)', re.IGNORECASE),
            # Relative paths: /api/v1/...
            re.compile(r'["\'](/api/v\d+/[^\s"\'`\)]+)["\']', re.IGNORECASE),
            # f-strings: f'/api/v1/...'
            re.compile(r'f["\'](/api/v\d+/[^\s"\'`\)]+)["\']', re.IGNORECASE),
            # URL variables: url = "..."
            re.compile(r'url\s*=\s*["\']([^"\']*?/api/v\d+/[^\s"\'`\)]+)["\']', re.IGNORECASE),
            # curl commands
            re.compile(r"curl\s+[^\s]*\s+([^\s]*?/api/v\d+/[^\s]+)", re.IGNORECASE),
            # HTTP method + path
            re.compile(
                r"(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+([^\s]*?/api/v\d+/[^\s]+)",
                re.IGNORECASE,
            ),
        ]

    def _load_endpoint_inventory(self):
        """Load endpoint inventory from JSON file"""
        try:
            with open(self.endpoint_inventory_file, encoding="utf-8") as f:
                inventory_data = json.load(f)

            # Handle different inventory formats
            if "inventory" in inventory_data:
                endpoints = inventory_data["inventory"].get("endpoints", [])
            elif "endpoints" in inventory_data:
                endpoints = inventory_data["endpoints"]
            else:
                endpoints = []

            for endpoint_info in endpoints:
                if isinstance(endpoint_info, dict):
                    # Handle different endpoint formats
                    endpoint_path = (
                        endpoint_info.get("full_path")
                        or endpoint_info.get("endpoint_path")
                        or endpoint_info.get("path", "")
                    )
                    methods = endpoint_info.get("methods", [])

                    if endpoint_path:
                        normalized = self.normalize_endpoint(endpoint_path)
                        if normalized not in self.known_endpoints:
                            self.known_endpoints[normalized] = set()
                        if isinstance(methods, list):
                            self.known_endpoints[normalized].update(m.upper() for m in methods)
                        elif isinstance(methods, str):
                            self.known_endpoints[normalized].add(methods.upper())

        except Exception as e:
            print(f"Warning: Error loading endpoint inventory: {e}", file=sys.stderr)

    def normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path for comparison"""
        # Remove protocol and host
        endpoint = re.sub(r"https?://[^/]+", "", endpoint)
        # Remove query parameters
        endpoint = endpoint.split("?")[0]
        # Remove fragments
        endpoint = endpoint.split("#")[0]
        # Normalize trailing slash (but preserve root paths)
        if (
            endpoint
            and not endpoint.endswith("/")
            and "/api/" in endpoint
            and endpoint != "/api/v1"
        ):
            endpoint += "/"
        return endpoint

    def is_our_api_endpoint(self, endpoint: str) -> bool:
        """Check if endpoint belongs to our API (not external services)"""
        normalized = self.normalize_endpoint(endpoint)
        # Skip Prometheus, Grafana, and other external service endpoints
        external_patterns = [
            r":9090",  # Prometheus
            r":3000",  # Grafana
            r"/metrics",
            r"/api/v1/query",  # Prometheus query API
        ]
        for pattern in external_patterns:
            if re.search(pattern, endpoint, re.IGNORECASE):
                return False
        # Only validate endpoints that start with /api/v1/ or /api/v2/ etc.
        return bool(re.match(r"^/api/v\d+/", normalized))

    def find_code_examples(self) -> list[CodeExample]:
        """Find all code examples in documentation and example files"""
        examples = []

        # Search markdown files in docs directory
        if self.docs_dir.exists():
            for md_file in self.docs_dir.rglob("*.md"):
                examples.extend(self._extract_from_markdown(md_file))

        # Search Python files in examples directory
        if self.examples_dir.exists():
            for py_file in self.examples_dir.rglob("*.py"):
                examples.extend(self._extract_from_python_file(py_file))

        self.code_examples = examples
        return examples

    def _extract_from_markdown(self, md_file: Path) -> list[CodeExample]:
        """Extract code examples from markdown file"""
        examples = []

        try:
            content = md_file.read_text(encoding="utf-8")
            # Try to get relative path, fall back to absolute if not subpath
            try:
                relative_path = str(md_file.relative_to(self.base_path))
            except ValueError:
                # File is not a subpath of base_path, use absolute path
                relative_path = str(md_file)

            # Pattern to match code blocks: ```language\ncode\n```
            code_block_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL | re.MULTILINE)

            line_number = 1
            for match in code_block_pattern.finditer(content):
                language = match.group(1) or "text"
                code = match.group(2).strip()

                # Calculate approximate line number
                line_number = content[: match.start()].count("\n") + 1

                # Get context (50 chars before and after)
                start_context = max(0, match.start() - 50)
                end_context = min(len(content), match.end() + 50)
                context = content[start_context:end_context]

                example = CodeExample(
                    source_file=relative_path,
                    language=language.lower(),
                    code=code,
                    line_number=line_number,
                    context=context,
                )
                examples.append(example)

        except Exception as e:
            print(f"Error processing {md_file}: {e}", file=sys.stderr)

        return examples

    def _extract_from_python_file(self, py_file: Path) -> list[CodeExample]:
        """Extract code example from Python file"""
        examples = []

        try:
            content = py_file.read_text(encoding="utf-8")
            # Try to get relative path, fall back to absolute if not subpath
            try:
                relative_path = str(py_file.relative_to(self.base_path))
            except ValueError:
                # File is not a subpath of base_path, use absolute path
                relative_path = str(py_file)

            example = CodeExample(
                source_file=relative_path,
                language="python",
                code=content,
                line_number=1,
                context="",
            )
            examples.append(example)

        except Exception as e:
            print(f"Error processing {py_file}: {e}", file=sys.stderr)

        return examples

    def extract_endpoints_from_examples(
        self, examples: list[CodeExample] | None = None
    ) -> list[dict[str, Any]]:
        """Extract endpoint URLs from code examples"""
        if examples is None:
            examples = self.code_examples

        endpoints = []
        seen = set()

        for example in examples:
            for pattern in self.endpoint_patterns:
                for match in pattern.finditer(example.code):
                    endpoint = match.group(1) if match.lastindex else match.group(0)
                    normalized = self.normalize_endpoint(endpoint)

                    # Avoid duplicates
                    key = (example.source_file, normalized, example.line_number)
                    if key not in seen:
                        seen.add(key)
                        endpoints.append(
                            {
                                "endpoint": normalized,
                                "original": endpoint,
                                "source_file": example.source_file,
                                "language": example.language,
                                "line_number": example.line_number,
                                "context": example.code[:200],  # First 200 chars
                            }
                        )

        return endpoints

    def validate_python_syntax(self, example: CodeExample) -> ExampleValidationResult:
        """Validate Python code syntax"""
        result = ExampleValidationResult(example=example, is_valid=True, errors=[], warnings=[])

        if example.language != "python":
            result.warnings.append(f"Not a Python example (language: {example.language})")
            return result

        # For code snippets in markdown, be more lenient with indentation
        # Only validate if it's a full Python file
        is_full_file = example.source_file.endswith(".py")

        try:
            # Try parsing as-is first
            ast.parse(example.code)
        except SyntaxError as e:
            # If it's a code snippet (not a full file), try dedenting
            if not is_full_file and "unexpected indent" in str(e).lower():
                try:
                    import textwrap

                    dedented = textwrap.dedent(example.code)
                    ast.parse(dedented)
                    # If dedenting fixes it, just warn instead of error
                    result.warnings.append("Code snippet has indentation (fixed by dedenting)")
                except:
                    # If dedenting doesn't help, it's a real syntax error
                    result.is_valid = False
                    result.errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            else:
                result.is_valid = False
                result.errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Parse error: {e!s}")

        return result

    def validate_endpoint_exists(self, endpoint: str) -> ExampleValidationResult:
        """Validate that endpoint exists in inventory"""
        normalized = self.normalize_endpoint(endpoint)

        # Create a dummy example for the result
        dummy_example = CodeExample(source_file="", language="", code="", line_number=0)

        result = ExampleValidationResult(
            example=dummy_example, is_valid=True, errors=[], warnings=[]
        )

        if normalized in self.known_endpoints:
            result.endpoints_valid.append(normalized)
        else:
            result.is_valid = False
            result.errors.append(f"Endpoint not found in inventory: {normalized}")
            result.endpoints_invalid.append(normalized)

        return result

    def validate_all_examples(self) -> dict[str, Any]:
        """Validate all code examples comprehensively"""
        print("🔍 Finding code examples...")
        examples = self.find_code_examples()
        print(f"   Found {len(examples)} code examples")

        print("🔍 Extracting endpoints from examples...")
        endpoints = self.extract_endpoints_from_examples(examples)
        print(f"   Found {len(endpoints)} endpoint references")

        print("✅ Validating examples...")
        validation_results = []

        # Group endpoints by example
        endpoints_by_example = defaultdict(list)
        for endpoint_info in endpoints:
            key = (endpoint_info["source_file"], endpoint_info["line_number"])
            endpoints_by_example[key].append(endpoint_info)

        for example in examples:
            result = ExampleValidationResult(example=example, is_valid=True, errors=[], warnings=[])

            # Validate Python syntax
            if example.language == "python":
                syntax_result = self.validate_python_syntax(example)
                if not syntax_result.is_valid:
                    result.is_valid = False
                    result.errors.extend(syntax_result.errors)

            # Validate endpoints in this example
            key = (example.source_file, example.line_number)
            example_endpoints = endpoints_by_example.get(key, [])

            for endpoint_info in example_endpoints:
                endpoint = endpoint_info["endpoint"]
                original_endpoint = endpoint_info.get("original", endpoint)
                result.endpoints_found.append(endpoint)

                # Only validate endpoints that belong to our API
                if self.is_our_api_endpoint(original_endpoint):
                    endpoint_result = self.validate_endpoint_exists(endpoint)
                    if endpoint_result.is_valid:
                        result.endpoints_valid.append(endpoint)
                    else:
                        result.is_valid = False
                        result.endpoints_invalid.append(endpoint)
                        result.errors.extend(endpoint_result.errors)
                else:
                    # External endpoint - just warn
                    result.warnings.append(
                        f"Skipping validation for external endpoint: {original_endpoint}"
                    )

            validation_results.append(result)

        # Calculate summary
        total_examples = len(validation_results)
        valid_examples = sum(1 for r in validation_results if r.is_valid)
        invalid_examples = total_examples - valid_examples
        total_endpoints = len(endpoints)
        valid_endpoints = sum(len(r.endpoints_valid) for r in validation_results)
        invalid_endpoints = sum(len(r.endpoints_invalid) for r in validation_results)

        return {
            "summary": {
                "generated_at": datetime.now().isoformat(),
                "total_examples": total_examples,
                "valid_examples": valid_examples,
                "invalid_examples": invalid_examples,
                "total_endpoints_found": total_endpoints,
                "valid_endpoints": valid_endpoints,
                "invalid_endpoints": invalid_endpoints,
                "known_endpoints_in_inventory": len(self.known_endpoints),
            },
            "examples": [asdict(result) for result in validation_results],
            "endpoints": endpoints,
        }

    def generate_report(self, results: dict[str, Any], output_file: str):
        """Generate JSON report"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📊 Report generated: {output_path}")
        print(f"   Total examples: {results['summary']['total_examples']}")
        print(f"   Valid examples: {results['summary']['valid_examples']}")
        print(f"   Invalid examples: {results['summary']['invalid_examples']}")
        print(f"   Total endpoints found: {results['summary']['total_endpoints_found']}")
        print(f"   Valid endpoints: {results['summary']['valid_endpoints']}")
        print(f"   Invalid endpoints: {results['summary']['invalid_endpoints']}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Check code examples in documentation and example files"
    )
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Directory containing documentation files (default: docs)",
    )
    parser.add_argument(
        "--examples-dir",
        default="examples",
        help="Directory containing example files (default: examples)",
    )
    parser.add_argument(
        "--inventory",
        default="docs/api-audit/endpoint-inventory-current.json",
        help="Endpoint inventory JSON file (default: docs/api-audit/endpoint-inventory-current.json)",
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/code-examples-audit.json",
        help="Output JSON report file (default: docs/api-audit/code-examples-audit.json)",
    )
    parser.add_argument("--base-path", default=".", help="Base path of the project (default: .)")

    args = parser.parse_args()

    try:
        checker = CodeExampleChecker(
            docs_dir=args.docs_dir,
            examples_dir=args.examples_dir,
            endpoint_inventory_file=args.inventory,
            base_path=args.base_path,
        )

        results = checker.validate_all_examples()
        checker.generate_report(results, args.output)

        # Exit with error code if there are invalid examples
        if results["summary"]["invalid_examples"] > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
