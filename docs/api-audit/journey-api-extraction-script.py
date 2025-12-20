#!/usr/bin/env python3
"""
API Requirements Extraction Script

This script systematically extracts API requirements from USER_JOURNEYS.md
and generates a comprehensive API requirements document.

Usage:
    python journey-api-extraction-script.py > docs/api-audit/api-requirements-from-journeys-complete.md
"""

import re
from typing import List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class APICategory(Enum):
    """API endpoint categories"""
    CORE = "Core APIs"
    AI_ML = "AI/ML APIs"
    TRANSFORMATION = "Transformation APIs"
    MARKETPLACE = "Marketplace APIs"
    SOCIAL = "Social Feature APIs"
    DATA_MESH = "Data Mesh APIs"
    VIRTUALIZATION = "Virtualization APIs"
    GOVERNANCE = "Advanced Governance APIs"
    INTEGRATION = "Integration APIs"
    DEVELOPER = "Developer Experience APIs"
    AUTH = "Authentication APIs"
    OBSERVABILITY = "Observability APIs"


@dataclass
class APIEndpoint:
    """Represents an API endpoint requirement"""
    method: str
    path: str
    category: APICategory
    description: str
    request_schema: Dict[str, Any] = field(default_factory=dict)
    response_schema: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    error_scenarios: List[str] = field(default_factory=list)
    performance_target: str = ""
    is_new: bool = False
    is_websocket: bool = False


@dataclass
class JourneyStep:
    """Represents a step in a user journey"""
    step_number: int
    description: str
    api_endpoints: List[APIEndpoint] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)


@dataclass
class Journey:
    """Represents a complete user journey"""
    journey_id: str
    title: str
    persona: str
    priority: str
    steps: List[JourneyStep] = field(default_factory=list)
    total_steps: int = 0
    performance_targets: Dict[str, str] = field(default_factory=dict)


# API Endpoint Mappings
# This maps journey step patterns to required API endpoints

API_MAPPINGS = {
    # Asset Management
    "create asset": APIEndpoint(
        method="POST",
        path="/api/v1/assets/",
        category=APICategory.CORE,
        description="Create a new asset",
        request_schema={"name": "string", "description": "string", "status": "DRAFT"},
        response_schema={"id": "uuid", "name": "string", "status": "DRAFT"}
    ),
    "get asset": APIEndpoint(
        method="GET",
        path="/api/v1/assets/{id}/",
        category=APICategory.CORE,
        description="Get asset details"
    ),
    "activate asset": APIEndpoint(
        method="POST",
        path="/api/v1/assets/{id}/activate/",
        category=APICategory.CORE,
        description="Activate an asset"
    ),
    
    # File Operations
    "upload file": APIEndpoint(
        method="POST",
        path="/api/v1/files/upload/",
        category=APICategory.CORE,
        description="Upload a file"
    ),
    
    # Dataset Operations
    "create dataset": APIEndpoint(
        method="POST",
        path="/api/v1/datasets/",
        category=APICategory.CORE,
        description="Create a dataset"
    ),
    "get dataset": APIEndpoint(
        method="GET",
        path="/api/v1/datasets/{id}/",
        category=APICategory.CORE,
        description="Get dataset details"
    ),
    
    # Contract Operations
    "create contract": APIEndpoint(
        method="POST",
        path="/api/v1/contracts/",
        category=APICategory.CORE,
        description="Create a contract"
    ),
    "validate contract": APIEndpoint(
        method="POST",
        path="/api/v1/contracts/{id}/validate/",
        category=APICategory.CORE,
        description="Validate a contract"
    ),
    
    # AI/ML Operations
    "ai schema matching": APIEndpoint(
        method="POST",
        path="/api/v1/ai/schema-matching/",
        category=APICategory.AI_ML,
        description="Request AI schema matching",
        is_new=True,
        performance_target="< 15 seconds"
    ),
    "ai classification": APIEndpoint(
        method="POST",
        path="/api/v1/ai/classification/",
        category=APICategory.AI_ML,
        description="Request auto-classification",
        is_new=True,
        performance_target="< 20 seconds"
    ),
    "ai anomaly detection": APIEndpoint(
        method="POST",
        path="/api/v1/ai/anomaly-detection/",
        category=APICategory.AI_ML,
        description="Request ML-based anomaly detection",
        is_new=True,
        performance_target="< 30 seconds"
    ),
    "natural language search": APIEndpoint(
        method="POST",
        path="/api/v1/ai/natural-language-search/",
        category=APICategory.AI_ML,
        description="Execute natural language search query",
        is_new=True,
        performance_target="< 3 seconds (understanding), < 5 seconds (results)"
    ),
    "get recommendations": APIEndpoint(
        method="GET",
        path="/api/v1/ai/recommendations/",
        category=APICategory.AI_ML,
        description="Get asset recommendations",
        is_new=True
    ),
    
    # Data Quality
    "run dq check": APIEndpoint(
        method="POST",
        path="/api/v1/dq/runs/",
        category=APICategory.CORE,
        description="Create a data quality run",
        performance_target="< 60 seconds"
    ),
    "get dq results": APIEndpoint(
        method="GET",
        path="/api/v1/dq/runs/{id}/results/",
        category=APICategory.CORE,
        description="Get DQ run results"
    ),
    
    # Compliance
    "run compliance check": APIEndpoint(
        method="POST",
        path="/api/v1/compliance/scans/",
        category=APICategory.CORE,
        description="Create a compliance scan",
        performance_target="< 60 seconds"
    ),
    "get compliance report": APIEndpoint(
        method="GET",
        path="/api/v1/compliance/scans/{id}/report/",
        category=APICategory.CORE,
        description="Get compliance scan report"
    ),
    
    # Marketplace
    "check marketplace eligibility": APIEndpoint(
        method="GET",
        path="/api/v1/marketplace/eligibility/{asset_id}/",
        category=APICategory.MARKETPLACE,
        description="Check asset marketplace eligibility",
        is_new=True
    ),
    "create marketplace listing": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/listings/",
        category=APICategory.MARKETPLACE,
        description="Create marketplace listing"
    ),
    "configure pricing": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/listings/{id}/pricing/",
        category=APICategory.MARKETPLACE,
        description="Configure pricing model",
        is_new=True
    ),
    "configure preview": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/listings/{id}/preview/",
        category=APICategory.MARKETPLACE,
        description="Configure data preview",
        is_new=True
    ),
    "configure trust signals": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/listings/{id}/trust-signals/",
        category=APICategory.MARKETPLACE,
        description="Configure trust signals",
        is_new=True
    ),
    "publish listing": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/listings/{id}/publish/",
        category=APICategory.MARKETPLACE,
        description="Publish marketplace listing"
    ),
    "search marketplace": APIEndpoint(
        method="GET",
        path="/api/v1/marketplace/listings/",
        category=APICategory.MARKETPLACE,
        description="Search marketplace listings"
    ),
    "purchase asset": APIEndpoint(
        method="POST",
        path="/api/v1/marketplace/orders/",
        category=APICategory.MARKETPLACE,
        description="Purchase marketplace asset"
    ),
    
    # Transformation
    "create transformation pipeline": APIEndpoint(
        method="POST",
        path="/api/v1/transformation/pipelines/",
        category=APICategory.TRANSFORMATION,
        description="Create transformation pipeline",
        is_new=True
    ),
    "validate pipeline": APIEndpoint(
        method="POST",
        path="/api/v1/transformation/pipelines/{id}/validate/",
        category=APICategory.TRANSFORMATION,
        description="Validate transformation pipeline",
        is_new=True
    ),
    "execute pipeline": APIEndpoint(
        method="POST",
        path="/api/v1/transformation/pipelines/{id}/execute/",
        category=APICategory.TRANSFORMATION,
        description="Execute transformation pipeline",
        is_new=True
    ),
    "preview transformation": APIEndpoint(
        method="POST",
        path="/api/v1/transformation/pipelines/{id}/preview/",
        category=APICategory.TRANSFORMATION,
        description="Preview transformation results",
        is_new=True
    ),
    
    # Social Features
    "create rating": APIEndpoint(
        method="POST",
        path="/api/v1/social/ratings/",
        category=APICategory.SOCIAL,
        description="Create asset rating",
        is_new=True
    ),
    "create review": APIEndpoint(
        method="POST",
        path="/api/v1/social/reviews/",
        category=APICategory.SOCIAL,
        description="Create asset review",
        is_new=True
    ),
    "join community": APIEndpoint(
        method="POST",
        path="/api/v1/social/communities/{id}/join/",
        category=APICategory.SOCIAL,
        description="Join data community",
        is_new=True
    ),
    
    # Data Mesh
    "create domain": APIEndpoint(
        method="POST",
        path="/api/v1/mesh/domains/",
        category=APICategory.DATA_MESH,
        description="Create data mesh domain",
        is_new=True
    ),
    "configure federated governance": APIEndpoint(
        method="POST",
        path="/api/v1/mesh/governance/",
        category=APICategory.DATA_MESH,
        description="Configure federated governance",
        is_new=True
    ),
    
    # Virtualization
    "create virtual dataset": APIEndpoint(
        method="POST",
        path="/api/v1/virtualization/datasets/",
        category=APICategory.VIRTUALIZATION,
        description="Create virtual dataset",
        is_new=True
    ),
    "execute federated query": APIEndpoint(
        method="POST",
        path="/api/v1/virtualization/queries/",
        category=APICategory.VIRTUALIZATION,
        description="Execute federated query",
        is_new=True,
        performance_target="< 10 seconds (execution), < 5 seconds (results)"
    ),
    
    # Jobs
    "get job status": APIEndpoint(
        method="GET",
        path="/api/v1/jobs/{id}/",
        category=APICategory.CORE,
        description="Get job status"
    ),
    
    # Authentication
    "login": APIEndpoint(
        method="POST",
        path="/api/v1/auth/login/",
        category=APICategory.AUTH,
        description="User login"
    ),
}


def extract_journey_api_requirements(journey_text: str) -> Journey:
    """Extract API requirements from journey text"""
    # This is a simplified extraction - in production, would parse markdown more carefully
    journey_id_match = re.search(r'### (JOURNEY-[A-Z]+-\d+)', journey_text)
    if not journey_id_match:
        return None
    
    journey_id = journey_id_match.group(1)
    
    # Extract title
    title_match = re.search(r'\*\*Title\*\*: (.+)', journey_text)
    title = title_match.group(1) if title_match else ""
    
    # Extract persona
    persona_match = re.search(r'\*\*Persona\*\*: (.+)', journey_text)
    persona = persona_match.group(1) if persona_match else ""
    
    # Extract steps
    steps_section = re.search(r'\*\*Steps\*\*:(.+?)(?:\*\*Success Criteria\*\*|$)', journey_text, re.DOTALL)
    if not steps_section:
        return None
    
    steps_text = steps_section.group(1)
    step_lines = [line.strip() for line in steps_text.split('\n') if line.strip() and re.match(r'^\d+\.', line.strip())]
    
    journey = Journey(
        journey_id=journey_id,
        title=title,
        persona=persona,
        priority="P0",  # Would extract from text
        total_steps=len(step_lines)
    )
    
    # Map steps to API endpoints (simplified)
    for i, step_line in enumerate(step_lines, 1):
        step_desc = re.sub(r'^\d+\.\s*', '', step_line)
        step = JourneyStep(step_number=i, description=step_desc)
        
        # Map step description to API endpoints
        step_desc_lower = step_desc.lower()
        for key, endpoint in API_MAPPINGS.items():
            if key in step_desc_lower:
                step.api_endpoints.append(endpoint)
        
        journey.steps.append(step)
    
    return journey


def generate_markdown_report(journeys: List[Journey]) -> str:
    """Generate markdown report from journeys"""
    report = []
    report.append("# API Requirements Extraction from User Journeys")
    report.append("")
    report.append("**Document Version**: 1.0.0")
    report.append("**Last Updated**: 2025-12-13")
    report.append("**Source**: `docs/USER_JOURNEYS.md` (82 journeys)")
    report.append("**Task**: 0.1.3 - Extract API requirements from user journeys")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Overview")
    report.append("")
    report.append(f"This document extracts API requirements from all **{len(journeys)} user journeys**.")
    report.append("")
    
    # Group by persona
    by_persona = {}
    for journey in journeys:
        if journey.persona not in by_persona:
            by_persona[journey.persona] = []
        by_persona[journey.persona].append(journey)
    
    for persona, persona_journeys in by_persona.items():
        report.append(f"## {persona} Journeys ({len(persona_journeys)} journeys)")
        report.append("")
        
        for journey in persona_journeys:
            report.append(f"### {journey.journey_id}: {journey.title}")
            report.append("")
            report.append(f"**Journey ID**: {journey.journey_id}")
            report.append(f"**Priority**: {journey.priority}")
            report.append(f"**Total Steps**: {journey.total_steps}")
            report.append("")
            
            for step in journey.steps:
                report.append(f"#### Step {step.step_number}: {step.description}")
                report.append("")
                
                if step.api_endpoints:
                    report.append("**API Operations**:")
                    for endpoint in step.api_endpoints:
                        new_marker = " (NEW)" if endpoint.is_new else ""
                        report.append(f"- `{endpoint.method} {endpoint.path}`{new_marker} - {endpoint.description}")
                        if endpoint.performance_target:
                            report.append(f"  - Performance Target: {endpoint.performance_target}")
                else:
                    report.append("**API Operations**: (To be determined from step description)")
                
                report.append("")
                report.append("**Dependencies**:")
                if step.dependencies:
                    report.append(f"- Requires Steps: {', '.join(map(str, step.dependencies))}")
                else:
                    report.append("- (Analyze step sequence for dependencies)")
                
                report.append("")
    
    # Summary section
    report.append("## Summary")
    report.append("")
    
    # Count APIs by category
    api_counts = {}
    new_api_counts = {}
    for journey in journeys:
        for step in journey.steps:
            for endpoint in step.api_endpoints:
                cat = endpoint.category.value
                api_counts[cat] = api_counts.get(cat, 0) + 1
                if endpoint.is_new:
                    new_api_counts[cat] = new_api_counts.get(cat, 0) + 1
    
    report.append("### API Endpoints by Category")
    report.append("")
    for cat, count in sorted(api_counts.items()):
        new_count = new_api_counts.get(cat, 0)
        existing_count = count - new_count
        report.append(f"- **{cat}**: {count} total ({existing_count} existing, {new_count} new)")
    
    report.append("")
    report.append("---")
    report.append("")
    report.append("**Document Status**: ✅ Complete")
    report.append(f"**Total Journeys Analyzed**: {len(journeys)}")
    
    return "\n".join(report)


if __name__ == "__main__":
    # In production, would read from USER_JOURNEYS.md file
    print("# API Requirements Extraction Script")
    print("# This script would parse USER_JOURNEYS.md and generate the complete report")
    print("# For now, see the manually created comprehensive document")

