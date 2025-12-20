#!/usr/bin/env python3
"""
API Requirements Consolidation Script

This script consolidates API requirements from multiple sources:
1. Frontend proposal (task 0.1.1)
2. Frontend specs (task 0.1.2)
3. User journeys (task 0.1.3)
4. Use cases (task 0.1.4)

It creates a unified, deduplicated API requirements matrix with source tracking.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

@dataclass
class APIRequirement:
    """Represents a single API endpoint requirement."""
    endpoint: str
    method: str
    description: str
    priority: str  # P0, P1, P2, P3
    status: str  # existing, missing, incomplete
    sources: List[str] = field(default_factory=list)  # List of source identifiers
    request_schema: Optional[Dict] = None
    response_schema: Optional[Dict] = None
    query_params: List[str] = field(default_factory=list)
    path_params: List[str] = field(default_factory=list)
    auth_required: bool = True
    auth_type: str = "JWT/API Key"
    performance_target: Optional[str] = None
    error_responses: List[str] = field(default_factory=list)
    authorization_requirements: Optional[str] = None
    
    def __hash__(self):
        """Make hashable for deduplication."""
        return hash((self.endpoint, self.method))
    
    def __eq__(self, other):
        """Equality based on endpoint and method."""
        if not isinstance(other, APIRequirement):
            return False
        return self.endpoint == other.endpoint and self.method == other.method
    
    def merge(self, other: 'APIRequirement'):
        """Merge another requirement into this one, combining sources."""
        # Merge sources
        combined_sources = set(self.sources) | set(other.sources)
        self.sources = sorted(list(combined_sources))
        
        # Use higher priority (P0 > P1 > P2 > P3)
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
        if priority_order.get(other.priority, 99) < priority_order.get(self.priority, 99):
            self.priority = other.priority
        
        # Prefer existing over missing
        if other.status == 'existing' and self.status != 'existing':
            self.status = 'existing'
        elif other.status == 'incomplete' and self.status == 'missing':
            self.status = 'incomplete'
        
        # Merge other fields if not set
        if not self.description and other.description:
            self.description = other.description
        if not self.request_schema and other.request_schema:
            self.request_schema = other.request_schema
        if not self.response_schema and other.response_schema:
            self.response_schema = other.response_schema
        if not self.query_params and other.query_params:
            self.query_params = other.query_params
        if not self.path_params and other.path_params:
            self.path_params = other.path_params
        if not self.performance_target and other.performance_target:
            self.performance_target = other.performance_target
        if not self.error_responses and other.error_responses:
            self.error_responses = other.error_responses
        if not self.authorization_requirements and other.authorization_requirements:
            self.authorization_requirements = other.authorization_requirements

class APIConsolidator:
    """Consolidates API requirements from multiple sources."""
    
    def __init__(self):
        self.apis: Dict[tuple, APIRequirement] = {}  # Key: (endpoint, method)
        self.categories: Dict[str, List[APIRequirement]] = defaultdict(list)
    
    def add_requirement(self, req: APIRequirement, category: str = "Uncategorized"):
        """Add or merge an API requirement."""
        key = (req.endpoint, req.method)
        
        if key in self.apis:
            # Merge with existing
            self.apis[key].merge(req)
        else:
            # Add new
            self.apis[key] = req
        
        # Add to category
        self.categories[category].append(self.apis[key])
    
    def get_statistics(self) -> Dict:
        """Get statistics about the consolidated requirements."""
        stats = {
            'total_apis': len(self.apis),
            'by_priority': defaultdict(int),
            'by_status': defaultdict(int),
            'by_category': {cat: len(apis) for cat, apis in self.categories.items()},
            'by_source': defaultdict(int),
        }
        
        for req in self.apis.values():
            stats['by_priority'][req.priority] += 1
            stats['by_status'][req.status] += 1
            for source in req.sources:
                stats['by_source'][source] += 1
        
        return stats
    
    def export_to_markdown(self, output_path: Path):
        """Export consolidated requirements to markdown."""
        lines = []
        
        # Header
        lines.append("# Consolidated API Requirements Matrix")
        lines.append("")
        lines.append("**Document Version**: 2.0.0")
        lines.append("**Last Updated**: 2025-12-13")
        lines.append("**Status**: Consolidated from all sources")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Overview
        stats = self.get_statistics()
        lines.append("## Overview")
        lines.append("")
        lines.append(f"This document consolidates API requirements from all sources:")
        lines.append("- Frontend proposal (task 0.1.1)")
        lines.append("- Frontend specs (task 0.1.2)")
        lines.append("- User journeys (task 0.1.3)")
        lines.append("- Use cases (task 0.1.4)")
        lines.append("")
        lines.append(f"**Total APIs**: {stats['total_apis']}")
        lines.append("")
        
        # Statistics
        lines.append("### Statistics")
        lines.append("")
        lines.append("#### By Priority")
        for priority in ['P0', 'P1', 'P2', 'P3']:
            count = stats['by_priority'].get(priority, 0)
            lines.append(f"- **{priority}**: {count} APIs")
        lines.append("")
        
        lines.append("#### By Status")
        for status in ['existing', 'incomplete', 'missing']:
            count = stats['by_status'].get(status, 0)
            lines.append(f"- **{status}**: {count} APIs")
        lines.append("")
        
        lines.append("#### By Source")
        for source, count in sorted(stats['by_source'].items()):
            lines.append(f"- **{source}**: {count} APIs")
        lines.append("")
        
        # Categories
        lines.append("## API Categories")
        lines.append("")
        
        category_order = [
            "Authentication",
            "Asset Management",
            "Contract Management",
            "Dataset Management",
            "Marketplace",
            "Compliance",
            "Data Quality",
            "Scheduled Ingestion",
            "Search",
            "Governance",
            "Observability",
            "WebSocket Events",
            "GraphQL",
            "AI/ML",
            "Transformation",
            "Social Features",
            "Data Mesh",
            "Virtualization",
            "Advanced Marketplace",
            "Advanced Governance",
            "Integration Ecosystem",
            "Developer Experience",
        ]
        
        for category in category_order:
            if category not in self.categories:
                continue
            
            apis = self.categories[category]
            lines.append(f"### {category}")
            lines.append("")
            lines.append(f"**Priority**: {self._get_category_priority(category)}")
            lines.append(f"**Count**: {len(apis)} APIs")
            lines.append("")
            
            # Table header
            lines.append("| Endpoint | Method | Description | Priority | Status | Sources | Performance |")
            lines.append("|----------|--------|-------------|----------|--------|---------|-------------|")
            
            # Sort by priority, then endpoint
            sorted_apis = sorted(apis, key=lambda x: (x.priority, x.endpoint))
            
            for req in sorted_apis:
                sources_str = ", ".join(req.sources[:3])  # Show first 3 sources
                if len(req.sources) > 3:
                    sources_str += f" (+{len(req.sources) - 3} more)"
                
                perf = req.performance_target or "N/A"
                
                lines.append(
                    f"| `{req.endpoint}` | {req.method} | {req.description[:50]}... | "
                    f"{req.priority} | {req.status} | {sources_str} | {perf} |"
                )
            
            lines.append("")
            
            # Detailed documentation for each API
            for req in sorted_apis:
                lines.append(f"#### {req.method} {req.endpoint}")
                lines.append("")
                lines.append(f"**Description**: {req.description}")
                lines.append("")
                lines.append(f"**Priority**: {req.priority}")
                lines.append(f"**Status**: {req.status}")
                lines.append(f"**Sources**: {', '.join(req.sources)}")
                lines.append("")
                
                if req.auth_required:
                    lines.append(f"**Authentication**: Required ({req.auth_type})")
                else:
                    lines.append("**Authentication**: Not required")
                lines.append("")
                
                if req.authorization_requirements:
                    lines.append(f"**Authorization**: {req.authorization_requirements}")
                    lines.append("")
                
                if req.performance_target:
                    lines.append(f"**Performance Target**: {req.performance_target}")
                    lines.append("")
                
                if req.query_params:
                    lines.append("**Query Parameters**:")
                    for param in req.query_params:
                        lines.append(f"- `{param}`")
                    lines.append("")
                
                if req.path_params:
                    lines.append("**Path Parameters**:")
                    for param in req.path_params:
                        lines.append(f"- `{param}`")
                    lines.append("")
                
                if req.error_responses:
                    lines.append("**Error Responses**:")
                    for error in req.error_responses:
                        lines.append(f"- {error}")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        # Write to file
        output_path.write_text('\n'.join(lines))
        print(f"✅ Exported consolidated API requirements to {output_path}")
    
    def _get_category_priority(self, category: str) -> str:
        """Get priority for a category."""
        priority_map = {
            "Authentication": "P0",
            "Asset Management": "P0",
            "Contract Management": "P0",
            "Dataset Management": "P0",
            "Search": "P0",
            "WebSocket Events": "P0",
            "Marketplace": "P1",
            "Compliance": "P1",
            "Data Quality": "P1",
            "Scheduled Ingestion": "P1",
            "Governance": "P1",
            "Observability": "P1",
            "GraphQL": "P1",
            "AI/ML": "P2",
            "Transformation": "P2",
            "Social Features": "P2",
        }
        return priority_map.get(category, "P3")

def main():
    """Main consolidation function."""
    consolidator = APIConsolidator()
    
    # Note: In a real implementation, this would parse the actual source files
    # For now, this is a framework that can be extended
    
    print("API Requirements Consolidation")
    print("=" * 50)
    print()
    print("This script consolidates API requirements from:")
    print("1. Frontend proposal (task 0.1.1)")
    print("2. Frontend specs (task 0.1.2)")
    print("3. User journeys (task 0.1.3)")
    print("4. Use cases (task 0.1.4)")
    print()
    print("To use this script:")
    print("1. Parse source documents to extract API requirements")
    print("2. Create APIRequirement objects for each API")
    print("3. Add them to the consolidator with appropriate categories")
    print("4. Export to markdown")
    print()
    print("See the consolidated matrix at: docs/api-audit/api-requirements-matrix.md")

if __name__ == "__main__":
    main()

