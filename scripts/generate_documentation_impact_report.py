#!/usr/bin/env python3
"""
Documentation Impact Report Generator

This script compiles documentation references from all audit reports and generates
a comprehensive documentation impact analysis report.

Usage:
    python scripts/generate_documentation_impact_report.py [--reports-dir REPORTS_DIR] [--output OUTPUT_FILE]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


class DocumentationImpactReportGenerator:
    """Generates comprehensive documentation impact analysis report"""

    def __init__(self, audit_reports_dir: str = "docs/api-audit", base_path: str = "."):
        self.base_path = Path(base_path)
        self.audit_reports_dir = self.base_path / audit_reports_dir

        # Loaded audit reports
        self.audit_reports: dict[str, Any] = {}

    def load_audit_reports(self) -> dict[str, Any]:
        """Load all audit report files"""
        reports = {}

        report_files = {
            "documentation_endpoint_audit": "documentation-endpoint-audit.json",
            "code_examples_audit": "code-examples-audit.json",
            "postman_collections_audit": "postman-collections-audit.json",
            "inventory_review": "inventory-review-report.json",
        }

        for report_key, filename in report_files.items():
            report_path = self.audit_reports_dir / filename
            if report_path.exists():
                try:
                    with open(report_path, encoding="utf-8") as f:
                        reports[report_key] = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not load {filename}: {e}", file=sys.stderr)
            else:
                print(f"Warning: Audit report not found: {filename}", file=sys.stderr)

        self.audit_reports = reports
        return reports

    def compile_documentation_references(self) -> dict[str, Any]:
        """Compile all documentation references from audit reports"""
        references = {
            "documentation_files": set(),
            "endpoints": {},
            "code_examples": [],
            "postman_collections": [],
            "statistics": {},
        }

        # From documentation endpoint audit
        if "documentation_endpoint_audit" in self.audit_reports:
            doc_audit = self.audit_reports["documentation_endpoint_audit"]
            summary = doc_audit.get("summary", {})

            references["statistics"]["total_documentation_files"] = summary.get(
                "total_documentation_files", 0
            )
            references["statistics"]["total_endpoint_references"] = summary.get(
                "total_references", 0
            )
            references["statistics"]["total_unique_endpoints"] = summary.get("total_endpoints", 0)

            # Collect documentation files
            for endpoint_data in doc_audit.get("endpoints", []):
                endpoint_path = endpoint_data.get("endpoint_path", "")
                normalized_path = endpoint_data.get("normalized_path", endpoint_path)
                methods = endpoint_data.get("methods", []) or []
                doc_files = endpoint_data.get("documentation_files", []) or []

                if not isinstance(methods, list):
                    methods = []
                if not isinstance(doc_files, list):
                    doc_files = []

                references["documentation_files"].update(doc_files)

                if normalized_path not in references["endpoints"]:
                    references["endpoints"][normalized_path] = {
                        "methods": set(methods),
                        "documentation_files": set(doc_files),
                        "total_references": endpoint_data.get("total_references", 0),
                    }
                else:
                    references["endpoints"][normalized_path]["methods"].update(methods)
                    references["endpoints"][normalized_path]["documentation_files"].update(
                        doc_files
                    )

        # From code examples audit
        if "code_examples_audit" in self.audit_reports:
            code_audit = self.audit_reports["code_examples_audit"]
            summary = code_audit.get("summary", {})

            references["statistics"]["total_code_examples"] = summary.get("total_examples", 0)
            references["statistics"]["valid_code_examples"] = summary.get("valid_examples", 0)
            references["statistics"]["invalid_code_examples"] = summary.get("invalid_examples", 0)
            references["statistics"]["code_example_endpoints_found"] = summary.get(
                "total_endpoints_found", 0
            )

            # Collect invalid examples
            for example_data in code_audit.get("examples", []):
                if not example_data.get("is_valid", True):
                    references["code_examples"].append(
                        {
                            "source_file": example_data.get("example", {}).get("source_file", ""),
                            "errors": example_data.get("errors", []),
                            "endpoints_invalid": example_data.get("endpoints_invalid", []),
                        }
                    )

        # From Postman collections audit
        if "postman_collections_audit" in self.audit_reports:
            postman_audit = self.audit_reports["postman_collections_audit"]
            summary = postman_audit.get("summary", {})

            references["statistics"]["total_postman_collections"] = summary.get(
                "total_collections", 0
            )
            references["statistics"]["valid_postman_collections"] = summary.get(
                "valid_collections", 0
            )
            references["statistics"]["invalid_postman_collections"] = summary.get(
                "invalid_collections", 0
            )
            references["statistics"]["total_postman_requests"] = summary.get("total_requests", 0)

            # Collect invalid collections
            for collection_data in postman_audit.get("collections", []):
                if not collection_data.get("is_valid", True):
                    references["postman_collections"].append(
                        {
                            "collection_file": collection_data.get("collection_file", ""),
                            "errors": collection_data.get("errors", []),
                        }
                    )

        # From inventory review
        if "inventory_review" in self.audit_reports:
            inventory_review = self.audit_reports["inventory_review"]
            summary = inventory_review.get("summary", {})

            references["statistics"]["inventory_endpoints"] = summary.get(
                "total_endpoints_in_inventory", 0
            )
            references["statistics"]["codebase_endpoints"] = summary.get(
                "total_endpoints_in_codebase", 0
            )
            references["statistics"]["discrepancies"] = summary.get("discrepancies", 0)

        # Convert sets to lists for JSON serialization
        references["documentation_files"] = sorted(list(references["documentation_files"]))
        for endpoint_path, endpoint_info in references["endpoints"].items():
            endpoint_info["methods"] = sorted(list(endpoint_info["methods"]))
            endpoint_info["documentation_files"] = sorted(
                list(endpoint_info["documentation_files"])
            )

        return references

    def identify_documentation_updates(self, references: dict[str, Any]) -> dict[str, Any]:
        """Identify documentation updates needed"""
        updates = {
            "files_to_update": [],
            "endpoints_missing_docs": [],
            "invalid_examples": references.get("code_examples", []),
            "invalid_collections": references.get("postman_collections", []),
            "recommendations": [],
        }

        # Identify endpoints with multiple documentation files (may need consolidation)
        endpoints_with_multiple_docs = []
        for endpoint_path, endpoint_info in references.get("endpoints", {}).items():
            doc_files = endpoint_info.get("documentation_files", [])
            if len(doc_files) > 1:
                endpoints_with_multiple_docs.append(
                    {
                        "endpoint": endpoint_path,
                        "documentation_files": doc_files,
                        "methods": endpoint_info.get("methods", []),
                    }
                )

        updates["endpoints_with_multiple_docs"] = endpoints_with_multiple_docs

        # Identify files with invalid examples
        files_with_invalid_examples = defaultdict(list)
        for example in references.get("code_examples", []):
            source_file = example.get("source_file", "")
            if source_file:
                files_with_invalid_examples[source_file].append(example)

        updates["files_with_invalid_examples"] = dict(files_with_invalid_examples)

        # Generate recommendations
        stats = references.get("statistics", {})

        if stats.get("invalid_code_examples", 0) > 0:
            updates["recommendations"].append(
                {
                    "priority": "high",
                    "category": "code_examples",
                    "description": f"Fix {stats['invalid_code_examples']} invalid code examples in documentation",
                    "action": "Review and update code examples with syntax errors or invalid endpoints",
                }
            )

        if stats.get("invalid_postman_collections", 0) > 0:
            updates["recommendations"].append(
                {
                    "priority": "medium",
                    "category": "postman_collections",
                    "description": f"Fix {stats['invalid_postman_collections']} invalid Postman collections",
                    "action": "Update Postman collections with invalid endpoints",
                }
            )

        if len(endpoints_with_multiple_docs) > 0:
            updates["recommendations"].append(
                {
                    "priority": "low",
                    "category": "documentation_consolidation",
                    "description": f"Consolidate documentation for {len(endpoints_with_multiple_docs)} endpoints with multiple documentation files",
                    "action": "Review and consolidate duplicate documentation",
                }
            )

        return updates

    def generate_report(self, output_file: str):
        """Generate comprehensive markdown report"""
        print("📊 Loading audit reports...")
        self.load_audit_reports()

        print("📝 Compiling documentation references...")
        references = self.compile_documentation_references()

        print("🔍 Identifying documentation updates...")
        updates = self.identify_documentation_updates(references)

        print("📄 Generating report...")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            self._write_report_header(f)
            self._write_summary(f, references, updates)
            self._write_documentation_files(f, references)
            self._write_endpoints(f, references, updates)
            self._write_code_examples(f, references, updates)
            self._write_postman_collections(f, references, updates)
            self._write_recommendations(f, updates)
            self._write_footer(f)

        print(f"\n✅ Report generated: {output_path}")
        print(f"   Documentation files analyzed: {len(references.get('documentation_files', []))}")
        print(f"   Endpoints documented: {len(references.get('endpoints', {}))}")
        print(f"   Invalid examples: {len(updates.get('invalid_examples', []))}")
        print(f"   Invalid collections: {len(updates.get('invalid_collections', []))}")

    def _write_report_header(self, f):
        """Write report header"""
        f.write("# Documentation Impact Analysis\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(
            "This report compiles documentation references from all audit reports and identifies "
            "documentation that needs to be updated.\n\n"
        )
        f.write("---\n\n")

    def _write_summary(self, f, references: dict[str, Any], updates: dict[str, Any]):
        """Write summary section"""
        f.write("## Summary\n\n")

        stats = references.get("statistics", {})

        f.write("### Documentation Statistics\n\n")
        f.write(f"- **Total Documentation Files:** {stats.get('total_documentation_files', 0)}\n")
        f.write(f"- **Total Endpoint References:** {stats.get('total_endpoint_references', 0)}\n")
        f.write(f"- **Total Unique Endpoints:** {stats.get('total_unique_endpoints', 0)}\n")
        f.write(f"- **Total Code Examples:** {stats.get('total_code_examples', 0)}\n")
        f.write(f"  - Valid: {stats.get('valid_code_examples', 0)}\n")
        f.write(f"  - Invalid: {stats.get('invalid_code_examples', 0)}\n")
        f.write(f"- **Total Postman Collections:** {stats.get('total_postman_collections', 0)}\n")
        f.write(f"  - Valid: {stats.get('valid_postman_collections', 0)}\n")
        f.write(f"  - Invalid: {stats.get('invalid_postman_collections', 0)}\n")
        f.write(f"- **Total Postman Requests:** {stats.get('total_postman_requests', 0)}\n")

        if "inventory_endpoints" in stats:
            f.write(f"- **Inventory Endpoints:** {stats.get('inventory_endpoints', 0)}\n")
            f.write(f"- **Codebase Endpoints:** {stats.get('codebase_endpoints', 0)}\n")
            f.write(f"- **Discrepancies:** {stats.get('discrepancies', 0)}\n")

        f.write("\n### Issues Identified\n\n")
        f.write(f"- **Invalid Code Examples:** {len(updates.get('invalid_examples', []))}\n")
        f.write(
            f"- **Invalid Postman Collections:** {len(updates.get('invalid_collections', []))}\n"
        )
        f.write(
            f"- **Endpoints with Multiple Documentation Files:** {len(updates.get('endpoints_with_multiple_docs', []))}\n"
        )

        f.write("\n---\n\n")

    def _write_documentation_files(self, f, references: dict[str, Any]):
        """Write documentation files section"""
        f.write("## Documentation Files\n\n")

        doc_files = references.get("documentation_files", [])
        if doc_files:
            f.write(f"Total documentation files analyzed: **{len(doc_files)}**\n\n")
            f.write("### Files List\n\n")
            for doc_file in sorted(doc_files):
                f.write(f"- `{doc_file}`\n")
        else:
            f.write("No documentation files found in audit reports.\n")

        f.write("\n---\n\n")

    def _write_endpoints(self, f, references: dict[str, Any], updates: dict[str, Any]):
        """Write endpoints section"""
        f.write("## Endpoints\n\n")

        endpoints = references.get("endpoints", {})
        if endpoints:
            f.write(f"Total endpoints documented: **{len(endpoints)}**\n\n")

            # Endpoints with multiple documentation files
            multiple_docs = updates.get("endpoints_with_multiple_docs", [])
            if multiple_docs:
                f.write("### Endpoints with Multiple Documentation Files\n\n")
                f.write(
                    "These endpoints have documentation in multiple files and may need consolidation:\n\n"
                )
                for item in multiple_docs[:20]:  # Limit to first 20
                    f.write(f"- **{item['endpoint']}** ({', '.join(item['methods'])})\n")
                    for doc_file in item["documentation_files"]:
                        f.write(f"  - `{doc_file}`\n")
                if len(multiple_docs) > 20:
                    f.write(f"\n*... and {len(multiple_docs) - 20} more*\n")
                f.write("\n")
        else:
            f.write("No endpoints found in audit reports.\n")

        f.write("\n---\n\n")

    def _write_code_examples(self, f, references: dict[str, Any], updates: dict[str, Any]):
        """Write code examples section"""
        f.write("## Code Examples\n\n")

        invalid_examples = updates.get("invalid_examples", [])
        if invalid_examples:
            f.write(f"### Invalid Code Examples ({len(invalid_examples)})\n\n")
            f.write("The following code examples have errors and need to be fixed:\n\n")

            files_with_issues = updates.get("files_with_invalid_examples", {})
            for file_path, examples in list(files_with_issues.items())[
                :10
            ]:  # Limit to first 10 files
                f.write(f"#### `{file_path}`\n\n")
                for example in examples[:5]:  # Limit to first 5 examples per file
                    errors = example.get("errors", [])
                    endpoints_invalid = example.get("endpoints_invalid", [])
                    f.write(f"- **Errors:** {len(errors)}\n")
                    if errors:
                        f.write(f"  - {errors[0]}\n")
                    if endpoints_invalid:
                        f.write(f"  - Invalid endpoints: {', '.join(endpoints_invalid[:3])}\n")
                f.write("\n")

            if len(files_with_issues) > 10:
                f.write(
                    f"\n*... and {len(files_with_issues) - 10} more files with invalid examples*\n"
                )
        else:
            f.write("✅ All code examples are valid.\n")

        f.write("\n---\n\n")

    def _write_postman_collections(self, f, references: dict[str, Any], updates: dict[str, Any]):
        """Write Postman collections section"""
        f.write("## Postman Collections\n\n")

        invalid_collections = updates.get("invalid_collections", [])
        if invalid_collections:
            f.write(f"### Invalid Postman Collections ({len(invalid_collections)})\n\n")
            f.write("The following Postman collections have errors:\n\n")

            for collection in invalid_collections[:10]:  # Limit to first 10
                f.write(f"#### `{collection.get('collection_file', 'Unknown')}`\n\n")
                errors = collection.get("errors", [])
                if errors:
                    f.write("**Errors:**\n")
                    for error in errors[:5]:  # Limit to first 5 errors
                        f.write(f"- {error}\n")
                f.write("\n")

            if len(invalid_collections) > 10:
                f.write(f"\n*... and {len(invalid_collections) - 10} more invalid collections*\n")
        else:
            f.write("✅ All Postman collections are valid.\n")

        f.write("\n---\n\n")

    def _write_recommendations(self, f, updates: dict[str, Any]):
        """Write recommendations section"""
        f.write("## Recommendations\n\n")

        recommendations = updates.get("recommendations", [])
        if recommendations:
            # Sort by priority
            priority_order = {"high": 0, "medium": 1, "low": 2}
            recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 2))

            for rec in recommendations:
                priority = rec.get("priority", "low")
                category = rec.get("category", "general")
                description = rec.get("description", "")
                action = rec.get("action", "")

                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                f.write(
                    f"### {priority_emoji} **{priority.upper()} Priority**: {category.replace('_', ' ').title()}\n\n"
                )
                f.write(f"{description}\n\n")
                f.write(f"**Action:** {action}\n\n")
        else:
            f.write("✅ No critical issues identified. Documentation is in good shape!\n")

        f.write("\n---\n\n")

    def _write_footer(self, f):
        """Write report footer"""
        f.write("## Next Steps\n\n")
        f.write("1. Review the recommendations above\n")
        f.write("2. Prioritize fixes based on priority levels\n")
        f.write("3. Update documentation files with invalid examples\n")
        f.write("4. Fix Postman collections with invalid endpoints\n")
        f.write("5. Consolidate duplicate documentation where appropriate\n")
        f.write("6. Re-run audits to verify fixes\n\n")
        f.write("---\n\n")
        f.write("*This report was generated automatically from audit data.*\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate documentation impact analysis report")
    parser.add_argument(
        "--reports-dir",
        default="docs/api-audit",
        help="Directory containing audit report files (default: docs/api-audit)",
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/documentation-impact-analysis.md",
        help="Output markdown report file (default: docs/api-audit/documentation-impact-analysis.md)",
    )
    parser.add_argument("--base-path", default=".", help="Base path of the project (default: .)")

    args = parser.parse_args()

    try:
        generator = DocumentationImpactReportGenerator(
            audit_reports_dir=args.reports_dir, base_path=args.base_path
        )

        generator.generate_report(args.output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
