#!/usr/bin/env python3
"""
API Gap Analysis Script

Comprehensively compares required APIs (from requirements matrix) with current APIs
(from inventory) to identify:
1. Missing endpoints
2. Incomplete endpoints (missing methods, parameters, fields)
3. Endpoints needing enhancements

This script:
- Parses requirements matrix and current inventory
- Performs systematic comparison
- Identifies gaps by priority
- Documents missing methods, parameters, and fields
- Generates comprehensive gap analysis report

Usage:
    python scripts/gap-analysis-api-requirements.py [--requirements REQUIREMENTS_FILE] [--inventory INVENTORY_FILE] [--output OUTPUT_FILE]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class APIEndpoint:
    """Represents an API endpoint."""

    endpoint: str
    method: str
    description: str = ""
    priority: str = "P3"
    category: str = "Uncategorized"
    request_schema: dict | None = None
    response_schema: dict | None = None
    query_params: list[str] = field(default_factory=list)
    path_params: list[str] = field(default_factory=list)
    auth_required: bool = True
    auth_type: str = "JWT/API Key"
    performance_target: str | None = None
    sources: list[str] = field(default_factory=list)

    def __hash__(self):
        return hash((self.endpoint, self.method))

    def __eq__(self, other):
        if not isinstance(other, APIEndpoint):
            return False
        return self.endpoint == other.endpoint and self.method == other.method


@dataclass
class Gap:
    """Represents a gap between required and current APIs."""

    endpoint: str
    method: str
    gap_type: (
        str  # missing, incomplete_method, incomplete_params, incomplete_fields, needs_enhancement
    )
    priority: str
    category: str
    description: str
    details: dict = field(default_factory=dict)
    impact: str = ""
    estimated_effort: str = ""
    sources: list[str] = field(default_factory=list)


class GapAnalyzer:
    """Analyzes gaps between required and current APIs."""

    def __init__(self):
        self.required_apis: dict[tuple[str, str], APIEndpoint] = {}
        self.current_apis: dict[tuple[str, str], APIEndpoint] = {}
        self.gaps: list[Gap] = []
        self.enhancements: list[Gap] = []

    def normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path for comparison."""
        # Remove trailing slashes
        endpoint = endpoint.rstrip("/")
        # Ensure starts with /api/v1
        if not endpoint.startswith("/api/v1"):
            if endpoint.startswith("/"):
                endpoint = f"/api/v1{endpoint}"
            else:
                endpoint = f"/api/v1/{endpoint}"
        # Normalize UUID placeholders
        endpoint = re.sub(r"<uuid:(\w+)>", r"{\1}", endpoint)
        endpoint = re.sub(r"<str:(\w+)>", r"{\1}", endpoint)
        endpoint = re.sub(r"<int:(\w+)>", r"{\1}", endpoint)
        endpoint = re.sub(r"\{id\}", "{id}", endpoint)
        return endpoint

    def parse_requirements_matrix(self, file_path: Path) -> dict[tuple[str, str], APIEndpoint]:
        """Parse requirements matrix markdown file."""
        apis = {}

        if not file_path.exists():
            print(f"⚠️  Requirements matrix not found: {file_path}")
            return apis

        content = file_path.read_text()

        # Parse markdown tables and detailed sections
        current_category = "Uncategorized"
        current_priority = "P3"

        # Look for category sections
        for line in content.split("\n"):
            line = line.strip()

            # Category headers
            if line.startswith("### ") and not line.startswith("#### "):
                category_match = re.match(r"### (.+?)(?:\s*\(|$)", line)
                if category_match:
                    current_category = category_match.group(1).strip()

            # Priority extraction from category
            if "**Priority**:" in line:
                priority_match = re.search(r"P[0-3]", line)
                if priority_match:
                    current_priority = priority_match.group(0)

            # Table rows with endpoints
            if "|" in line and (
                "GET" in line
                or "POST" in line
                or "PUT" in line
                or "DELETE" in line
                or "PATCH" in line
            ):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    method = parts[1].strip().upper()
                    endpoint = parts[2].strip().replace("`", "").replace("|", "").strip()

                    if endpoint and method and endpoint.startswith("/"):
                        endpoint = self.normalize_endpoint(endpoint)
                        description = parts[3].strip() if len(parts) > 3 else ""
                        priority = parts[4].strip() if len(parts) > 4 else current_priority

                        api = APIEndpoint(
                            endpoint=endpoint,
                            method=method,
                            description=description,
                            priority=priority,
                            category=current_category,
                        )
                        apis[(endpoint, method)] = api

            # Detailed endpoint documentation
            if line.startswith("##### ") and (
                "POST" in line
                or "GET" in line
                or "PUT" in line
                or "DELETE" in line
                or "PATCH" in line
            ):
                # Extract method and endpoint
                match = re.match(r"##### (GET|POST|PUT|DELETE|PATCH)\s+(.+)", line)
                if match:
                    method = match.group(1).upper()
                    endpoint = self.normalize_endpoint(match.group(2).strip())
                    key = (endpoint, method)

                    if key in apis:
                        api = apis[key]
                    else:
                        api = APIEndpoint(
                            endpoint=endpoint,
                            method=method,
                            category=current_category,
                            priority=current_priority,
                        )
                        apis[key] = api

                    # Parse details from following lines
                    in_section = True
                    current_section = None
                    continue

            # Parse detailed endpoint information
            if "in_section" in locals() and in_section:
                if line.startswith("**") and "**:" in line:
                    field_name = line.split("**")[1].split(":")[0].strip().lower()
                    field_value = line.split(":", 1)[1].strip() if ":" in line else ""

                    if field_name == "priority":
                        api.priority = field_value
                    elif field_name == "status":
                        # Skip status, it's about existence
                        pass
                    elif field_name == "sources":
                        api.sources = [s.strip() for s in field_value.split(",")]
                    elif field_name == "authentication":
                        api.auth_required = "required" in field_value.lower()
                    elif field_name == "performance target":
                        api.performance_target = field_value

        return apis

    def parse_inventory(self, file_path: Path) -> dict[tuple[str, str], APIEndpoint]:
        """Parse current API inventory markdown file."""
        apis = {}

        if not file_path.exists():
            print(f"⚠️  Inventory file not found: {file_path}")
            return apis

        content = file_path.read_text()

        current_category = "Uncategorized"

        # Parse markdown tables
        for line in content.split("\n"):
            line = line.strip()

            # Category headers
            if line.startswith("### ") and not line.startswith("#### "):
                category_match = re.match(r"### (.+?)(?:\s*\(|$)", line)
                if category_match:
                    current_category = category_match.group(1).strip()

            # Table rows
            if "|" in line and (
                "GET" in line
                or "POST" in line
                or "PUT" in line
                or "DELETE" in line
                or "PATCH" in line
            ):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    method = parts[0].strip().upper()
                    endpoint = parts[1].strip().replace("`", "").strip()

                    if endpoint and method:
                        endpoint = self.normalize_endpoint(endpoint)

                        api = APIEndpoint(
                            endpoint=endpoint,
                            method=method,
                            category=current_category,
                            priority="P3",  # Default, will be updated from requirements
                        )
                        apis[(endpoint, method)] = api

        return apis

    def analyze_gaps(self):
        """Analyze gaps between required and current APIs."""
        self.gaps = []
        self.enhancements = []

        # Find missing endpoints
        for (endpoint, method), required_api in self.required_apis.items():
            if (endpoint, method) not in self.current_apis:
                gap = Gap(
                    endpoint=endpoint,
                    method=method,
                    gap_type="missing",
                    priority=required_api.priority,
                    category=required_api.category,
                    description=f"Missing endpoint: {method} {endpoint}",
                    details={
                        "required_description": required_api.description,
                        "required_auth": required_api.auth_required,
                        "required_performance": required_api.performance_target,
                    },
                    impact=self._assess_impact(required_api),
                    estimated_effort=self._estimate_effort(required_api),
                    sources=required_api.sources,
                )
                self.gaps.append(gap)

        # Find incomplete endpoints (missing methods)
        for (endpoint, method), required_api in self.required_apis.items():
            if (endpoint, method) in self.current_apis:
                current_api = self.current_apis[(endpoint, method)]

                # Check for missing query parameters
                missing_query_params = set(required_api.query_params) - set(
                    current_api.query_params
                )
                if missing_query_params:
                    gap = Gap(
                        endpoint=endpoint,
                        method=method,
                        gap_type="incomplete_params",
                        priority=required_api.priority,
                        category=required_api.category,
                        description=f"Missing query parameters: {', '.join(missing_query_params)}",
                        details={
                            "missing_params": list(missing_query_params),
                            "existing_params": current_api.query_params,
                        },
                        impact="May limit filtering/sorting capabilities",
                        estimated_effort="Low (1-2 hours)",
                        sources=required_api.sources,
                    )
                    self.enhancements.append(gap)

                # Check for missing path parameters
                missing_path_params = set(required_api.path_params) - set(current_api.path_params)
                if missing_path_params:
                    gap = Gap(
                        endpoint=endpoint,
                        method=method,
                        gap_type="incomplete_params",
                        priority=required_api.priority,
                        category=required_api.category,
                        description=f"Missing path parameters: {', '.join(missing_path_params)}",
                        details={"missing_params": list(missing_path_params)},
                        impact="May limit endpoint functionality",
                        estimated_effort="Medium (2-4 hours)",
                        sources=required_api.sources,
                    )
                    self.enhancements.append(gap)

                # Check for missing request/response fields
                if required_api.request_schema and not current_api.request_schema:
                    gap = Gap(
                        endpoint=endpoint,
                        method=method,
                        gap_type="incomplete_fields",
                        priority=required_api.priority,
                        category=required_api.category,
                        description="Missing request schema documentation",
                        details={"required_schema": required_api.request_schema},
                        impact="May cause integration issues",
                        estimated_effort="Low (documentation)",
                        sources=required_api.sources,
                    )
                    self.enhancements.append(gap)

                # Check performance requirements
                if required_api.performance_target and not current_api.performance_target:
                    gap = Gap(
                        endpoint=endpoint,
                        method=method,
                        gap_type="needs_enhancement",
                        priority=required_api.priority,
                        category=required_api.category,
                        description=f"Performance target not met: {required_api.performance_target}",
                        details={"required_performance": required_api.performance_target},
                        impact="May cause user experience issues",
                        estimated_effort="Variable (optimization)",
                        sources=required_api.sources,
                    )
                    self.enhancements.append(gap)

    def _assess_impact(self, api: APIEndpoint) -> str:
        """Assess impact of missing API."""
        if api.priority == "P0":
            return "CRITICAL - Blocks frontend MVP implementation"
        elif api.priority == "P1":
            return "HIGH - Blocks core features"
        elif api.priority == "P2":
            return "MEDIUM - Blocks advanced features"
        else:
            return "LOW - Blocks strategic differentiators"

    def _estimate_effort(self, api: APIEndpoint) -> str:
        """Estimate effort to implement API."""
        if api.priority == "P0":
            return "High (1-3 days)"
        elif api.priority == "P1":
            return "Medium (1-2 days)"
        elif api.priority == "P2":
            return "Medium (2-5 days)"
        else:
            return "Low-Medium (3-7 days)"

    def generate_gap_analysis(self, output_path: Path):
        """Generate comprehensive gap analysis report."""
        lines = []

        # Header
        lines.append("# API Gap Analysis")
        lines.append("")
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}")
        lines.append("**Task**: 0.3.1 - Compare current vs required APIs")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append("This document compares required APIs (from consolidated requirements matrix)")
        lines.append("with current APIs (from codebase inventory) to identify gaps.")
        lines.append("")
        lines.append(f"- **Required APIs**: {len(self.required_apis)}")
        lines.append(f"- **Current APIs**: {len(self.current_apis)}")
        lines.append(
            f"- **Missing Endpoints**: {len([g for g in self.gaps if g.gap_type == 'missing'])}"
        )
        lines.append(
            f"- **Incomplete Endpoints**: {len([g for g in self.enhancements if 'incomplete' in g.gap_type])}"
        )
        lines.append(
            f"- **Endpoints Needing Enhancements**: {len([g for g in self.enhancements if g.gap_type == 'needs_enhancement'])}"
        )
        lines.append("")

        # Statistics
        lines.append("## Statistics")
        lines.append("")

        # By priority
        gaps_by_priority = defaultdict(int)
        for gap in self.gaps:
            gaps_by_priority[gap.priority] += 1

        lines.append("### Gaps by Priority")
        lines.append("")
        for priority in ["P0", "P1", "P2", "P3"]:
            count = gaps_by_priority.get(priority, 0)
            lines.append(f"- **{priority}**: {count} gaps")
        lines.append("")

        # By gap type
        gaps_by_type = defaultdict(int)
        for gap in self.gaps + self.enhancements:
            gaps_by_type[gap.gap_type] += 1

        lines.append("### Gaps by Type")
        lines.append("")
        for gap_type, count in sorted(gaps_by_type.items()):
            lines.append(f"- **{gap_type}**: {count}")
        lines.append("")

        # By category
        gaps_by_category = defaultdict(int)
        for gap in self.gaps + self.enhancements:
            gaps_by_category[gap.category] += 1

        lines.append("### Gaps by Category")
        lines.append("")
        for category, count in sorted(gaps_by_category.items(), key=lambda x: -x[1]):
            lines.append(f"- **{category}**: {count} gaps")
        lines.append("")

        # Missing Endpoints
        missing = [g for g in self.gaps if g.gap_type == "missing"]
        if missing:
            lines.append("## Missing Endpoints")
            lines.append("")
            lines.append("Endpoints that are required but not currently implemented.")
            lines.append("")

            # Group by priority
            for priority in ["P0", "P1", "P2", "P3"]:
                priority_missing = [g for g in missing if g.priority == priority]
                if priority_missing:
                    lines.append(
                        f"### {priority} - {'Critical' if priority == 'P0' else 'High' if priority == 'P1' else 'Medium' if priority == 'P2' else 'Low'} Priority"
                    )
                    lines.append("")
                    lines.append("| Endpoint | Method | Category | Impact | Effort | Sources |")
                    lines.append("|----------|--------|----------|--------|--------|---------|")

                    for gap in sorted(priority_missing, key=lambda x: x.endpoint):
                        sources_str = ", ".join(gap.sources[:2]) if gap.sources else "N/A"
                        if len(gap.sources) > 2:
                            sources_str += f" (+{len(gap.sources) - 2} more)"

                        lines.append(
                            f"| `{gap.endpoint}` | {gap.method} | {gap.category} | "
                            f"{gap.impact[:50]}... | {gap.estimated_effort} | {sources_str} |"
                        )
                    lines.append("")

                    # Detailed documentation
                    for gap in priority_missing:
                        lines.append(f"#### {gap.method} {gap.endpoint}")
                        lines.append("")
                        lines.append(f"**Description**: {gap.description}")
                        lines.append(f"**Priority**: {gap.priority}")
                        lines.append(f"**Category**: {gap.category}")
                        lines.append(f"**Impact**: {gap.impact}")
                        lines.append(f"**Estimated Effort**: {gap.estimated_effort}")
                        lines.append("")
                        if gap.sources:
                            lines.append(f"**Sources**: {', '.join(gap.sources)}")
                            lines.append("")
                        if gap.details:
                            lines.append("**Details**:")
                            for key, value in gap.details.items():
                                if isinstance(value, (dict, list)):
                                    lines.append(f"- {key}: {json.dumps(value, indent=2)}")
                                else:
                                    lines.append(f"- {key}: {value}")
                            lines.append("")
                        lines.append("---")
                        lines.append("")

        # Incomplete Endpoints
        incomplete = [g for g in self.enhancements if "incomplete" in g.gap_type]
        if incomplete:
            lines.append("## Incomplete Endpoints")
            lines.append("")
            lines.append("Endpoints that exist but are missing methods, parameters, or fields.")
            lines.append("")

            lines.append("| Endpoint | Method | Gap Type | Missing Items | Impact | Effort |")
            lines.append("|----------|--------|----------|---------------|--------|--------|")

            for gap in sorted(incomplete, key=lambda x: (x.priority, x.endpoint)):
                missing_items = gap.details.get("missing_params", [])
                if not missing_items:
                    missing_items = gap.details.get("missing_fields", [])

                missing_str = ", ".join(missing_items[:3]) if missing_items else "See details"
                if len(missing_items) > 3:
                    missing_str += f" (+{len(missing_items) - 3} more)"

                lines.append(
                    f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                    f"{missing_str} | {gap.impact} | {gap.estimated_effort} |"
                )
            lines.append("")

        # Endpoints Needing Enhancements
        enhancements = [g for g in self.enhancements if g.gap_type == "needs_enhancement"]
        if enhancements:
            lines.append("## Endpoints Needing Enhancements")
            lines.append("")
            lines.append(
                "Endpoints that exist but need improvements (performance, features, etc.)."
            )
            lines.append("")

            lines.append("| Endpoint | Method | Enhancement Needed | Impact | Effort |")
            lines.append("|----------|--------|---------------------|--------|--------|")

            for gap in sorted(enhancements, key=lambda x: (x.priority, x.endpoint)):
                enhancement = gap.description
                lines.append(
                    f"| `{gap.endpoint}` | {gap.method} | {enhancement} | "
                    f"{gap.impact} | {gap.estimated_effort} |"
                )
            lines.append("")

        # Coverage Analysis
        lines.append("## Coverage Analysis")
        lines.append("")

        # Calculate coverage by category
        lines.append("### Coverage by Category")
        lines.append("")
        lines.append("| Category | Required | Current | Missing | Coverage % |")
        lines.append("|----------|----------|---------|---------|------------|")

        categories = set()
        for api in self.required_apis.values():
            categories.add(api.category)
        for api in self.current_apis.values():
            categories.add(api.category)

        for category in sorted(categories):
            required = [a for a in self.required_apis.values() if a.category == category]
            current = [a for a in self.current_apis.values() if a.category == category]
            missing = [g for g in self.gaps if g.category == category and g.gap_type == "missing"]

            required_count = len(required)
            current_count = len(current)
            missing_count = len(missing)

            if required_count > 0:
                coverage = ((required_count - missing_count) / required_count) * 100
                lines.append(
                    f"| {category} | {required_count} | {current_count} | {missing_count} | {coverage:.1f}% |"
                )
        lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")

        p0_missing = [g for g in self.gaps if g.gap_type == "missing" and g.priority == "P0"]
        if p0_missing:
            lines.append("### Immediate Actions (P0 - Critical)")
            lines.append("")
            lines.append("These endpoints must be implemented before frontend MVP:")
            lines.append("")
            for gap in p0_missing:
                lines.append(f"- **{gap.method} {gap.endpoint}**")
                lines.append(f"  - Impact: {gap.impact}")
                lines.append(f"  - Effort: {gap.estimated_effort}")
                lines.append(f"  - Sources: {', '.join(gap.sources[:3])}")
                lines.append("")

        p1_missing = [g for g in self.gaps if g.gap_type == "missing" and g.priority == "P1"]
        if p1_missing:
            lines.append("### High Priority Actions (P1)")
            lines.append("")
            lines.append("These endpoints should be implemented for core features:")
            lines.append("")
            for gap in p1_missing[:10]:  # Top 10
                lines.append(f"- **{gap.method} {gap.endpoint}** - {gap.impact}")
                lines.append("")

        # Write to file
        output_path.write_text("\n".join(lines))
        print(f"✅ Gap analysis saved to {output_path}")

    def export_json(self, output_path: Path):
        """Export gap analysis as JSON."""
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "required_apis": len(self.required_apis),
                "current_apis": len(self.current_apis),
                "missing_endpoints": len([g for g in self.gaps if g.gap_type == "missing"]),
                "incomplete_endpoints": len(
                    [g for g in self.enhancements if "incomplete" in g.gap_type]
                ),
                "enhancements_needed": len(
                    [g for g in self.enhancements if g.gap_type == "needs_enhancement"]
                ),
            },
            "gaps": [asdict(g) for g in self.gaps],
            "enhancements": [asdict(g) for g in self.enhancements],
        }

        output_path.write_text(json.dumps(data, indent=2))
        print(f"✅ JSON gap analysis saved to {output_path}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Analyze gaps between required and current APIs")
    parser.add_argument(
        "--requirements",
        default="docs/api-audit/api-requirements-matrix-consolidated.md",
        help="Path to requirements matrix file",
    )
    parser.add_argument(
        "--inventory",
        default="docs/api-audit/current-api-inventory.md",
        help="Path to current API inventory file",
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/gap-analysis.md",
        help="Path to output gap analysis file",
    )

    args = parser.parse_args()

    analyzer = GapAnalyzer()

    # Parse requirements
    print("📋 Parsing requirements matrix...")
    requirements_path = Path(args.requirements)
    analyzer.required_apis = analyzer.parse_requirements_matrix(requirements_path)
    print(f"✅ Found {len(analyzer.required_apis)} required APIs")

    # Parse inventory
    print("📋 Parsing current API inventory...")
    inventory_path = Path(args.inventory)
    analyzer.current_apis = analyzer.parse_inventory(inventory_path)
    print(f"✅ Found {len(analyzer.current_apis)} current APIs")

    # Analyze gaps
    print("🔍 Analyzing gaps...")
    analyzer.analyze_gaps()

    missing = [g for g in analyzer.gaps if g.gap_type == "missing"]
    incomplete = [g for g in analyzer.enhancements if "incomplete" in g.gap_type]
    enhancements = [g for g in analyzer.enhancements if g.gap_type == "needs_enhancement"]

    print(f"✅ Found {len(missing)} missing endpoints")
    print(f"✅ Found {len(incomplete)} incomplete endpoints")
    print(f"✅ Found {len(enhancements)} endpoints needing enhancements")

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    analyzer.generate_gap_analysis(output_path)

    # Export JSON
    json_path = output_path.with_suffix(".json")
    analyzer.export_json(json_path)

    # Print summary
    print("\n" + "=" * 60)
    print("GAP ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Required APIs: {len(analyzer.required_apis)}")
    print(f"Current APIs: {len(analyzer.current_apis)}")
    print(f"Missing: {len(missing)}")
    print(f"Incomplete: {len(incomplete)}")
    print(f"Enhancements: {len(enhancements)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
