#!/usr/bin/env python3
"""
Comprehensive OpenAPI Specification Review Script

Reviews the OpenAPI specification and identifies:
- Missing request/response schemas
- Missing error responses
- Missing examples
- Incomplete documentation
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class OpenAPISpecReviewer:
    """Reviewer for OpenAPI specifications."""

    def __init__(self, spec_path: str):
        """Initialize reviewer with OpenAPI spec path."""
        self.spec_path = Path(spec_path)
        self.spec = self._load_spec()
        self.issues: List[Dict[str, Any]] = []
        self.stats: Dict[str, Any] = {}

    def _load_spec(self) -> Dict[str, Any]:
        """Load OpenAPI specification."""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found: {self.spec_path}")

        with open(self.spec_path, "r") as f:
            if self.spec_path.suffix in [".yaml", ".yml"]:
                return yaml.safe_load(f)
            else:
                return json.load(f)

    def review(self) -> Dict[str, Any]:
        """Perform comprehensive review of OpenAPI spec."""
        print("=" * 80)
        print("OpenAPI Specification Review")
        print("=" * 80)
        print()

        # Basic stats
        self._collect_stats()

        # Review paths
        self._review_paths()

        # Review components
        self._review_components()

        # Review security
        self._review_security()

        # Review examples
        self._review_examples()

        # Review error responses
        self._review_error_responses()

        # Generate report
        return self._generate_report()

    def _collect_stats(self):
        """Collect basic statistics about the spec."""
        paths = self.spec.get("paths", {})
        components = self.spec.get("components", {})
        schemas = components.get("schemas", {})

        self.stats = {
            "openapi_version": self.spec.get("openapi", "N/A"),
            "title": self.spec.get("info", {}).get("title", "N/A"),
            "version": self.spec.get("info", {}).get("version", "N/A"),
            "total_paths": len(paths),
            "total_operations": sum(
                len([m for m in path_item.keys() if m in ["get", "post", "put", "patch", "delete"]])
                for path_item in paths.values()
                if isinstance(path_item, dict)
            ),
            "total_schemas": len(schemas),
            "total_tags": len(self.spec.get("tags", [])),
        }

        print("📊 Statistics:")
        for key, value in self.stats.items():
            print(f"  {key}: {value}")
        print()

    def _review_paths(self):
        """Review all paths and operations."""
        paths = self.spec.get("paths", {})
        operations_without_description = []
        operations_without_summary = []
        operations_without_tags = []
        operations_without_operation_id = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                operation_path = f"{method.upper()} {path}"

                # Check for description
                if not operation.get("description"):
                    operations_without_description.append(operation_path)

                # Check for summary
                if not operation.get("summary"):
                    operations_without_summary.append(operation_path)

                # Check for tags
                if not operation.get("tags"):
                    operations_without_tags.append(operation_path)

                # Check for operationId
                if not operation.get("operationId"):
                    operations_without_operation_id.append(operation_path)

        # Add issues
        if operations_without_description:
            self.issues.append(
                {
                    "severity": "warn",
                    "category": "documentation",
                    "message": f"{len(operations_without_description)} operations without descriptions",
                    "details": operations_without_description[:10],  # Show first 10
                }
            )

        if operations_without_summary:
            self.issues.append(
                {
                    "severity": "warn",
                    "category": "documentation",
                    "message": f"{len(operations_without_summary)} operations without summaries",
                    "details": operations_without_summary[:10],
                }
            )

        if operations_without_tags:
            self.issues.append(
                {
                    "severity": "error",
                    "category": "structure",
                    "message": f"{len(operations_without_tags)} operations without tags",
                    "details": operations_without_tags[:10],
                }
            )

        if operations_without_operation_id:
            self.issues.append(
                {
                    "severity": "error",
                    "category": "structure",
                    "message": f"{len(operations_without_operation_id)} operations without operationId",
                    "details": operations_without_operation_id[:10],
                }
            )

    def _review_components(self):
        """Review components section."""
        components = self.spec.get("components", {})
        schemas = components.get("schemas", {})

        schemas_without_description = []
        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            if not schema.get("description"):
                schemas_without_description.append(schema_name)

        if schemas_without_description:
            self.issues.append(
                {
                    "severity": "warn",
                    "category": "documentation",
                    "message": f"{len(schemas_without_description)} schemas without descriptions",
                    "details": schemas_without_description[:20],
                }
            )

    def _review_security(self):
        """Review security schemes."""
        components = self.spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        if not security_schemes:
            self.issues.append(
                {
                    "severity": "error",
                    "category": "security",
                    "message": "No security schemes defined",
                }
            )

    def _review_examples(self):
        """Review examples in operations."""
        paths = self.spec.get("paths", {})
        operations_without_examples = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                has_example = False

                # Check request body examples
                request_body = operation.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    for media_type, media_spec in content.items():
                        if "example" in media_spec or "examples" in media_spec:
                            has_example = True
                            break

                # Check response examples
                responses = operation.get("responses", {})
                for status_code, response in responses.items():
                    if isinstance(response, dict):
                        content = response.get("content", {})
                        for media_type, media_spec in content.items():
                            if "example" in media_spec or "examples" in media_spec:
                                has_example = True
                                break
                    if has_example:
                        break

                if not has_example and method in ["post", "put", "patch"]:
                    operations_without_examples.append(f"{method.upper()} {path}")

        if operations_without_examples:
            self.issues.append(
                {
                    "severity": "warn",
                    "category": "examples",
                    "message": f"{len(operations_without_examples)} operations without examples",
                    "details": operations_without_examples[:20],
                }
            )

    def _review_error_responses(self):
        """Review error responses in operations."""
        paths = self.spec.get("paths", {})
        operations_missing_errors = []

        standard_error_codes = ["400", "401", "403", "404", "500"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                responses = operation.get("responses", {})
                missing_errors = [code for code in standard_error_codes if code not in responses]

                if missing_errors:
                    operations_missing_errors.append(
                        {
                            "operation": f"{method.upper()} {path}",
                            "missing": missing_errors,
                        }
                    )

        if operations_missing_errors:
            self.issues.append(
                {
                    "severity": "warn",
                    "category": "error_responses",
                    "message": f"{len(operations_missing_errors)} operations missing standard error responses",
                    "details": operations_missing_errors[:20],
                }
            )

    def _generate_report(self) -> Dict[str, Any]:
        """Generate review report."""
        error_count = sum(1 for issue in self.issues if issue["severity"] == "error")
        warn_count = sum(1 for issue in self.issues if issue["severity"] == "warn")

        print("=" * 80)
        print("Review Results")
        print("=" * 80)
        print(f"Total Issues: {len(self.issues)}")
        print(f"  Errors: {error_count}")
        print(f"  Warnings: {warn_count}")
        print()

        if self.issues:
            print("Issues Found:")
            print()
            for i, issue in enumerate(self.issues, 1):
                severity_icon = "❌" if issue["severity"] == "error" else "⚠️"
                print(f"{i}. {severity_icon} [{issue['category']}] {issue['message']}")
                if "details" in issue and issue["details"]:
                    if isinstance(issue["details"], list):
                        for detail in issue["details"][:5]:
                            print(f"     - {detail}")
                        if len(issue["details"]) > 5:
                            print(f"     ... and {len(issue['details']) - 5} more")
                    else:
                        print(f"     {issue['details']}")
                print()
        else:
            print("✅ No issues found!")

        return {
            "stats": self.stats,
            "issues": self.issues,
            "summary": {
                "total_issues": len(self.issues),
                "errors": error_count,
                "warnings": warn_count,
            },
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Review OpenAPI specification")
    parser.add_argument(
        "spec",
        nargs="?",
        default="api/openapi-hub-v1.yaml",
        help="Path to OpenAPI specification file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    try:
        reviewer = OpenAPISpecReviewer(args.spec)
        report = reviewer.review()

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            # Exit with error code if there are errors
            error_count = report["summary"]["errors"]
            sys.exit(1 if error_count > 0 else 0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
