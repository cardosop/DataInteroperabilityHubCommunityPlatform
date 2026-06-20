#!/usr/bin/env python3
"""
Gap Categorization by Priority Script

Categorizes API gaps by priority (P0/P1/P2/P3) based on frontend MVP timeline
and impact on implementation phases.

This script:
- Reads gap analysis results
- Categorizes gaps by priority categories
- Organizes gaps by implementation phase
- Generates prioritized gap categorization document
- Updates gap analysis file with categorization

Usage:
    python scripts/categorize-gaps-by-priority.py [--gap-analysis GAP_ANALYSIS_FILE] [--output OUTPUT_FILE]
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
class CategorizedGap:
    """Represents a gap categorized by priority."""

    endpoint: str
    method: str
    gap_type: str  # missing, incomplete, enhancement
    priority: str  # P0, P1, P2, P3
    category: str  # Authentication, Asset Management, etc.
    priority_category: str  # P0-Auth, P0-Core-CRUD, P1-Credentials, etc.
    phase: str  # Phase 0, Phase 1, Phase 2, Phase 3
    weeks: str  # Weeks 1-16, Weeks 5-24, etc.
    description: str
    impact: str
    estimated_effort: str
    sources: list[str] = field(default_factory=list)


class GapCategorizer:
    """Categorizes gaps by priority and implementation phase."""

    # Priority category mappings
    P0_CATEGORIES = {
        "Authentication": [
            "auth",
            "login",
            "register",
            "logout",
            "password-reset",
            "api-keys",
            "me",
        ],
        "Core CRUD": ["assets", "contracts", "datasets"],
        "File Operations": ["files", "upload", "download", "chunks"],
        "Job Status": ["jobs", "status", "progress", "cancel"],
        "Search": ["search", "query", "suggestions"],
    }

    P1_CATEGORIES = {
        "Credential Management": ["credentials", "credential", "api-key", "rotate", "test"],
        "Marketplace": ["marketplace", "listings", "purchase", "download"],
        "Compliance": ["compliance", "runs", "scans", "violations"],
        "Data Quality": ["dq", "quality", "checks", "runs"],
    }

    P2_CATEGORIES = {
        "AI/ML": [
            "ai",
            "ml",
            "natural-language",
            "schema-matching",
            "recommendations",
            "classification",
        ],
        "Transformation": ["transformation", "pipeline", "transform", "etl"],
        "Social Features": ["social", "ratings", "reviews", "comments", "communities"],
    }

    P3_CATEGORIES = {
        "Data Mesh": ["mesh", "domain", "federated", "topology"],
        "Virtualization": ["virtual", "virtualization", "federated-query"],
        "Advanced Marketplace": ["advanced-marketplace", "preview", "pricing", "usage-based"],
        "Developer Experience": ["developer", "sdk", "cli", "plugin", "portal"],
    }

    def __init__(self):
        self.gaps: list[CategorizedGap] = []
        self.categorized_gaps: dict[str, list[CategorizedGap]] = defaultdict(list)

    def parse_gap_analysis(self, file_path: Path) -> list[dict]:
        """Parse gap analysis markdown file."""
        gaps = []

        if not file_path.exists():
            print(f"⚠️  Gap analysis file not found: {file_path}")
            return gaps

        content = file_path.read_text()

        current_section = None
        current_gap = None

        for line in content.split("\n"):
            line = line.strip()

            # Section headers
            if line.startswith("## "):
                current_section = line.replace("## ", "").strip()
                current_gap = None

            # Missing endpoints
            if current_section == "Missing Endpoints":
                if line.startswith("#### "):
                    # Extract endpoint and method
                    match = re.match(r"#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)", line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            "endpoint": endpoint,
                            "method": method,
                            "gap_type": "missing",
                            "section": "Missing Endpoints",
                        }
                        gaps.append(current_gap)
                elif current_gap and line.startswith("**"):
                    # Parse gap details
                    if "**Priority**:" in line:
                        current_gap["priority"] = (
                            re.search(r"P[0-3]", line).group(0)
                            if re.search(r"P[0-3]", line)
                            else "P3"
                        )
                    elif "**Category**:" in line:
                        current_gap["category"] = line.split("**Category**:")[1].strip()
                    elif "**Impact**:" in line:
                        current_gap["impact"] = line.split("**Impact**:")[1].strip()
                    elif "**Estimated Effort**:" in line:
                        current_gap["estimated_effort"] = line.split("**Estimated Effort**:")[
                            1
                        ].strip()

            # Incomplete endpoints
            elif current_section == "Incomplete Endpoints":
                if line.startswith("#### "):
                    match = re.match(r"#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)", line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            "endpoint": endpoint,
                            "method": method,
                            "gap_type": "incomplete",
                            "section": "Incomplete Endpoints",
                        }
                        gaps.append(current_gap)
                elif current_gap and line.startswith("**"):
                    if "**Priority**:" in line:
                        current_gap["priority"] = (
                            re.search(r"P[0-3]", line).group(0)
                            if re.search(r"P[0-3]", line)
                            else "P3"
                        )
                    elif "**Category**:" in line:
                        current_gap["category"] = line.split("**Category**:")[1].strip()
                    elif "**Impact**:" in line:
                        current_gap["impact"] = line.split("**Impact**:")[1].strip()
                    elif "**Estimated Effort**:" in line:
                        current_gap["estimated_effort"] = line.split("**Estimated Effort**:")[
                            1
                        ].strip()

            # Enhancements
            elif current_section == "Endpoints Needing Enhancements":
                if line.startswith("#### "):
                    match = re.match(r"#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)", line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            "endpoint": endpoint,
                            "method": method,
                            "gap_type": "enhancement",
                            "section": "Endpoints Needing Enhancements",
                        }
                        gaps.append(current_gap)
                elif current_gap and line.startswith("**"):
                    if "**Priority**:" in line:
                        current_gap["priority"] = (
                            re.search(r"P[0-3]", line).group(0)
                            if re.search(r"P[0-3]", line)
                            else "P3"
                        )
                    elif "**Category**:" in line:
                        current_gap["category"] = line.split("**Category**:")[1].strip()
                    elif "**Impact**:" in line:
                        current_gap["impact"] = line.split("**Impact**:")[1].strip()
                    elif "**Estimated Effort**:" in line:
                        current_gap["estimated_effort"] = line.split("**Estimated Effort**:")[
                            1
                        ].strip()

        return gaps

    def categorize_gap(self, gap: dict) -> CategorizedGap:
        """Categorize a gap by priority category."""
        endpoint_lower = gap["endpoint"].lower()
        category = gap.get("category", "Uncategorized")
        priority = gap.get("priority", "P3")

        # Determine priority category
        priority_category = None
        phase = None
        weeks = None

        # Check P0 categories
        if priority == "P0":
            for cat_name, keywords in self.P0_CATEGORIES.items():
                if any(kw in endpoint_lower or kw in category.lower() for kw in keywords):
                    priority_category = f"P0-{cat_name}"
                    phase = "Phase 0"
                    weeks = "Weeks 0-4 (Before Frontend MVP)"
                    break

        # Check P1 categories
        if not priority_category and priority == "P1":
            for cat_name, keywords in self.P1_CATEGORIES.items():
                if any(kw in endpoint_lower or kw in category.lower() for kw in keywords):
                    priority_category = f"P1-{cat_name}"
                    phase = "Phase 1"
                    weeks = "Weeks 5-24 (Core Features)"
                    break

        # Check P2 categories
        if not priority_category and priority == "P2":
            for cat_name, keywords in self.P2_CATEGORIES.items():
                if any(kw in endpoint_lower or kw in category.lower() for kw in keywords):
                    priority_category = f"P2-{cat_name}"
                    phase = "Phase 2"
                    weeks = "Weeks 25-40 (Advanced Features)"
                    break

        # Check P3 categories
        if not priority_category and priority == "P3":
            for cat_name, keywords in self.P3_CATEGORIES.items():
                if any(kw in endpoint_lower or kw in category.lower() for kw in keywords):
                    priority_category = f"P3-{cat_name}"
                    phase = "Phase 3"
                    weeks = "Weeks 41-64 (Strategic Differentiators)"
                    break

        # Default categorization
        if not priority_category:
            if priority == "P0":
                priority_category = "P0-Core"
                phase = "Phase 0"
                weeks = "Weeks 0-4 (Before Frontend MVP)"
            elif priority == "P1":
                priority_category = "P1-Feature"
                phase = "Phase 1"
                weeks = "Weeks 5-24 (Core Features)"
            elif priority == "P2":
                priority_category = "P2-Advanced"
                phase = "Phase 2"
                weeks = "Weeks 25-40 (Advanced Features)"
            else:
                priority_category = "P3-Strategic"
                phase = "Phase 3"
                weeks = "Weeks 41-64 (Strategic Differentiators)"

        return CategorizedGap(
            endpoint=gap["endpoint"],
            method=gap["method"],
            gap_type=gap["gap_type"],
            priority=priority,
            category=category,
            priority_category=priority_category,
            phase=phase,
            weeks=weeks,
            description=gap.get("description", ""),
            impact=gap.get("impact", ""),
            estimated_effort=gap.get("estimated_effort", ""),
            sources=gap.get("sources", []),
        )

    def categorize_all_gaps(self, gaps: list[dict]):
        """Categorize all gaps."""
        for gap in gaps:
            categorized = self.categorize_gap(gap)
            self.gaps.append(categorized)
            self.categorized_gaps[categorized.priority_category].append(categorized)

    def generate_categorization_report(self, output_path: Path):
        """Generate prioritized gap categorization report."""
        lines = []

        # Header
        lines.append("# API Gap Categorization by Priority")
        lines.append("")
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}")
        lines.append("**Task**: 0.3.2 - Categorize gaps by priority")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append("This document categorizes all API gaps by priority based on:")
        lines.append("- Frontend MVP timeline (Weeks 1-16)")
        lines.append("- Impact on implementation phases")
        lines.append("- Feature dependencies")
        lines.append("")
        lines.append(f"**Total Gaps**: {len(self.gaps)}")
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

        # By priority category
        lines.append("### Gaps by Priority Category")
        lines.append("")
        for priority in ["P0", "P1", "P2", "P3"]:
            priority_gaps = [g for g in self.gaps if g.priority == priority]
            if priority_gaps:
                lines.append(
                    f"#### {priority} - {'Critical' if priority == 'P0' else 'High' if priority == 'P1' else 'Medium' if priority == 'P2' else 'Low'} Priority"
                )
                lines.append("")
                for cat_name in sorted(set(g.priority_category for g in priority_gaps)):
                    cat_gaps = [g for g in priority_gaps if g.priority_category == cat_name]
                    lines.append(f"- **{cat_name}**: {len(cat_gaps)} gaps")
                lines.append("")

        # P0 - Critical Priority
        p0_gaps = [g for g in self.gaps if g.priority == "P0"]
        if p0_gaps:
            lines.append("## P0 - Critical Priority")
            lines.append("")
            lines.append("**Blocks**: Frontend MVP (Weeks 1-16)")
            lines.append("**Timeline**: Weeks 0-4 (Before Frontend MVP)")
            lines.append("")

            # Authentication APIs
            auth_gaps = [g for g in p0_gaps if "Auth" in g.priority_category]
            if auth_gaps:
                lines.append("### Authentication APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(auth_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Core CRUD APIs
            crud_gaps = [g for g in p0_gaps if "CRUD" in g.priority_category]
            if crud_gaps:
                lines.append("### Core CRUD APIs (Assets, Contracts, Datasets)")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(crud_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # File upload/download
            file_gaps = [g for g in p0_gaps if "File" in g.priority_category]
            if file_gaps:
                lines.append("### File Upload/Download APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(file_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Job status APIs
            job_gaps = [g for g in p0_gaps if "Job" in g.priority_category]
            if job_gaps:
                lines.append("### Job Status APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(job_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Search APIs
            search_gaps = [g for g in p0_gaps if "Search" in g.priority_category]
            if search_gaps:
                lines.append("### Search APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(search_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

        # P1 - High Priority
        p1_gaps = [g for g in self.gaps if g.priority == "P1"]
        if p1_gaps:
            lines.append("## P1 - High Priority")
            lines.append("")
            lines.append("**Blocks**: Core features (Weeks 5-24)")
            lines.append("**Timeline**: Weeks 5-24 (Core Features)")
            lines.append("")

            # Credential management APIs
            cred_gaps = [g for g in p1_gaps if "Credential" in g.priority_category]
            if cred_gaps:
                lines.append("### Credential Management APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(cred_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Marketplace APIs
            marketplace_gaps = [g for g in p1_gaps if "Marketplace" in g.priority_category]
            if marketplace_gaps:
                lines.append("### Marketplace APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(marketplace_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Compliance APIs
            compliance_gaps = [g for g in p1_gaps if "Compliance" in g.priority_category]
            if compliance_gaps:
                lines.append("### Compliance APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(compliance_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Data quality APIs
            dq_gaps = [g for g in p1_gaps if "Quality" in g.priority_category]
            if dq_gaps:
                lines.append("### Data Quality APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(dq_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

        # P2 - Medium Priority
        p2_gaps = [g for g in self.gaps if g.priority == "P2"]
        if p2_gaps:
            lines.append("## P2 - Medium Priority")
            lines.append("")
            lines.append("**Blocks**: Advanced features (Weeks 25-40)")
            lines.append("**Timeline**: Weeks 25-40 (Advanced Features)")
            lines.append("")

            # AI/ML APIs
            ai_gaps = [
                g for g in p2_gaps if "AI" in g.priority_category or "ML" in g.priority_category
            ]
            if ai_gaps:
                lines.append("### AI/ML APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(ai_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Transformation APIs
            transform_gaps = [g for g in p2_gaps if "Transformation" in g.priority_category]
            if transform_gaps:
                lines.append("### Transformation APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(transform_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Social feature APIs
            social_gaps = [g for g in p2_gaps if "Social" in g.priority_category]
            if social_gaps:
                lines.append("### Social Feature APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(social_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

        # P3 - Low Priority
        p3_gaps = [g for g in self.gaps if g.priority == "P3"]
        if p3_gaps:
            lines.append("## P3 - Low Priority")
            lines.append("")
            lines.append("**Blocks**: Strategic differentiators (Weeks 41-64)")
            lines.append("**Timeline**: Weeks 41-64 (Strategic Differentiators)")
            lines.append("")

            # Data mesh APIs
            mesh_gaps = [g for g in p3_gaps if "Mesh" in g.priority_category]
            if mesh_gaps:
                lines.append("### Data Mesh APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(mesh_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Virtualization APIs
            virt_gaps = [g for g in p3_gaps if "Virtualization" in g.priority_category]
            if virt_gaps:
                lines.append("### Virtualization APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(virt_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Advanced marketplace APIs
            adv_marketplace_gaps = [
                g for g in p3_gaps if "Advanced Marketplace" in g.priority_category
            ]
            if adv_marketplace_gaps:
                lines.append("### Advanced Marketplace APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(adv_marketplace_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

            # Developer experience APIs
            dev_gaps = [g for g in p3_gaps if "Developer" in g.priority_category]
            if dev_gaps:
                lines.append("### Developer Experience APIs")
                lines.append("")
                lines.append("| Endpoint | Method | Gap Type | Impact | Effort |")
                lines.append("|----------|--------|----------|--------|--------|")
                for gap in sorted(dev_gaps, key=lambda x: x.endpoint):
                    lines.append(
                        f"| `{gap.endpoint}` | {gap.method} | {gap.gap_type} | "
                        f"{gap.impact[:50]}... | {gap.estimated_effort} |"
                    )
                lines.append("")

        # Implementation Timeline
        lines.append("## Implementation Timeline")
        lines.append("")
        lines.append("### Phase 0 (Weeks 0-4) - Before Frontend MVP")
        lines.append("")
        p0_list = [g for g in self.gaps if g.priority == "P0"]
        lines.append(f"**Total Gaps**: {len(p0_list)}")
        lines.append("")
        lines.append("**Must Complete** (Blockers):")
        missing_p0 = [g for g in p0_list if g.gap_type == "missing"]
        for gap in missing_p0:
            lines.append(f"- ✅ {gap.method} `{gap.endpoint}` - {gap.impact}")
        lines.append("")
        lines.append("**Should Complete** (High Value):")
        incomplete_p0 = [g for g in p0_list if g.gap_type == "incomplete"]
        for gap in incomplete_p0[:5]:  # Top 5
            lines.append(f"- ⚠️ {gap.method} `{gap.endpoint}` - {gap.impact[:60]}...")
        lines.append("")

        lines.append("### Phase 1 (Weeks 5-24) - Core Features")
        lines.append("")
        p1_list = [g for g in self.gaps if g.priority == "P1"]
        lines.append(f"**Total Gaps**: {len(p1_list)}")
        lines.append("")
        lines.append("**Categories**:")
        for cat_name in sorted(set(g.priority_category for g in p1_list)):
            cat_count = len([g for g in p1_list if g.priority_category == cat_name])
            lines.append(f"- {cat_name}: {cat_count} gaps")
        lines.append("")

        lines.append("### Phase 2 (Weeks 25-40) - Advanced Features")
        lines.append("")
        p2_list = [g for g in self.gaps if g.priority == "P2"]
        lines.append(f"**Total Gaps**: {len(p2_list)}")
        lines.append("")
        lines.append("**Categories**:")
        for cat_name in sorted(set(g.priority_category for g in p2_list)):
            cat_count = len([g for g in p2_list if g.priority_category == cat_name])
            lines.append(f"- {cat_name}: {cat_count} gaps")
        lines.append("")

        lines.append("### Phase 3 (Weeks 41-64) - Strategic Differentiators")
        lines.append("")
        p3_list = [g for g in self.gaps if g.priority == "P3"]
        lines.append(f"**Total Gaps**: {len(p3_list)}")
        lines.append("")
        lines.append("**Categories**:")
        for cat_name in sorted(set(g.priority_category for g in p3_list)):
            cat_count = len([g for g in p3_list if g.priority_category == cat_name])
            lines.append(f"- {cat_name}: {cat_count} gaps")
        lines.append("")

        # Summary Table
        lines.append("## Summary by Priority Category")
        lines.append("")
        lines.append("| Priority Category | Phase | Weeks | Gap Count |")
        lines.append("|-------------------|-------|-------|-----------|")

        for priority in ["P0", "P1", "P2", "P3"]:
            priority_gaps = [g for g in self.gaps if g.priority == priority]
            if priority_gaps:
                for cat_name in sorted(set(g.priority_category for g in priority_gaps)):
                    cat_gaps = [g for g in priority_gaps if g.priority_category == cat_name]
                    phase = cat_gaps[0].phase
                    weeks = cat_gaps[0].weeks
                    lines.append(f"| {cat_name} | {phase} | {weeks} | {len(cat_gaps)} |")
        lines.append("")

        # Write to file
        output_path.write_text("\n".join(lines))
        print(f"✅ Gap categorization saved to {output_path}")

    def export_json(self, output_path: Path):
        """Export categorization as JSON."""
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_gaps": len(self.gaps),
            "gaps_by_priority": {
                "P0": len([g for g in self.gaps if g.priority == "P0"]),
                "P1": len([g for g in self.gaps if g.priority == "P1"]),
                "P2": len([g for g in self.gaps if g.priority == "P2"]),
                "P3": len([g for g in self.gaps if g.priority == "P3"]),
            },
            "categorized_gaps": {
                cat: [asdict(g) for g in gaps] for cat, gaps in self.categorized_gaps.items()
            },
            "gaps": [asdict(g) for g in self.gaps],
        }

        output_path.write_text(json.dumps(data, indent=2))
        print(f"✅ JSON categorization saved to {output_path}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Categorize API gaps by priority")
    parser.add_argument(
        "--gap-analysis", default="docs/api-audit/gap-analysis.md", help="Path to gap analysis file"
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/gap-categorization-by-priority.md",
        help="Path to output categorization file",
    )

    args = parser.parse_args()

    categorizer = GapCategorizer()

    # Parse gap analysis
    print("📋 Parsing gap analysis...")
    gap_analysis_path = Path(args.gap_analysis)
    gaps = categorizer.parse_gap_analysis(gap_analysis_path)
    print(f"✅ Found {len(gaps)} gaps")

    # Categorize gaps
    print("🔍 Categorizing gaps by priority...")
    categorizer.categorize_all_gaps(gaps)

    # Print summary
    print("\n" + "=" * 60)
    print("GAP CATEGORIZATION SUMMARY")
    print("=" * 60)
    for priority in ["P0", "P1", "P2", "P3"]:
        priority_gaps = [g for g in categorizer.gaps if g.priority == priority]
        print(f"{priority}: {len(priority_gaps)} gaps")
        for cat_name in sorted(set(g.priority_category for g in priority_gaps)):
            cat_count = len([g for g in priority_gaps if g.priority_category == cat_name])
            print(f"  - {cat_name}: {cat_count}")
    print("=" * 60)

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    categorizer.generate_categorization_report(output_path)

    # Export JSON
    json_path = output_path.with_suffix(".json")
    categorizer.export_json(json_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
