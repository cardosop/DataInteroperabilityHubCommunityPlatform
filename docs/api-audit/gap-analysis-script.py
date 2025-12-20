#!/usr/bin/env python3
"""
API Gap Analysis Script

This script compares:
1. API Requirements Matrix (from task 0.1.5) - what's required
2. Current API Inventory (from task 0.2.2) - what exists in codebase

It identifies:
- Missing endpoints (required but not in codebase)
- Incomplete endpoints (exist but missing methods/parameters/fields)
- Endpoints needing enhancements
- Endpoints in codebase but not in requirements (extra endpoints)

Usage:
    python gap-analysis-script.py > docs/api-audit/gap-analysis.md
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class APIEndpoint:
    """Represents an API endpoint"""
    path: str
    method: str
    description: str = ""
    priority: str = ""
    status: str = ""
    sources: List[str] = field(default_factory=list)
    category: str = ""
    performance_target: str = ""
    auth_required: bool = True
    auth_type: str = ""
    query_params: List[str] = field(default_factory=list)
    path_params: List[str] = field(default_factory=list)
    request_schema: Optional[Dict] = None
    response_schema: Optional[Dict] = None
    
    def normalize_path(self) -> str:
        """Normalize path for comparison (handle {id} vs <uuid:id> variations)"""
        # Replace various ID patterns with {id}
        path = self.path
        path = re.sub(r'<uuid:id>', '{id}', path)
        path = re.sub(r'<str:id>', '{id}', path)
        path = re.sub(r'<int:id>', '{id}', path)
        path = re.sub(r'<uuid:tenant_id>', '{tenant_id}', path)
        path = re.sub(r'<str:resource_type>', '{resource_type}', path)
        path = re.sub(r'<str:resource_id>', '{resource_id}', path)
        path = re.sub(r'<str:asset_uuid>', '{asset_uuid}', path)
        path = re.sub(r'<str:field_name>', '{field_name}', path)
        return path
    
    def key(self) -> Tuple[str, str]:
        """Return (normalized_path, method) as comparison key"""
        return (self.normalize_path(), self.method.upper())


class GapAnalyzer:
    """Analyze gaps between requirements and current inventory"""
    
    def __init__(self):
        self.requirements: Dict[Tuple[str, str], APIEndpoint] = {}
        self.current: Dict[Tuple[str, str], APIEndpoint] = {}
        self.missing: List[APIEndpoint] = []
        self.incomplete: List[Tuple[APIEndpoint, APIEndpoint, List[str]]] = []  # (required, current, issues)
        self.enhancements: List[Tuple[APIEndpoint, APIEndpoint, List[str]]] = []  # (required, current, enhancements)
        self.extra: List[APIEndpoint] = []  # In codebase but not in requirements
        
    def load_requirements(self, file_path: str):
        """Load API requirements from consolidated matrix"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract endpoints from table format: | `/api/v1/...` | METHOD | Description | ...
        pattern = r'\|\s+`(/api/v1/[^`]+)`\s+\|\s+(\w+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)\s+\|\s+([^|]+)'
        
        # Also extract from detailed sections: ##### METHOD `/api/v1/...`
        detailed_pattern = r'^#####\s+(GET|POST|PUT|PATCH|DELETE)\s+`(/api/v1/[^`]+)`'
        
        current_category = ""
        current_section = ""
        
        for line in content.split('\n'):
            # Track current category
            if line.startswith('### ') and 'APIs' in line:
                current_category = line.replace('### ', '').replace(' APIs', '').strip()
            
            # Extract endpoint from table
            match = re.search(pattern, line)
            if match:
                path, method, description, priority, status = match.groups()
                endpoint = APIEndpoint(
                    path=path.strip(),
                    method=method.strip().upper(),
                    description=description.strip(),
                    priority=priority.strip(),
                    status=status.strip(),
                    category=current_category
                )
                key = endpoint.key()
                # Merge if already exists (from detailed section)
                if key in self.requirements:
                    existing = self.requirements[key]
                    # Merge sources and enhance description
                    if not existing.description or len(description) > len(existing.description):
                        existing.description = description
                else:
                    self.requirements[key] = endpoint
            
            # Extract from detailed sections
            detailed_match = re.search(detailed_pattern, line)
            if detailed_match:
                method, path = detailed_match.groups()
                # Extract priority and status from following lines
                endpoint = APIEndpoint(
                    path=path.strip(),
                    method=method.strip().upper(),
                    description="",
                    priority="",
                    status="",
                    category=current_category
                )
                key = endpoint.key()
                # Try to find priority and status in next 10 lines
                lines_after = content[content.find(line):content.find(line)+2000].split('\n')[:20]
                for next_line in lines_after:
                    if '**Priority**:' in next_line:
                        priority_match = re.search(r'\*\*Priority\*\*:\s*([^|]+)', next_line)
                        if priority_match:
                            priority_str = priority_match.group(1).strip()
                            if 'P0' in priority_str:
                                endpoint.priority = 'P0'
                            elif 'P1' in priority_str:
                                endpoint.priority = 'P1'
                            elif 'P2' in priority_str:
                                endpoint.priority = 'P2'
                            elif 'P3' in priority_str:
                                endpoint.priority = 'P3'
                    if '**Status**:' in next_line:
                        status_match = re.search(r'\*\*Status\*\*:\s*([^|]+)', next_line)
                        if status_match:
                            endpoint.status = status_match.group(1).strip()
                    if '**Description**:' in next_line:
                        desc_match = re.search(r'\*\*Description\*\*:\s*(.+)', next_line)
                        if desc_match:
                            endpoint.description = desc_match.group(1).strip()
                
                # Merge with existing or add new
                if key in self.requirements:
                    existing = self.requirements[key]
                    if not existing.priority and endpoint.priority:
                        existing.priority = endpoint.priority
                    if not existing.status and endpoint.status:
                        existing.status = endpoint.status
                    if not existing.description and endpoint.description:
                        existing.description = endpoint.description
                else:
                    self.requirements[key] = endpoint
    
    def load_current_inventory(self, file_path: str):
        """Load current API inventory from codebase extraction"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract endpoints from table format: | METHOD | `/api/v1/...` | View | Action | Type |
        pattern = r'\|\s+(\w+)\s+\|\s+`(/api/v1/[^`]+)`\s+\|\s+`?([^|`]+)`?\s+\|\s+([^|]+)\s+\|\s+([^|]+)'
        matches = re.findall(pattern, content)
        
        current_category = ""
        for line in content.split('\n'):
            # Track current category
            if line.startswith('### ') and not line.startswith('####'):
                current_category = line.replace('### ', '').strip()
            
            # Extract endpoint from table
            match = re.search(pattern, line)
            if match:
                method, path, view, action, endpoint_type = match.groups()
                endpoint = APIEndpoint(
                    path=path.strip(),
                    method=method.strip().upper(),
                    description=f"{view.strip()} - {action.strip()} ({endpoint_type.strip()})",
                    category=current_category
                )
                key = endpoint.key()
                self.current[key] = endpoint
    
    def analyze_gaps(self):
        """Perform gap analysis"""
        # Find missing endpoints (in requirements but not in current)
        for key, req_endpoint in self.requirements.items():
            if key not in self.current:
                self.missing.append(req_endpoint)
            else:
                current_endpoint = self.current[key]
                # Check for incompleteness
                issues = self._check_incompleteness(req_endpoint, current_endpoint)
                if issues:
                    self.incomplete.append((req_endpoint, current_endpoint, issues))
                
                # Check for enhancements needed
                enhancements = self._check_enhancements(req_endpoint, current_endpoint)
                if enhancements:
                    self.enhancements.append((req_endpoint, current_endpoint, enhancements))
        
        # Find extra endpoints (in current but not in requirements)
        for key, current_endpoint in self.current.items():
            if key not in self.requirements:
                self.extra.append(current_endpoint)
    
    def _check_incompleteness(self, required: APIEndpoint, current: APIEndpoint) -> List[str]:
        """Check if current endpoint is incomplete compared to requirements"""
        issues = []
        
        # Check if method matches
        if required.method != current.method:
            issues.append(f"Method mismatch: required {required.method}, found {current.method}")
        
        # Note: We can't check parameters/schemas from the inventory alone
        # This would require OpenAPI schema comparison (task 0.2.1)
        
        return issues
    
    def _check_enhancements(self, required: APIEndpoint, current: APIEndpoint) -> List[str]:
        """Check if current endpoint needs enhancements"""
        enhancements = []
        
        # Check performance targets (if specified in requirements)
        if required.performance_target and not current.performance_target:
            enhancements.append(f"Performance target not documented: {required.performance_target}")
        
        # Check authentication requirements
        if required.auth_required and not current.auth_type:
            enhancements.append("Authentication requirements not documented")
        
        return enhancements
    
    def generate_report(self) -> str:
        """Generate comprehensive gap analysis report"""
        report = []
        report.append("# API Gap Analysis")
        report.append("")
        report.append("**Document Version**: 1.0.0")
        report.append("**Last Updated**: 2025-12-13")
        report.append("**Task**: 0.3.1 - Compare current vs required APIs")
        report.append("")
        report.append("---")
        report.append("")
        report.append("## Overview")
        report.append("")
        report.append("This document compares:")
        report.append("1. **API Requirements Matrix** (from task 0.1.5): What's required for Frontend MVP")
        report.append("2. **Current API Inventory** (from task 0.2.2): What exists in the codebase")
        report.append("")
        report.append(f"**Total Required APIs**: {len(self.requirements)}")
        report.append(f"**Total Current APIs**: {len(self.current)}")
        report.append(f"**Missing APIs**: {len(self.missing)}")
        report.append(f"**Incomplete APIs**: {len(self.incomplete)}")
        report.append(f"**APIs Needing Enhancements**: {len(self.enhancements)}")
        report.append(f"**Extra APIs** (in codebase, not in requirements): {len(self.extra)}")
        report.append("")
        
        # Summary by priority
        report.append("## Summary by Priority")
        report.append("")
        by_priority = defaultdict(lambda: {'total': 0, 'missing': 0, 'incomplete': 0, 'enhancements': 0})
        
        for req in self.requirements.values():
            key = req.key()
            by_priority[req.priority]['total'] += 1
            if key not in self.current:
                by_priority[req.priority]['missing'] += 1
            elif key in [inc[0].key() for inc in self.incomplete]:
                by_priority[req.priority]['incomplete'] += 1
            elif key in [enh[0].key() for enh in self.enhancements]:
                by_priority[req.priority]['enhancements'] += 1
        
        report.append("| Priority | Total | Missing | Incomplete | Needs Enhancement | Complete |")
        report.append("|----------|-------|---------|-------------|-------------------|----------|")
        for priority in ['P0', 'P1', 'P2', 'P3']:
            if priority in by_priority:
                stats = by_priority[priority]
                complete = stats['total'] - stats['missing'] - stats['incomplete'] - stats['enhancements']
                report.append(f"| {priority} | {stats['total']} | {stats['missing']} | {stats['incomplete']} | {stats['enhancements']} | {complete} |")
        
        # Missing endpoints
        report.append("")
        report.append("## Missing Endpoints")
        report.append("")
        report.append(f"**Total Missing**: {len(self.missing)}")
        report.append("")
        
        if not self.missing:
            report.append("✅ **No missing endpoints found!**")
        else:
            by_priority_missing = defaultdict(list)
            for endpoint in self.missing:
                by_priority_missing[endpoint.priority].append(endpoint)
            
            for priority in ['P0', 'P1', 'P2', 'P3']:
                if priority in by_priority_missing:
                    report.append(f"### {priority} - {priority_labels[priority]} ({len(by_priority_missing[priority])} endpoints)")
                    report.append("")
                    report.append("| Method | Path | Description | Category | Sources |")
                    report.append("|--------|------|-------------|----------|---------|")
                    for endpoint in sorted(by_priority_missing[priority], key=lambda x: (x.category, x.path)):
                        sources = ', '.join(endpoint.sources) if endpoint.sources else 'Requirements Matrix'
                        report.append(f"| {endpoint.method} | `{endpoint.path}` | {endpoint.description[:60]}... | {endpoint.category} | {sources} |")
                    report.append("")
        
        # Incomplete endpoints
        report.append("")
        report.append("## Incomplete Endpoints")
        report.append("")
        report.append(f"**Total Incomplete**: {len(self.incomplete)}")
        report.append("")
        report.append("These endpoints exist in the codebase but may be missing:")
        report.append("- Required HTTP methods")
        report.append("- Query parameters")
        report.append("- Request/response schema fields")
        report.append("- Error response handling")
        report.append("")
        report.append("**Note**: Detailed schema comparison requires OpenAPI schema analysis (task 0.2.1)")
        report.append("")
        
        if not self.incomplete:
            report.append("✅ **No incomplete endpoints found!**")
        else:
            report.append("| Method | Path | Issue | Required | Current |")
            report.append("|--------|------|-------|----------|---------|")
            for required, current, issues in self.incomplete:
                for issue in issues:
                    report.append(f"| {required.method} | `{required.path}` | {issue} | {required.description[:40]}... | {current.description[:40]}... |")
            report.append("")
        
        # Enhancements needed
        report.append("")
        report.append("## Endpoints Needing Enhancements")
        report.append("")
        report.append(f"**Total Needing Enhancements**: {len(self.enhancements)}")
        report.append("")
        report.append("These endpoints exist but may need:")
        report.append("- Performance target documentation")
        report.append("- Authentication/authorization documentation")
        report.append("- Enhanced error handling")
        report.append("- Additional query parameters")
        report.append("")
        
        if not self.enhancements:
            report.append("✅ **No enhancements needed!**")
        else:
            report.append("| Method | Path | Enhancement Needed | Priority |")
            report.append("|--------|------|-------------------|----------|")
            for required, current, enhancements in self.enhancements:
                for enhancement in enhancements:
                    report.append(f"| {required.method} | `{required.path}` | {enhancement} | {required.priority} |")
            report.append("")
        
        # Extra endpoints
        report.append("")
        report.append("## Extra Endpoints (In Codebase, Not in Requirements)")
        report.append("")
        report.append(f"**Total Extra**: {len(self.extra)}")
        report.append("")
        report.append("These endpoints exist in the codebase but are not documented in the requirements matrix.")
        report.append("They may be:")
        report.append("- Internal/admin endpoints")
        report.append("- Backward compatibility endpoints")
        report.append("- Endpoints not yet required by frontend")
        report.append("")
        
        if not self.extra:
            report.append("✅ **No extra endpoints found!**")
        else:
            by_category_extra = defaultdict(list)
            for endpoint in self.extra:
                by_category_extra[endpoint.category].append(endpoint)
            
            for category in sorted(by_category_extra.keys()):
                report.append(f"### {category} ({len(by_category_extra[category])} endpoints)")
                report.append("")
                report.append("| Method | Path | Description |")
                report.append("|--------|------|-------------|")
                for endpoint in sorted(by_category_extra[category], key=lambda x: x.path):
                    report.append(f"| {endpoint.method} | `{endpoint.path}` | {endpoint.description[:60]}... |")
                report.append("")
        
        # Recommendations
        report.append("")
        report.append("## Recommendations")
        report.append("")
        report.append("### Immediate Actions (P0 - Critical)")
        report.append("")
        p0_missing = [e for e in self.missing if e.priority == 'P0']
        if p0_missing:
            report.append(f"1. **Implement {len(p0_missing)} missing P0 endpoints** - These block frontend MVP")
            report.append("   - These must be implemented before frontend development begins")
        else:
            report.append("1. ✅ **All P0 endpoints exist** - Frontend MVP can proceed")
        report.append("")
        
        report.append("### Short-term Actions (P1 - High Priority)")
        report.append("")
        p1_missing = [e for e in self.missing if e.priority == 'P1']
        if p1_missing:
            report.append(f"1. **Implement {len(p1_missing)} missing P1 endpoints** - Required for core features")
            report.append("   - Target: Weeks 5-24")
        else:
            report.append("1. ✅ **All P1 endpoints exist**")
        report.append("")
        
        report.append("### Medium-term Actions (P2 - Medium Priority)")
        report.append("")
        p2_missing = [e for e in self.missing if e.priority == 'P2']
        if p2_missing:
            report.append(f"1. **Implement {len(p2_missing)} missing P2 endpoints** - Required for advanced features")
            report.append("   - Target: Weeks 25-40")
        else:
            report.append("1. ✅ **All P2 endpoints exist**")
        report.append("")
        
        report.append("### Long-term Actions (P3 - Low Priority)")
        report.append("")
        p3_missing = [e for e in self.missing if e.priority == 'P3']
        if p3_missing:
            report.append(f"1. **Implement {len(p3_missing)} missing P3 endpoints** - Strategic differentiators")
            report.append("   - Target: Weeks 41-64")
        else:
            report.append("1. ✅ **All P3 endpoints exist**")
        report.append("")
        
        report.append("### Schema Validation")
        report.append("")
        report.append("1. **Compare with OpenAPI schema** (task 0.2.1) to validate:")
        report.append("   - Request/response schemas match requirements")
        report.append("   - Query parameters are documented")
        report.append("   - Error responses are properly defined")
        report.append("   - Authentication/authorization is correctly implemented")
        report.append("")
        
        report.append("---")
        report.append("")
        report.append("**Document Status**: ✅ Complete")
        report.append(f"**Total Gaps Identified**: {len(self.missing) + len(self.incomplete) + len(self.enhancements)}")
        report.append("")
        report.append("**Next Steps**:")
        report.append("1. Task 0.3.2: Categorize gaps by priority")
        report.append("2. Task 0.3.3: Document gap details with estimated effort")
        report.append("3. Task 0.4: Create API contract specifications for missing APIs")
        
        return "\n".join(report)


priority_labels = {
    'P0': 'Critical',
    'P1': 'High',
    'P2': 'Medium',
    'P3': 'Low'
}


if __name__ == "__main__":
    analyzer = GapAnalyzer()
    
    # Load requirements
    requirements_file = "docs/api-audit/api-requirements-matrix-consolidated.md"
    print(f"Loading requirements from {requirements_file}...", file=__import__('sys').stderr)
    analyzer.load_requirements(requirements_file)
    print(f"Loaded {len(analyzer.requirements)} required APIs", file=__import__('sys').stderr)
    
    # Load current inventory
    inventory_file = "docs/api-audit/current-api-inventory.md"
    print(f"Loading current inventory from {inventory_file}...", file=__import__('sys').stderr)
    analyzer.load_current_inventory(inventory_file)
    print(f"Loaded {len(analyzer.current)} current APIs", file=__import__('sys').stderr)
    
    # Perform analysis
    print("Performing gap analysis...", file=__import__('sys').stderr)
    analyzer.analyze_gaps()
    
    # Generate report
    report = analyzer.generate_report()
    print(report)

