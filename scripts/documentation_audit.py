#!/usr/bin/env python3
"""
Comprehensive Documentation Audit Script
Performs a complete audit of all documentation files in the docs/ directory.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class DocumentationAuditor:
    """Comprehensive documentation auditor."""

    def __init__(self, docs_root: str):
        self.docs_root = Path(docs_root)
        self.categories = {
            "architecture": [],
            "api": [],
            "developer": [],
            "operational": [],
            "user": [],
            "other": [],
        }

        # Keywords to search for
        self.keyword_groups = {
            "contracts": ["contract", "ODPS", "open data product", "data product standard"],
            "odcs": ["ODCS", "open data contract", "data contract"],
            "workflows": [
                "workflow",
                "orchestration",
                "ProductCreationWorkflow",
                "workflow engine",
            ],
            "events": ["event", "event bus", "event-driven", "event publishing", "event consumer"],
            "websockets": ["websocket", "WebSocket", "real-time", "real time"],
            "marketplace": [
                "marketplace",
                "connector",
                "sync job",
                "marketplace integration",
                "GCP marketplace",
            ],
            "baas": ["BaaS", "baas platform", "backend as a service"],
            "odh": ["ODH", "open data hub", "data hub integration"],
            "model_serving": ["model serving", "ML model", "model deployment", "ML serving"],
        }

        # Usage guide patterns
        self.usage_guides = [
            "MARKETPLACE_USAGE.md",
            "BAAS_USAGE.md",
            "ODH_USAGE.md",
            "MODEL_SERVING_USAGE.md",
        ]

        self.file_analysis = {}
        self.references = defaultdict(list)

    def categorize_file(self, file_path: Path) -> str:
        """Categorize a file based on its path and name."""
        path_str = str(file_path.relative_to(self.docs_root)).lower()
        name_lower = file_path.name.lower()

        # Architecture files
        if any(
            term in name_lower for term in ["architecture", "design", "structure", "integration"]
        ):
            return "architecture"

        # API files
        if "api" in name_lower or "api-" in path_str or "api/" in path_str:
            return "api"

        # Developer files
        if any(
            term in name_lower
            for term in [
                "development",
                "developer",
                "onboarding",
                "testing",
                "code quality",
                "bug prevention",
            ]
        ):
            return "developer"

        # Operational files
        if any(
            term in name_lower
            for term in [
                "monitoring",
                "deployment",
                "kubernetes",
                "docker",
                "runbook",
                "troubleshooting",
                "infrastructure",
            ]
        ):
            return "operational"

        # User files
        if any(
            term in name_lower
            for term in ["user", "guide", "usage", "tutorial", "quick start", "features"]
        ):
            return "user"

        return "other"

    def analyze_file_content(self, file_path: Path) -> dict:
        """Analyze file content for keywords and references."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return {"error": str(e), "size": 0, "keywords_found": {}}

        analysis = {
            "size": len(content),
            "lines": len(content.splitlines()),
            "keywords_found": {},
            "has_usage_guide": False,
        }

        # Check for keywords
        content.lower()
        for group, keywords in self.keyword_groups.items():
            found_keywords = []
            for keyword in keywords:
                # Case-insensitive search with word boundaries
                pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b", re.IGNORECASE)
                matches = pattern.findall(content)
                if matches:
                    found_keywords.append(keyword)

            if found_keywords:
                analysis["keywords_found"][group] = found_keywords

        # Check if it's a usage guide
        for guide_pattern in self.usage_guides:
            if guide_pattern.lower() in file_path.name.upper():
                analysis["has_usage_guide"] = True
                break

        return analysis

    def audit(self) -> dict:
        """Perform comprehensive audit."""
        print(f"Starting documentation audit of {self.docs_root}...")

        # Find all documentation files
        all_files = []
        for ext in ["*.md", "*.yaml", "*.yml", "*.json", "*.py"]:
            all_files.extend(self.docs_root.rglob(ext))

        print(f"Found {len(all_files)} documentation files")

        # Analyze each file
        for file_path in all_files:
            # Skip files in deprecated-doc unless specifically needed
            if "deprecated-doc" in str(file_path):
                continue

            category = self.categorize_file(file_path)
            self.categories[category].append(str(file_path.relative_to(self.docs_root)))

            # Analyze content
            analysis = self.analyze_file_content(file_path)
            self.file_analysis[str(file_path.relative_to(self.docs_root))] = {
                "category": category,
                "path": str(file_path),
                **analysis,
            }

            # Track references
            for group, keywords in analysis.get("keywords_found", {}).items():
                self.references[group].append(
                    {
                        "file": str(file_path.relative_to(self.docs_root)),
                        "keywords": keywords,
                        "category": category,
                    }
                )

        return self.generate_report()

    def generate_report(self) -> dict:
        """Generate comprehensive audit report."""
        report = {
            "audit_date": datetime.now().isoformat(),
            "total_files": len(self.file_analysis),
            "categories": {cat: len(files) for cat, files in self.categories.items()},
            "files_by_category": self.categories,
            "keyword_references": {
                group: {"count": len(refs), "files": refs}
                for group, refs in self.references.items()
            },
            "usage_guides_found": [],
            "usage_guides_missing": [],
            "file_details": self.file_analysis,
        }

        # Check for usage guides
        found_guides = set()
        for file_path, details in self.file_analysis.items():
            if details.get("has_usage_guide"):
                found_guides.add(file_path)

        for guide in self.usage_guides:
            guide_lower = guide.lower()
            found = any(guide_lower in f.lower() for f in self.file_analysis.keys())
            if found:
                report["usage_guides_found"].append(guide)
            else:
                report["usage_guides_missing"].append(guide)

        return report

    def save_report(self, report: dict, output_path: str):
        """Save report to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON report
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Generate markdown summary
        md_output = output_file.with_suffix(".md")
        self.generate_markdown_report(report, md_output)

        print(f"Report saved to {output_file}")
        print(f"Markdown summary saved to {md_output}")

    def generate_markdown_report(self, report: dict, output_path: Path):
        """Generate human-readable markdown report."""
        md_lines = [
            "# Documentation Audit Report",
            "",
            f"**Audit Date**: {report['audit_date']}",
            f"**Total Files Analyzed**: {report['total_files']}",
            "",
            "## Summary",
            "",
            "### Files by Category",
            "",
        ]

        for category, count in report["categories"].items():
            md_lines.append(f"- **{category.title()}**: {count} files")

        md_lines.extend(["", "## Keyword References", ""])

        for group, data in report["keyword_references"].items():
            md_lines.append(f"### {group.title().replace('_', ' ')}")
            md_lines.append(f"- **Files referencing**: {data['count']}")
            md_lines.append("")
            for ref in data["files"][:10]:  # Show first 10
                md_lines.append(f"  - `{ref['file']}` ({ref['category']})")
            if len(data["files"]) > 10:
                md_lines.append(f"  - ... and {len(data['files']) - 10} more")
            md_lines.append("")

        md_lines.extend(["## Usage Guides", "", "### Found", ""])

        for guide in report["usage_guides_found"]:
            md_lines.append(f"- ✅ {guide}")

        md_lines.extend(["", "### Missing", ""])

        for guide in report["usage_guides_missing"]:
            md_lines.append(f"- ❌ {guide}")

        md_lines.extend(["", "## File Details", "", "### By Category", ""])

        for category, files in report["files_by_category"].items():
            if files:
                md_lines.append(f"### {category.title()}")
                md_lines.append("")
                for file_path in sorted(files)[:20]:  # Show first 20
                    md_lines.append(f"- `{file_path}`")
                if len(files) > 20:
                    md_lines.append(f"- ... and {len(files) - 20} more")
                md_lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))


def main():
    """Main execution."""
    docs_root = Path(__file__).parent.parent / "docs"
    output_dir = Path(__file__).parent.parent / "docs"

    auditor = DocumentationAuditor(str(docs_root))
    report = auditor.audit()

    output_path = output_dir / "documentation_audit_report.json"
    auditor.save_report(report, str(output_path))

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total files: {report['total_files']}")
    print("\nBy category:")
    for cat, count in report["categories"].items():
        print(f"  {cat}: {count}")
    print("\nKeyword references:")
    for group, data in report["keyword_references"].items():
        print(f"  {group}: {data['count']} files")
    print(f"\nUsage guides found: {len(report['usage_guides_found'])}")
    print(f"Usage guides missing: {len(report['usage_guides_missing'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
