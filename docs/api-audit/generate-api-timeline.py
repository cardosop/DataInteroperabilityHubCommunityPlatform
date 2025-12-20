#!/usr/bin/env python3
"""
Generate API Development Timeline

This script creates a comprehensive timeline for API development based on:
- Priority (P0/P1/P2/P3)
- Dependencies
- Effort estimates
- Parallel work opportunities
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class APITimelineItem:
    method: str
    path: str
    priority: str
    category: str
    gap_type: str
    effort_hours: float
    effort_days: float
    dependencies: List[str] = field(default_factory=list)
    phase: Optional[int] = None
    week_start: Optional[int] = None
    week_end: Optional[int] = None
    parallel_group: Optional[int] = None

class APITimelineGenerator:
    def __init__(self):
        self.apis: Dict[str, APITimelineItem] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.phases = {
            0: {"weeks": (0, 4), "priority": "P0", "name": "Foundation (P0 - Critical)"},
            1: {"weeks": (5, 8), "priority": "P1", "name": "Core Features (P1 - High Priority)"},
            2: {"weeks": (9, 20), "priority": "P2", "name": "Enhanced Features (P2 - Medium Priority)"},
            3: {"weeks": (21, 40), "priority": "P3", "name": "Strategic Features (P3 - Low Priority)"},
        }

    def load_backlog(self, file_path: str):
        """Load APIs from backlog file using simpler parsing."""
        print(f"Loading backlog from {file_path}...", file=__import__('sys').stderr)
        content = Path(file_path).read_text()
        
        # Split by API sections (#### number. METHOD)
        sections = re.split(r'#### \d+\.\s+(GET|POST|PUT|PATCH|DELETE)\s+`(/api/v1/[^`]+)`', content)
        
        # Process each section
        for i in range(1, len(sections), 3):
            if i + 2 >= len(sections):
                break
                
            method = sections[i]
            path = sections[i + 1].rstrip('/')
            section_content = sections[i + 2] if i + 2 < len(sections) else ""
            
            api_key = f"{method} {path}"
            
            # Extract priority
            priority_match = re.search(r'\*\*Priority\*\*:\s*(P\d+)', section_content)
            priority = priority_match.group(1) if priority_match else "P3"
            
            # Extract category
            category_match = re.search(r'\*\*Category\*\*:\s*(.*?)\n', section_content)
            category = category_match.group(1).strip() if category_match else "General"
            
            # Extract gap type
            gap_type_match = re.search(r'\*\*Gap Type\*\*:\s*(.*?)\n', section_content)
            gap_type = gap_type_match.group(1).strip() if gap_type_match else "Unknown"
            
            # Extract effort
            effort_match = re.search(r'\*\*Estimated Effort\*\*:\s*([\d.]+)\s*hours\s*\(([\d.]+)\s*days\)', section_content)
            if effort_match:
                effort_hours = float(effort_match.group(1))
                effort_days = float(effort_match.group(2))
            else:
                # Try alternative format
                effort_match = re.search(r'(\d+(?:\.\d+)?)\s*hours?\s*\((\d+(?:\.\d+)?)\s*days?\)', section_content)
                if effort_match:
                    effort_hours = float(effort_match.group(1))
                    effort_days = float(effort_match.group(2))
                else:
                    effort_hours = 10.0
                    effort_days = 1.25
            
            # Extract dependencies
            dependencies = []
            deps_section = re.search(r'\*\*API Dependencies\*\*:\s*\n((?:- `[^`]+`.*?\n)+)', section_content, re.MULTILINE)
            if deps_section:
                dep_lines = deps_section.group(1).strip().split('\n')
                for dep_line in dep_lines:
                    dep_match = re.search(r'- `([^`]+)`', dep_line)
                    if dep_match:
                        dep_path = dep_match.group(1).rstrip('/')
                        # Try to infer method from context or use POST as default
                        dependencies.append(dep_path)
            
            self.apis[api_key] = APITimelineItem(
                method=method,
                path=path,
                priority=priority,
                category=category,
                gap_type=gap_type,
                effort_hours=effort_hours,
                effort_days=effort_days,
                dependencies=dependencies
            )
            self.dependencies[api_key] = dependencies
        
        print(f"Loaded {len(self.apis)} APIs from backlog.", file=__import__('sys').stderr)

    def assign_phases(self):
        """Assign APIs to phases based on priority."""
        for api_key, api in self.apis.items():
            if api.priority == "P0":
                api.phase = 0
            elif api.priority == "P1":
                api.phase = 1
            elif api.priority == "P2":
                api.phase = 2
            elif api.priority == "P3":
                api.phase = 3

    def calculate_week_ranges(self):
        """Calculate week ranges for each API within its phase."""
        for phase_num, phase_info in self.phases.items():
            week_start, week_end = phase_info["weeks"]
            phase_apis = [api for api in self.apis.values() if api.phase == phase_num]
            
            if not phase_apis:
                continue
            
            # Sort by dependencies (APIs with no dependencies first)
            phase_apis.sort(key=lambda a: (len(a.dependencies), a.effort_days))
            
            # Calculate cumulative weeks (assuming 5 days per week, 8 hours per day = 40 hours/week)
            current_week = week_start
            for api in phase_apis:
                # Estimate weeks needed
                weeks_needed = max(1, int((api.effort_days / 5) + 0.5))  # Round up
                api.week_start = current_week
                api.week_end = min(week_end, current_week + weeks_needed - 1)
                current_week = api.week_end + 1
                
                # Don't exceed phase boundaries
                if current_week > week_end:
                    current_week = week_end

    def identify_parallel_groups(self):
        """Identify APIs that can be worked on in parallel."""
        parallel_group = 0
        
        for phase_num in range(4):
            phase_apis = [api for api in self.apis.values() if api.phase == phase_num]
            if not phase_apis:
                continue
            
            # Group by dependencies
            dependency_groups = defaultdict(list)
            for api in phase_apis:
                dep_key = tuple(sorted(api.dependencies))
                dependency_groups[dep_key].append(api)
            
            # Assign parallel groups
            for group_apis in dependency_groups.values():
                for api in group_apis:
                    api.parallel_group = parallel_group
                parallel_group += 1

    def generate_timeline_report(self, output_file: str):
        """Generate the timeline markdown report."""
        report_content = [
            "# API Development Timeline",
            "",
            "**Document Version**: 1.0.0",
            "**Last Updated**: 2025-12-13",
            "**Task**: 0.5.4 - Create API development timeline",
            "",
            "---",
            "",
            "## Overview",
            "",
            "This document provides a comprehensive timeline for API development, organized by priority",
            "and phase. The timeline accounts for:",
            "- **Priority**: P0 (Critical) → P1 (High) → P2 (Medium) → P3 (Low)",
            "- **Dependencies**: APIs are scheduled after their dependencies",
            "- **Effort Estimates**: Realistic time estimates based on complexity",
            "- **Parallel Work**: Opportunities for concurrent development",
            "",
            f"**Total APIs**: {len(self.apis)}",
            f"**Total Estimated Effort**: {sum(api.effort_hours for api in self.apis.values()):.1f} hours ({sum(api.effort_days for api in self.apis.values()):.1f} days)",
            "",
            "**Timeline Phases**:",
            "- **Phase 0** (Weeks 0-4): P0 - Critical APIs (Foundation)",
            "- **Phase 1** (Weeks 5-8): P1 - High Priority APIs (Core Features)",
            "- **Phase 2** (Weeks 9-20): P2 - Medium Priority APIs (Enhanced Features)",
            "- **Phase 3** (Weeks 21-40): P3 - Low Priority APIs (Strategic Features)",
            "",
            "---",
            "",
            "## Timeline Summary",
            "",
            "| Phase | Weeks | Priority | APIs | Total Effort (Hours) | Total Effort (Days) |",
            "|-------|-------|----------|------|---------------------|---------------------|",
        ]
        
        for phase_num, phase_info in self.phases.items():
            phase_apis = [api for api in self.apis.values() if api.phase == phase_num]
            week_start, week_end = phase_info["weeks"]
            total_hours = sum(api.effort_hours for api in phase_apis)
            total_days = sum(api.effort_days for api in phase_apis)
            
            report_content.append(
                f"| Phase {phase_num} | {week_start}-{week_end} | {phase_info['priority']} | {len(phase_apis)} | {total_hours:.1f} | {total_days:.1f} |"
            )
        
        report_content.extend([
            "",
            "---",
            "",
            "## Detailed Timeline by Phase",
            ""
        ])
        
        # Generate detailed timeline for each phase
        for phase_num, phase_info in self.phases.items():
            week_start, week_end = phase_info["weeks"]
            phase_apis = [api for api in self.apis.values() if api.phase == phase_num]
            
            if not phase_apis:
                continue
            
            report_content.append(f"### Phase {phase_num}: {phase_info['name']}")
            report_content.append("")
            report_content.append(f"**Timeline**: Weeks {week_start}-{week_end}")
            report_content.append(f"**Total APIs**: {len(phase_apis)}")
            report_content.append(f"**Total Effort**: {sum(api.effort_hours for api in phase_apis):.1f} hours ({sum(api.effort_days for api in phase_apis):.1f} days)")
            report_content.append("")
            
            # Group by parallel groups
            parallel_groups = defaultdict(list)
            for api in phase_apis:
                parallel_groups[api.parallel_group].append(api)
            
            # Sort by parallel group
            for group_id in sorted(parallel_groups.keys()):
                group_apis = parallel_groups[group_id]
                if len(group_apis) > 1:
                    report_content.append(f"#### Parallel Group {group_id + 1} (Can be implemented concurrently)")
                else:
                    report_content.append(f"#### Sequential Implementation")
                report_content.append("")
                
                report_content.append("| Method | Endpoint | Category | Gap Type | Effort (Hours) | Effort (Days) | Weeks | Dependencies |")
                report_content.append("|--------|----------|----------|----------|----------------|---------------|-------|--------------|")
                
                for api in sorted(group_apis, key=lambda a: (a.week_start or 0, a.effort_days)):
                    deps_str = ", ".join([f"`{d}`" for d in api.dependencies[:3]]) if api.dependencies else "None"
                    if len(api.dependencies) > 3:
                        deps_str += f" (+{len(api.dependencies) - 3} more)"
                    
                    week_range = f"{api.week_start}-{api.week_end}" if api.week_start and api.week_end else "TBD"
                    
                    report_content.append(
                        f"| {api.method} | `{api.path}` | {api.category} | {api.gap_type} | {api.effort_hours:.1f} | {api.effort_days:.1f} | {week_range} | {deps_str} |"
                    )
                
                report_content.append("")
            
            report_content.append("---")
            report_content.append("")
        
        # Add milestones section
        report_content.extend([
            "## Milestones and Deliverables",
            "",
            "### Phase 0 Milestones (Weeks 0-4)",
            "",
            "**Week 2 Milestone**: Foundation APIs Complete",
            "- ✅ `POST /api/v1/auth/register/` - User registration",
            "- ✅ `POST /api/v1/auth/login/` - User authentication",
            "- ✅ `GET /api/v1/auth/me/` - Current user info",
            "- ✅ `POST /api/v1/assets/` - Asset creation",
            "",
            "**Week 4 Milestone**: Core CRUD APIs Complete",
            "- ✅ `GET /api/v1/assets/` - Asset listing with filters",
            "- ✅ `POST /api/v1/contracts/{id}/validate/` - Contract validation",
            "- ✅ `POST /api/v1/assets/{id}/activate/` - Asset activation",
            "",
            "**Deliverables**:",
            "- All P0 APIs implemented and tested",
            "- Frontend MVP can begin development",
            "- Authentication and core asset management functional",
            "",
            "### Phase 1 Milestones (Weeks 5-8)",
            "",
            "**Week 6 Milestone**: Credential Management APIs",
            "- ✅ `GET /api/v1/scheduled-ingestions/{id}/credentials/`",
            "- ✅ `POST /api/v1/scheduled-ingestions/{id}/credentials/test/`",
            "",
            "**Week 8 Milestone**: Marketplace and Search APIs",
            "- ✅ `GET /api/v1/marketplace/listings/` - Marketplace listings",
            "- ✅ `GET /api/v1/search/search/` - Advanced search",
            "",
            "**Deliverables**:",
            "- All P1 APIs implemented and tested",
            "- Marketplace functionality available",
            "- Credential management operational",
            "",
            "### Phase 2 Milestones (Weeks 9-20)",
            "",
            "**Week 12 Milestone**: AI/ML APIs",
            "- ✅ `POST /api/v1/ai/natural-language-search/`",
            "- ✅ `POST /api/v1/ai/schema-matching/`",
            "",
            "**Week 16 Milestone**: Social Features",
            "- ✅ `POST /api/v1/social/ratings/`",
            "- ✅ `POST /api/v1/social/reviews/`",
            "- ✅ `POST /api/v1/social/comments/`",
            "- ✅ `POST /api/v1/social/communities/`",
            "",
            "**Deliverables**:",
            "- All P2 APIs implemented and tested",
            "- AI/ML capabilities available",
            "- Social features operational",
            "",
            "### Phase 3 Milestones (Weeks 21-40)",
            "",
            "**Week 30 Milestone**: Developer Experience APIs",
            "- ✅ `GET /api/v1/developer/plugins/`",
            "- ✅ `GET /api/v1/developer/sdk/`",
            "",
            "**Week 40 Milestone**: Advanced Marketplace",
            "- ✅ `GET /api/v1/marketplace/listings/{id}/preview/`",
            "",
            "**Deliverables**:",
            "- All P3 APIs implemented and tested",
            "- Developer experience enhanced",
            "- Advanced marketplace features available",
            "",
            "---",
            "",
            "## Parallel Implementation Opportunities",
            "",
            "The following APIs can be implemented in parallel within their phases:",
            "",
        ])
        
        # Identify parallel opportunities
        for phase_num in range(4):
            phase_apis = [api for api in self.apis.values() if api.phase == phase_num]
            if not phase_apis:
                continue
            
            parallel_groups = defaultdict(list)
            for api in phase_apis:
                parallel_groups[api.parallel_group].append(api)
            
            parallel_opportunities = [g for g in parallel_groups.values() if len(g) > 1]
            if parallel_opportunities:
                report_content.append(f"### Phase {phase_num}")
                report_content.append("")
                for i, group in enumerate(parallel_opportunities, 1):
                    report_content.append(f"**Group {i}** (Parallel):")
                    for api in group:
                        report_content.append(f"- `{api.method} {api.path}` ({api.effort_days:.1f} days)")
                    report_content.append("")
        
        report_content.extend([
            "---",
            "",
            "## Risk Factors and Mitigation",
            "",
            "### High Risk Items",
            "",
            "1. **Complex Dependencies**: APIs with multiple dependencies may face delays",
            "   - **Mitigation**: Implement dependency APIs early, add buffer time",
            "",
            "2. **Large Effort Estimates**: APIs with >20 days effort may require more time",
            "   - **Mitigation**: Break down into smaller tasks, add 20% buffer",
            "",
            "3. **External Service Integration**: APIs requiring external services may face integration delays",
            "   - **Mitigation**: Early integration testing, mock services for development",
            "",
            "### Medium Risk Items",
            "",
            "1. **Parallel Work Coordination**: Multiple teams working in parallel may face conflicts",
            "   - **Mitigation**: Clear API contracts, regular sync meetings",
            "",
            "2. **Testing Overhead**: Comprehensive testing may take longer than estimated",
            "   - **Mitigation**: Automated testing, test-driven development",
            "",
            "---",
            "",
            "## Resource Allocation Recommendations",
            "",
            "### Phase 0 (Weeks 0-4)",
            "- **Team Size**: 2-3 developers",
            "- **Focus**: Foundation APIs, authentication, core CRUD",
            "- **Critical Path**: Authentication → Assets → Contracts → Activation",
            "",
            "### Phase 1 (Weeks 5-8)",
            "- **Team Size**: 2-3 developers",
            "- **Focus**: Marketplace, credential management, search",
            "- **Critical Path**: Credentials → Marketplace → Search",
            "",
            "### Phase 2 (Weeks 9-20)",
            "- **Team Size**: 3-4 developers (including AI/ML specialist)",
            "- **Focus**: AI/ML APIs, social features, transformation",
            "- **Critical Path**: AI/ML → Social → Transformation",
            "",
            "### Phase 3 (Weeks 21-40)",
            "- **Team Size**: 1-2 developers",
            "- **Focus**: Developer experience, advanced marketplace",
            "- **Critical Path**: Developer APIs → Advanced Marketplace",
            "",
            "---",
            "",
            "## Success Criteria",
            "",
            "### Phase 0 Success Criteria",
            "- ✅ All P0 APIs implemented and tested",
            "- ✅ Authentication flow complete",
            "- ✅ Asset onboarding flow functional",
            "- ✅ Frontend MVP can begin development",
            "",
            "### Phase 1 Success Criteria",
            "- ✅ All P1 APIs implemented and tested",
            "- ✅ Marketplace discovery functional",
            "- ✅ Credential management operational",
            "",
            "### Phase 2 Success Criteria",
            "- ✅ All P2 APIs implemented and tested",
            "- ✅ AI/ML capabilities available",
            "- ✅ Social features operational",
            "",
            "### Phase 3 Success Criteria",
            "- ✅ All P3 APIs implemented and tested",
            "- ✅ Developer experience enhanced",
            "- ✅ Advanced features available",
            "",
            "---",
            "",
            "**Document Status**: ✅ Complete",
            f"**Total APIs**: {len(self.apis)}",
            f"**Total Effort**: {sum(api.effort_hours for api in self.apis.values()):.1f} hours ({sum(api.effort_days for api in self.apis.values()):.1f} days)",
            "",
            "**Next Steps**:",
            "1. ✅ Review timeline with stakeholders",
            "2. ✅ Allocate resources per phase",
            "3. ✅ Begin Phase 0 implementation",
            "4. ✅ Update backlog with timeline information",
            ""
        ])
        
        Path(output_file).write_text('\n'.join(report_content))
        print(f"Generated timeline report: {output_file}", file=__import__('sys').stderr)

if __name__ == "__main__":
    generator = APITimelineGenerator()
    generator.load_backlog("docs/api-audit/api-development-backlog.md")
    generator.assign_phases()
    generator.calculate_week_ranges()
    generator.identify_parallel_groups()
    generator.generate_timeline_report("docs/api-audit/api-development-timeline.md")
