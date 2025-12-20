#!/usr/bin/env python3
"""
Gap Details Documentation Script

Documents detailed information for each API gap including:
- Gap type (missing endpoint, incomplete endpoint, enhancement)
- Impact (blocks which journeys/use cases)
- Priority (P0/P1/P2/P3)
- Estimated effort
- Dependencies
- Timeline

This script:
- Reads gap analysis and categorization documents
- Maps gaps to journeys and use cases
- Generates comprehensive gap details document
- Updates gap analysis file with detailed information

Usage:
    python scripts/document-gap-details.py [--gap-analysis GAP_ANALYSIS_FILE] [--output OUTPUT_FILE]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@dataclass
class GapDetail:
    """Represents detailed information for a gap."""
    endpoint: str
    method: str
    gap_type: str  # missing, incomplete, enhancement
    priority: str  # P0, P1, P2, P3
    category: str
    priority_category: str
    phase: str
    weeks: str
    description: str
    impact: str
    estimated_effort: str
    dependencies: List[str] = field(default_factory=list)
    blocked_journeys: List[str] = field(default_factory=list)
    blocked_use_cases: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    implementation_notes: List[str] = field(default_factory=list)
    performance_requirements: str = ""
    error_responses: List[str] = field(default_factory=list)

class GapDetailsDocumenter:
    """Documents detailed information for each gap."""
    
    # Journey to API mapping (based on gap analysis sources)
    JOURNEY_API_MAPPING = {
        'JOURNEY-AUTH-002': ['POST /api/v1/auth/register/'],
        'JOURNEY-AUTH-006': ['GET /api/v1/auth/me/'],
        'JOURNEY-AUTH-007': ['GET /api/v1/auth/api-keys/'],
        'JOURNEY-DPO-004': ['POST /api/v1/assets/{id}/activate/'],
        'JOURNEY-DPO-005': ['GET /api/v1/assets/'],
        'JOURNEY-DC-001': ['GET /api/v1/marketplace/listings/'],
        'JOURNEY-DC-002': ['GET /api/v1/marketplace/listings/{id}/download/'],
        'JOURNEY-CPO-001': ['GET /api/v1/compliance/compliance-runs/{id}/results/'],
        'JOURNEY-DE-003': ['GET /api/v1/dq/dq-runs/', 'GET /api/v1/dq/dq-runs/{id}/results/'],
    }
    
    # Use case to API mapping
    USE_CASE_API_MAPPING = {
        'UC-AUTH-002': ['POST /api/v1/auth/register/'],
        'UC-AUTH-006': ['GET /api/v1/auth/me/'],
        'UC-AUTH-007': ['GET /api/v1/auth/api-keys/'],
        'UC-DPO-004': ['POST /api/v1/assets/{id}/activate/'],
        'UC-DPO-005': ['GET /api/v1/assets/'],
        'UC-DC-001': ['GET /api/v1/marketplace/listings/'],
        'UC-CPO-001': ['GET /api/v1/compliance/compliance-runs/{id}/results/'],
    }
    
    # Dependency mapping
    DEPENDENCY_MAPPING = {
        'POST /api/v1/assets/{id}/activate/': [
            'Contract validation service',
            'DQ service',
            'Compliance service',
            'Workflow engine'
        ],
        'POST /api/v1/contracts/{id}/validate/': [
            'Contract validation service',
            'Schema validation service'
        ],
        'GET /api/v1/scheduled-ingestions/{id}/credentials/': [
            'Scheduled ingestion model',
            'Credential manager service (Phase 8)'
        ],
        'POST /api/v1/scheduled-ingestions/{id}/credentials/test/': [
            'Scheduled ingestion model',
            'Credential manager service (Phase 8)',
            'Connector framework'
        ],
        'POST /api/v1/ai/natural-language-search/': [
            'LLM service',
            'Query understanding service',
            'Search service'
        ],
        'POST /api/v1/ai/schema-matching/': [
            'AI service infrastructure',
            'LLM API access',
            'Schema management service'
        ],
    }
    
    def __init__(self):
        self.gap_details: List[GapDetail] = []
        self.gaps_by_priority: Dict[str, List[GapDetail]] = defaultdict(list)
    
    def parse_gap_analysis(self, file_path: Path) -> List[Dict]:
        """Parse gap analysis markdown file to extract gap information."""
        gaps = []
        
        if not file_path.exists():
            print(f"⚠️  Gap analysis file not found: {file_path}")
            return gaps
        
        content = file_path.read_text()
        
        current_section = None
        current_gap = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Section headers
            if line.startswith('## '):
                current_section = line.replace('## ', '').strip()
                current_gap = None
            
            # Missing endpoints
            if current_section == 'Missing Endpoints':
                if line.startswith('#### '):
                    match = re.match(r'#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)', line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            'endpoint': endpoint,
                            'method': method,
                            'gap_type': 'missing',
                            'section': 'Missing Endpoints'
                        }
                        gaps.append(current_gap)
                elif current_gap:
                    if '**Status**:' in line:
                        current_gap['status'] = line.split('**Status**:')[1].strip()
                    elif '**Priority**:' in line:
                        current_gap['priority'] = re.search(r'P[0-3]', line).group(0) if re.search(r'P[0-3]', line) else 'P3'
                    elif '**Category**:' in line:
                        current_gap['category'] = line.split('**Category**:')[1].strip()
                    elif '**Impact**:' in line:
                        current_gap['impact'] = line.split('**Impact**:')[1].strip()
                    elif '**Estimated Effort**:' in line:
                        current_gap['estimated_effort'] = line.split('**Estimated Effort**:')[1].strip()
                    elif '**Description**:' in line:
                        current_gap['description'] = line.split('**Description**:')[1].strip()
                    elif '**Sources**:' in line:
                        current_gap['sources'] = []
                    elif line.startswith('- ') and 'Sources' in str(current_gap.get('sources', [])):
                        if 'Journeys' in line:
                            journeys = re.findall(r'JOURNEY-[A-Z]+-\d+', line)
                            current_gap.setdefault('journeys', []).extend(journeys)
                        if 'Use Cases' in line:
                            use_cases = re.findall(r'UC-[A-Z]+-\d+', line)
                            current_gap.setdefault('use_cases', []).extend(use_cases)
                    elif '**Performance Requirements**:' in line:
                        current_gap['performance_requirements'] = line.split('**Performance Requirements**:')[1].strip()
                    elif '**Implementation Notes**:' in line:
                        current_gap['implementation_notes'] = []
                    elif line.startswith('- ') and 'implementation_notes' in current_gap:
                        current_gap['implementation_notes'].append(line.replace('- ', '').strip())
            
            # Incomplete endpoints
            elif current_section == 'Incomplete Endpoints':
                if line.startswith('#### '):
                    match = re.match(r'#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)', line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            'endpoint': endpoint,
                            'method': method,
                            'gap_type': 'incomplete',
                            'section': 'Incomplete Endpoints'
                        }
                        gaps.append(current_gap)
                elif current_gap:
                    if '**Priority**:' in line:
                        current_gap['priority'] = re.search(r'P[0-3]', line).group(0) if re.search(r'P[0-3]', line) else 'P3'
                    elif '**Gap Type**:' in line:
                        current_gap['gap_type_detail'] = line.split('**Gap Type**:')[1].strip()
                    elif '**Impact**:' in line:
                        current_gap['impact'] = line.split('**Impact**:')[1].strip()
                    elif '**Estimated Effort**:' in line:
                        current_gap['estimated_effort'] = line.split('**Estimated Effort**:')[1].strip()
                    elif '**Sources**:' in line:
                        current_gap['sources'] = []
                    elif line.startswith('- ') and 'Sources' in str(current_gap.get('sources', [])):
                        if 'Journeys' in line:
                            journeys = re.findall(r'JOURNEY-[A-Z]+-\d+', line)
                            current_gap.setdefault('journeys', []).extend(journeys)
            
            # Enhancements
            elif current_section == 'Endpoints Needing Enhancements':
                if line.startswith('#### '):
                    match = re.match(r'#### (\d+)\.\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)', line)
                    if match:
                        method = match.group(2).upper()
                        endpoint = match.group(3).strip()
                        current_gap = {
                            'endpoint': endpoint,
                            'method': method,
                            'gap_type': 'enhancement',
                            'section': 'Endpoints Needing Enhancements'
                        }
                        gaps.append(current_gap)
                elif current_gap:
                    if '**Priority**:' in line:
                        current_gap['priority'] = re.search(r'P[0-3]', line).group(0) if re.search(r'P[0-3]', line) else 'P3'
                    elif '**Enhancement Type**:' in line:
                        current_gap['enhancement_type'] = line.split('**Enhancement Type**:')[1].strip()
                    elif '**Impact**:' in line:
                        current_gap['impact'] = line.split('**Impact**:')[1].strip()
                    elif '**Estimated Effort**:' in line:
                        current_gap['estimated_effort'] = line.split('**Estimated Effort**:')[1].strip()
        
        return gaps
    
    def map_journeys_and_use_cases(self, gap: Dict) -> tuple[List[str], List[str]]:
        """Map gap to blocked journeys and use cases."""
        endpoint_key = f"{gap['method']} {gap['endpoint']}"
        
        blocked_journeys = gap.get('journeys', [])
        blocked_use_cases = gap.get('use_cases', [])
        
        # Add from mapping
        for journey_id, endpoints in self.JOURNEY_API_MAPPING.items():
            if endpoint_key in endpoints:
                if journey_id not in blocked_journeys:
                    blocked_journeys.append(journey_id)
        
        for use_case_id, endpoints in self.USE_CASE_API_MAPPING.items():
            if endpoint_key in endpoints:
                if use_case_id not in blocked_use_cases:
                    blocked_use_cases.append(use_case_id)
        
        return blocked_journeys, blocked_use_cases
    
    def get_dependencies(self, gap: Dict) -> List[str]:
        """Get dependencies for a gap."""
        endpoint_key = f"{gap['method']} {gap['endpoint']}"
        return self.DEPENDENCY_MAPPING.get(endpoint_key, [])
    
    def get_phase_and_weeks(self, priority: str, category: str) -> tuple[str, str]:
        """Get implementation phase and weeks based on priority."""
        if priority == 'P0':
            return "Phase 0", "Weeks 0-4 (Before Frontend MVP)"
        elif priority == 'P1':
            return "Phase 1", "Weeks 5-24 (Core Features)"
        elif priority == 'P2':
            return "Phase 2", "Weeks 25-40 (Advanced Features)"
        else:
            return "Phase 3", "Weeks 41-64 (Strategic Differentiators)"
    
    def create_gap_detail(self, gap: Dict) -> GapDetail:
        """Create detailed gap information."""
        blocked_journeys, blocked_use_cases = self.map_journeys_and_use_cases(gap)
        dependencies = self.get_dependencies(gap)
        priority = gap.get('priority', 'P3')
        category = gap.get('category', 'Uncategorized')
        phase, weeks = self.get_phase_and_weeks(priority, category)
        
        # Determine priority category
        priority_category = f"{priority}-{category.replace(' ', '-')}"
        
        return GapDetail(
            endpoint=gap['endpoint'],
            method=gap['method'],
            gap_type=gap['gap_type'],
            priority=priority,
            category=category,
            priority_category=priority_category,
            phase=phase,
            weeks=weeks,
            description=gap.get('description', ''),
            impact=gap.get('impact', ''),
            estimated_effort=gap.get('estimated_effort', ''),
            dependencies=dependencies,
            blocked_journeys=blocked_journeys,
            blocked_use_cases=blocked_use_cases,
            sources=gap.get('sources', []),
            implementation_notes=gap.get('implementation_notes', []),
            performance_requirements=gap.get('performance_requirements', ''),
            error_responses=gap.get('error_responses', [])
        )
    
    def document_all_gaps(self, gaps: List[Dict]):
        """Document all gaps with detailed information."""
        for gap in gaps:
            detail = self.create_gap_detail(gap)
            self.gap_details.append(detail)
            self.gaps_by_priority[detail.priority].append(detail)
    
    def generate_gap_details_report(self, output_path: Path):
        """Generate comprehensive gap details report."""
        lines = []
        
        # Header
        lines.append("# API Gap Details Documentation")
        lines.append("")
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}")
        lines.append(f"**Task**: 0.3.3 - Document gap details")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append("This document provides detailed information for each API gap including:")
        lines.append("- Gap type (missing endpoint, incomplete endpoint, enhancement)")
        lines.append("- Impact (blocks which journeys/use cases)")
        lines.append("- Priority (P0/P1/P2/P3)")
        lines.append("- Estimated effort")
        lines.append("- Dependencies")
        lines.append("- Timeline")
        lines.append("")
        lines.append(f"**Total Gaps**: {len(self.gap_details)}")
        lines.append("")
        
        # Statistics
        lines.append("## Statistics")
        lines.append("")
        
        # By gap type
        gaps_by_type = defaultdict(int)
        for gap in self.gap_details:
            gaps_by_type[gap.gap_type] += 1
        
        lines.append("### Gaps by Type")
        lines.append("")
        for gap_type in ['missing', 'incomplete', 'enhancement']:
            count = gaps_by_type.get(gap_type, 0)
            lines.append(f"- **{gap_type.capitalize()}**: {count} gaps")
        lines.append("")
        
        # By priority
        lines.append("### Gaps by Priority")
        lines.append("")
        for priority in ['P0', 'P1', 'P2', 'P3']:
            count = len(self.gaps_by_priority.get(priority, []))
            lines.append(f"- **{priority}**: {count} gaps")
        lines.append("")
        
        # Detailed gap information by priority
        for priority in ['P0', 'P1', 'P2', 'P3']:
            priority_gaps = self.gaps_by_priority.get(priority, [])
            if not priority_gaps:
                continue
            
            priority_name = {
                'P0': 'Critical',
                'P1': 'High',
                'P2': 'Medium',
                'P3': 'Low'
            }[priority]
            
            lines.append(f"## {priority} - {priority_name} Priority")
            lines.append("")
            lines.append(f"**Total Gaps**: {len(priority_gaps)}")
            lines.append("")
            
            # Group by gap type
            for gap_type in ['missing', 'incomplete', 'enhancement']:
                type_gaps = [g for g in priority_gaps if g.gap_type == gap_type]
                if not type_gaps:
                    continue
                
                lines.append(f"### {gap_type.capitalize()} Endpoints")
                lines.append("")
                
                for gap in sorted(type_gaps, key=lambda x: x.endpoint):
                    lines.append(f"#### {gap.method} `{gap.endpoint}`")
                    lines.append("")
                    lines.append(f"**Gap Type**: {gap.gap_type.capitalize()}")
                    lines.append(f"**Priority**: {gap.priority} - {priority_name}")
                    lines.append(f"**Category**: {gap.category}")
                    lines.append(f"**Priority Category**: {gap.priority_category}")
                    lines.append(f"**Phase**: {gap.phase}")
                    lines.append(f"**Timeline**: {gap.weeks}")
                    lines.append("")
                    
                    if gap.description:
                        lines.append(f"**Description**: {gap.description}")
                        lines.append("")
                    
                    lines.append(f"**Impact**: {gap.impact}")
                    lines.append("")
                    
                    if gap.blocked_journeys:
                        lines.append("**Blocked Journeys**:")
                        for journey in gap.blocked_journeys:
                            lines.append(f"- {journey}")
                        lines.append("")
                    
                    if gap.blocked_use_cases:
                        lines.append("**Blocked Use Cases**:")
                        for use_case in gap.blocked_use_cases:
                            lines.append(f"- {use_case}")
                        lines.append("")
                    
                    lines.append(f"**Estimated Effort**: {gap.estimated_effort}")
                    lines.append("")
                    
                    if gap.dependencies:
                        lines.append("**Dependencies**:")
                        for dep in gap.dependencies:
                            lines.append(f"- {dep}")
                        lines.append("")
                    
                    if gap.performance_requirements:
                        lines.append(f"**Performance Requirements**: {gap.performance_requirements}")
                        lines.append("")
                    
                    if gap.implementation_notes:
                        lines.append("**Implementation Notes**:")
                        for note in gap.implementation_notes:
                            lines.append(f"- {note}")
                        lines.append("")
                    
                    if gap.sources:
                        lines.append("**Sources**:")
                        for source in gap.sources:
                            lines.append(f"- {source}")
                        lines.append("")
                    
                    lines.append("---")
                    lines.append("")
        
        # Summary by impact
        lines.append("## Impact Summary")
        lines.append("")
        lines.append("### Journeys Blocked by Gaps")
        lines.append("")
        journey_gaps = defaultdict(list)
        for gap in self.gap_details:
            for journey in gap.blocked_journeys:
                journey_gaps[journey].append(f"{gap.method} {gap.endpoint}")
        
        for journey in sorted(journey_gaps.keys()):
            lines.append(f"**{journey}**: {len(journey_gaps[journey])} gaps")
            for endpoint in journey_gaps[journey]:
                lines.append(f"- {endpoint}")
            lines.append("")
        
        lines.append("### Use Cases Blocked by Gaps")
        lines.append("")
        use_case_gaps = defaultdict(list)
        for gap in self.gap_details:
            for use_case in gap.blocked_use_cases:
                use_case_gaps[use_case].append(f"{gap.method} {gap.endpoint}")
        
        for use_case in sorted(use_case_gaps.keys()):
            lines.append(f"**{use_case}**: {len(use_case_gaps[use_case])} gaps")
            for endpoint in use_case_gaps[use_case]:
                lines.append(f"- {endpoint}")
            lines.append("")
        
        # Write to file
        output_path.write_text('\n'.join(lines))
        print(f"✅ Gap details report saved to {output_path}")
    
    def export_json(self, output_path: Path):
        """Export gap details as JSON."""
        data = {
            'generated_at': datetime.utcnow().isoformat(),
            'total_gaps': len(self.gap_details),
            'gaps_by_priority': {
                priority: len(gaps) for priority, gaps in self.gaps_by_priority.items()
            },
            'gaps': [asdict(gap) for gap in self.gap_details]
        }
        
        output_path.write_text(json.dumps(data, indent=2))
        print(f"✅ JSON gap details saved to {output_path}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Document API gap details')
    parser.add_argument('--gap-analysis', default='docs/api-audit/gap-analysis.md',
                       help='Path to gap analysis file')
    parser.add_argument('--output', default='docs/api-audit/gap-details.md',
                       help='Path to output gap details file')
    
    args = parser.parse_args()
    
    documenter = GapDetailsDocumenter()
    
    # Parse gap analysis
    print("📋 Parsing gap analysis...")
    gap_analysis_path = Path(args.gap_analysis)
    gaps = documenter.parse_gap_analysis(gap_analysis_path)
    print(f"✅ Found {len(gaps)} gaps")
    
    # Document gaps
    print("📝 Documenting gap details...")
    documenter.document_all_gaps(gaps)
    
    # Print summary
    print("\n" + "="*60)
    print("GAP DETAILS SUMMARY")
    print("="*60)
    for priority in ['P0', 'P1', 'P2', 'P3']:
        priority_gaps = documenter.gaps_by_priority.get(priority, [])
        print(f"{priority}: {len(priority_gaps)} gaps")
        for gap_type in ['missing', 'incomplete', 'enhancement']:
            type_count = len([g for g in priority_gaps if g.gap_type == gap_type])
            if type_count > 0:
                print(f"  - {gap_type}: {type_count}")
    print("="*60)
    
    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    documenter.generate_gap_details_report(output_path)
    
    # Export JSON
    json_path = output_path.with_suffix('.json')
    documenter.export_json(json_path)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

