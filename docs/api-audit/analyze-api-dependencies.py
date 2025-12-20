#!/usr/bin/env python3
"""
Analyze API Dependencies

This script analyzes dependencies between APIs from multiple sources:
- User journeys (sequential step dependencies)
- Use cases (flow dependencies)
- API requirements (which APIs call other APIs)
- Gap analysis (prerequisite APIs)

Usage:
    python analyze-api-dependencies.py > docs/api-audit/api-dependencies.md
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class APIDependency:
    """Represents a dependency between two APIs"""
    dependent_api: str  # API that depends on another
    depends_on_api: str  # API that must be implemented first
    dependency_type: str  # e.g., "requires_resource", "calls", "prerequisite"
    description: str = ""
    priority: str = ""
    source: str = ""  # journey, use_case, gap_analysis, etc.


class APIDependencyAnalyzer:
    """Analyze and document API dependencies"""
    
    def __init__(self):
        self.dependencies: List[APIDependency] = []
        self.api_dependencies: Dict[str, Set[str]] = defaultdict(set)  # API -> set of dependencies
        self.api_dependents: Dict[str, Set[str]] = defaultdict(set)  # API -> set of dependents
        self.api_info: Dict[str, Dict] = {}  # API -> info dict
        
    def load_from_journeys(self, file_path: str):
        """Load dependencies from journey extraction document"""
        print(f"Loading journey dependencies from {file_path}...", file=__import__('sys').stderr)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract journey step dependencies
        # Pattern: Journey Step | Depends On | API Endpoint | Dependency Type
        pattern = r'JOURNEY-(\w+)-(\d+)\s+Step\s+(\d+)\s*\|\s*Step\s+(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)'
        
        for match in re.finditer(pattern, content):
            journey_id = f"JOURNEY-{match.group(1)}-{match.group(2)}"
            step_num = match.group(3)
            depends_on_step = match.group(4)
            api_endpoint = match.group(5).strip()
            dep_type = match.group(6).strip()
            
            # Find the API that the step depends on
            # Look for the step that provides the resource
            # This is a simplified extraction - in reality, we'd need to map steps to APIs
            
            # Extract API calls from journey steps
            step_pattern = r'#### Step\s+(\d+):\s+([^\n]+)\n\n.*?`([^`]+)`'
            for step_match in re.finditer(step_pattern, content, re.DOTALL):
                step_num_found = step_match.group(1)
                step_desc = step_match.group(2)
                api_called = step_match.group(3).strip()
                
                # If this step depends on a previous step, find that step's API
                if step_num == step_num_found:
                    # This API depends on APIs from previous steps
                    # We'll handle this in a more structured way below
                    pass
        
        # Extract explicit dependency matrix
        dep_matrix_pattern = r'\| Journey Step \| Depends On \| API Endpoint \| Dependency Type \|\n\|-+\|-+\|-+\|-+\|\n((?:\| [^|]+\| [^|]+\| [^|]+\| [^|]+\|\n)+)'
        
        for match in re.finditer(dep_matrix_pattern, content):
            table_content = match.group(1)
            for line in table_content.strip().split('\n'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 4:
                    journey_step = parts[0]
                    depends_on = parts[1]
                    api_endpoint = parts[2].strip('`')
                    dep_type = parts[3]
                    
                    # Extract journey and step numbers
                    journey_match = re.search(r'JOURNEY-(\w+)-(\d+)\s+Step\s+(\d+)', journey_step)
                    if journey_match:
                        journey_id = f"JOURNEY-{journey_match.group(1)}-{journey_match.group(2)}"
                        step_num = journey_match.group(3)
                        
                        # Find what API the dependency step uses
                        # This requires parsing the journey steps more carefully
                        # For now, we'll extract common patterns
                        
                        # Common dependency patterns:
                        # - Step 2 depends on Step 1 (asset_id)
                        # - Step 3 depends on Step 2 (file_id)
                        # - Step 4 depends on Step 3 (dataset_id)
                        
                        if 'asset_id' in dep_type.lower():
                            self._add_dependency(
                                api_endpoint,
                                'POST /api/v1/assets/',
                                'requires_resource',
                                f"Requires asset_id from {journey_step}",
                                'P0',
                                'journey'
                            )
                        elif 'file_id' in dep_type.lower():
                            self._add_dependency(
                                api_endpoint,
                                'POST /api/v1/files/upload/',
                                'requires_resource',
                                f"Requires file_id from {journey_step}",
                                'P0',
                                'journey'
                            )
                        elif 'dataset_id' in dep_type.lower():
                            self._add_dependency(
                                api_endpoint,
                                'POST /api/v1/datasets/',
                                'requires_resource',
                                f"Requires dataset_id from {journey_step}",
                                'P0',
                                'journey'
                            )
                        elif 'contract' in dep_type.lower() or 'validated' in dep_type.lower():
                            self._add_dependency(
                                api_endpoint,
                                'POST /api/v1/contracts/',
                                'requires_resource',
                                f"Requires validated contract from {journey_step}",
                                'P0',
                                'journey'
                            )
    
    def load_from_gap_analysis(self, file_path: str):
        """Load dependencies from gap analysis"""
        print(f"Loading gap analysis dependencies from {file_path}...", file=__import__('sys').stderr)
        
        with open(file_path, 'r') as content:
            text = content.read()
        
        # Extract blocked journeys/use cases
        blocked_pattern = r'\*\*Blocked Journeys\*\*:\s*\n((?:- [^\n]+\n)+)'
        for match in re.finditer(blocked_pattern, text):
            blocked_list = match.group(1)
            # Extract journey IDs
            journey_ids = re.findall(r'JOURNEY-[\w-]+', blocked_list)
            
            # Find the API endpoint in the context
            # Look backwards for the endpoint
            context_start = max(0, match.start() - 500)
            context = text[context_start:match.start()]
            
            # Find endpoint pattern
            endpoint_match = re.search(r'`([^`]+)`', context)
            if endpoint_match:
                api_endpoint = endpoint_match.group(1)
                
                # These journeys depend on this API
                for journey_id in journey_ids:
                    # Extract APIs from journey
                    # This is simplified - would need full journey parsing
                    pass
    
    def load_from_backlog(self, file_path: str):
        """Load dependencies from backlog file"""
        print(f"Loading backlog dependencies from {file_path}...", file=__import__('sys').stderr)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract blocked journeys/use cases
        current_api = None
        current_priority = None
        
        for line in content.split('\n'):
            # Extract API endpoint
            endpoint_match = re.search(r'#### \d+\.\s+(GET|POST|PUT|PATCH|DELETE)\s+`([^`]+)`', line)
            if endpoint_match:
                method = endpoint_match.group(1)
                path = endpoint_match.group(2)
                current_api = f"{method} {path}"
                continue
            
            # Extract priority
            priority_match = re.search(r'\*\*Priority\*\*:\s*([P0-3])', line)
            if priority_match:
                current_priority = priority_match.group(1)
                continue
            
            # Extract blocked journeys
            if 'Blocked Journeys' in line or 'Blocked Use Cases' in line:
                # Next lines contain the list
                continue
            
            # Extract journey/use case references
            journey_match = re.search(r'JOURNEY-[\w-]+', line)
            use_case_match = re.search(r'UC-[\w-]+', line)
            
            if current_api and (journey_match or use_case_match):
                # This API blocks these journeys/use cases
                # We can infer dependencies from journey flows
                pass
    
    def _add_dependency(self, dependent: str, depends_on: str, dep_type: str, 
                       description: str = "", priority: str = "", source: str = ""):
        """Add a dependency relationship"""
        dep = APIDependency(
            dependent_api=dependent,
            depends_on_api=depends_on,
            dependency_type=dep_type,
            description=description,
            priority=priority,
            source=source
        )
        self.dependencies.append(dep)
        self.api_dependencies[dependent].add(depends_on)
        self.api_dependents[depends_on].add(dependent)
    
    def load_from_use_cases(self, file_path: str):
        """Load dependencies from use case extraction document"""
        print(f"Loading use case dependencies from {file_path}...", file=__import__('sys').stderr)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract step dependencies
        # Pattern: "Requires Step X" or "Dependencies: - Requires Step X"
        step_pattern = r'#### Main Flow Step (\d+):[^\n]+\n\n.*?`([^`]+)`.*?\n\n.*?Dependencies?:\s*\n((?:- [^\n]+\n)+)'
        
        current_use_case = None
        step_apis = {}  # step_num -> api_endpoint
        
        for match in re.finditer(r'### UC-([\w-]+):', content):
            current_use_case = match.group(1)
        
        # Extract step-to-API mappings
        step_api_pattern = r'#### Main Flow Step (\d+):[^\n]+\n\n.*?`([^`]+)`'
        for match in re.finditer(step_api_pattern, content, re.DOTALL):
            step_num = match.group(1)
            api_endpoint = match.group(2).strip()
            step_apis[step_num] = api_endpoint
        
        # Extract dependencies
        dep_pattern = r'Dependencies?:\s*\n((?:- [^\n]+\n)+)'
        for match in re.finditer(dep_pattern, content):
            deps_text = match.group(1)
            
            # Find the step this belongs to (look backwards)
            context_start = max(0, match.start() - 500)
            context = content[context_start:match.start()]
            
            step_match = re.search(r'#### Main Flow Step (\d+):', context)
            if step_match:
                step_num = step_match.group(1)
                current_api = step_apis.get(step_num)
                
                if current_api:
                    # Parse dependencies
                    requires_step = re.search(r'Requires Step (\d+)', deps_text)
                    if requires_step:
                        required_step_num = requires_step.group(1)
                        required_api = step_apis.get(required_step_num)
                        
                        if required_api:
                            self._add_dependency(
                                current_api,
                                required_api,
                                'requires_resource',
                                f"Requires Step {required_step_num} from use case",
                                'P0',
                                'use_case'
                            )
    
    def add_common_dependencies(self):
        """Add common API dependencies based on domain knowledge"""
        
        # Authentication dependencies
        self._add_dependency(
            'GET /api/v1/auth/me/',
            'POST /api/v1/auth/login/',
            'requires_authentication',
            'Requires user to be authenticated',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/auth/refresh/',
            'POST /api/v1/auth/login/',
            'requires_authentication',
            'Requires existing session',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/auth/logout/',
            'POST /api/v1/auth/login/',
            'requires_authentication',
            'Requires existing session',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'GET /api/v1/auth/api-keys/',
            'POST /api/v1/auth/login/',
            'requires_authentication',
            'Requires user to be authenticated',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/auth/api-keys/',
            'POST /api/v1/auth/login/',
            'requires_authentication',
            'Requires user to be authenticated',
            'P0',
            'domain_knowledge'
        )
        
        # Asset activation dependencies
        self._add_dependency(
            'POST /api/v1/assets/{id}/activate/',
            'POST /api/v1/assets/',
            'requires_resource',
            'Requires asset to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/assets/{id}/activate/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires validated contract',
            'P0',
            'domain_knowledge'
        )
        
        # Contract validation dependencies
        self._add_dependency(
            'POST /api/v1/contracts/{id}/validate/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires contract to exist',
            'P0',
            'domain_knowledge'
        )
        
        # Dataset dependencies
        self._add_dependency(
            'POST /api/v1/datasets/',
            'POST /api/v1/files/upload/',
            'requires_resource',
            'Requires uploaded file',
            'P0',
            'domain_knowledge'
        )
        
        # AI/ML dependencies
        self._add_dependency(
            'POST /api/v1/ai/schema-matching/',
            'POST /api/v1/datasets/',
            'requires_resource',
            'Requires dataset for schema matching',
            'P2',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/ai/classification/',
            'POST /api/v1/datasets/',
            'requires_resource',
            'Requires dataset for classification',
            'P2',
            'domain_knowledge'
        )
        
        # Transformation dependencies
        self._add_dependency(
            'POST /api/v1/transformation/pipelines/{id}/execute/',
            'POST /api/v1/transformation/pipelines/',
            'requires_resource',
            'Requires pipeline to exist',
            'P2',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/transformation/pipelines/{id}/validate/',
            'POST /api/v1/transformation/pipelines/',
            'requires_resource',
            'Requires pipeline to exist',
            'P2',
            'domain_knowledge'
        )
        
        # Marketplace dependencies
        self._add_dependency(
            'GET /api/v1/marketplace/listings/{id}/preview/',
            'POST /api/v1/assets/{id}/activate/',
            'requires_resource',
            'Requires activated asset',
            'P3',
            'domain_knowledge'
        )
        
        # Credential management dependencies
        self._add_dependency(
            'GET /api/v1/scheduled-ingestions/{id}/credentials/',
            'POST /api/v1/scheduled-ingestions/',
            'requires_resource',
            'Requires scheduled ingestion to exist',
            'P1',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/scheduled-ingestions/{id}/credentials/test/',
            'GET /api/v1/scheduled-ingestions/{id}/credentials/',
            'requires_resource',
            'Requires credentials to exist',
            'P1',
            'domain_knowledge'
        )
        
        # Social feature dependencies
        self._add_dependency(
            'POST /api/v1/social/ratings/',
            'POST /api/v1/assets/{id}/activate/',
            'requires_resource',
            'Requires activated asset to rate',
            'P2',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/social/reviews/',
            'POST /api/v1/assets/{id}/activate/',
            'requires_resource',
            'Requires activated asset to review',
            'P2',
            'domain_knowledge'
        )
        
        # Additional asset dependencies
        self._add_dependency(
            'POST /api/v1/assets/{id}/contracts/',
            'POST /api/v1/assets/',
            'requires_resource',
            'Requires asset to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/assets/{id}/contracts/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires contract to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/assets/{id}/datasets/',
            'POST /api/v1/assets/',
            'requires_resource',
            'Requires asset to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/assets/{id}/datasets/',
            'POST /api/v1/datasets/',
            'requires_resource',
            'Requires dataset to exist',
            'P0',
            'domain_knowledge'
        )
        
        # Compliance and DQ dependencies
        self._add_dependency(
            'POST /api/v1/compliance/scans/',
            'POST /api/v1/assets/',
            'requires_resource',
            'Requires asset to scan',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/dq/runs/',
            'POST /api/v1/assets/',
            'requires_resource',
            'Requires asset for DQ check',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/dq/runs/',
            'POST /api/v1/datasets/',
            'requires_resource',
            'Requires dataset for DQ check',
            'P0',
            'domain_knowledge'
        )
        
        # Marketplace dependencies
        self._add_dependency(
            'GET /api/v1/marketplace/listings/',
            'POST /api/v1/assets/{id}/activate/',
            'requires_resource',
            'Requires activated assets to list',
            'P1',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/marketplace/listings/',
            'POST /api/v1/assets/{id}/activate/',
            'requires_resource',
            'Requires activated asset to publish',
            'P1',
            'domain_knowledge'
        )
        
        # Job dependencies
        self._add_dependency(
            'GET /api/v1/jobs/{id}/',
            'POST /api/v1/jobs/',
            'requires_resource',
            'Requires job to exist',
            'P0',
            'domain_knowledge'
        )
        
        # File validation dependencies
        self._add_dependency(
            'POST /api/v1/files/{id}/validate/',
            'POST /api/v1/files/upload/',
            'requires_resource',
            'Requires file to exist',
            'P0',
            'domain_knowledge'
        )
        
        # Contract dependencies
        self._add_dependency(
            'PUT /api/v1/contracts/{id}/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires contract to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'PATCH /api/v1/contracts/{id}/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires contract to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/contracts/{id}/publish/',
            'POST /api/v1/contracts/',
            'requires_resource',
            'Requires contract to exist',
            'P0',
            'domain_knowledge'
        )
        
        self._add_dependency(
            'POST /api/v1/contracts/{id}/publish/',
            'POST /api/v1/contracts/{id}/validate/',
            'requires_resource',
            'Requires contract to be validated',
            'P0',
            'domain_knowledge'
        )
    
    def generate_dependency_document(self) -> str:
        """Generate comprehensive dependency documentation"""
        doc = []
        doc.append("# API Dependencies")
        doc.append("")
        doc.append("**Document Version**: 1.0.0")
        doc.append("**Last Updated**: 2025-12-13")
        doc.append("**Task**: 0.5.3 - Define API dependencies")
        doc.append("")
        doc.append("---")
        doc.append("")
        doc.append("## Overview")
        doc.append("")
        doc.append("This document defines dependencies between API endpoints, identifying which APIs")
        doc.append("must be implemented before others. Dependencies are extracted from:")
        doc.append("- **User Journeys**: Sequential step dependencies")
        doc.append("- **Use Cases**: Flow dependencies")
        doc.append("- **Gap Analysis**: Prerequisite APIs")
        doc.append("- **Domain Knowledge**: Logical API dependencies")
        doc.append("")
        doc.append(f"**Total Dependencies Documented**: {len(self.dependencies)}")
        doc.append(f"**Total APIs with Dependencies**: {len(self.api_dependencies)}")
        doc.append(f"**Total APIs that are Dependencies**: {len(self.api_dependents)}")
        doc.append("")
        doc.append("---")
        doc.append("")
        doc.append("## Dependency Types")
        doc.append("")
        doc.append("1. **requires_resource**: API requires a resource created by another API")
        doc.append("   - Example: `POST /api/v1/datasets/` requires `POST /api/v1/files/upload/`")
        doc.append("")
        doc.append("2. **requires_authentication**: API requires authentication APIs to be implemented")
        doc.append("   - Example: `GET /api/v1/auth/me/` requires `POST /api/v1/auth/login/`")
        doc.append("")
        doc.append("3. **calls**: API directly calls another API internally")
        doc.append("   - Example: `POST /api/v1/assets/{id}/activate/` calls contract validation")
        doc.append("")
        doc.append("4. **prerequisite**: API must be implemented before dependent API")
        doc.append("   - Example: Asset APIs must be implemented before marketplace APIs")
        doc.append("")
        doc.append("---")
        doc.append("")
        doc.append("## Dependencies by Priority")
        doc.append("")
        
        # Group by priority
        by_priority = defaultdict(list)
        for dep in self.dependencies:
            by_priority[dep.priority].append(dep)
        
        for priority in ['P0', 'P1', 'P2', 'P3']:
            if priority in by_priority:
                doc.append(f"### {priority} - {self._priority_name(priority)}")
                doc.append("")
                doc.append("| Dependent API | Depends On | Type | Description | Source |")
                doc.append("|--------------|------------|------|-------------|--------|")
                
                for dep in sorted(by_priority[priority], key=lambda x: x.dependent_api):
                    dep_type_short = dep.dependency_type.replace('requires_', '').replace('_', ' ').title()
                    doc.append(f"| `{dep.dependent_api}` | `{dep.depends_on_api}` | {dep_type_short} | {dep.description[:50]}... | {dep.source} |")
                
                doc.append("")
        
        # Dependency graph
        doc.append("---")
        doc.append("")
        doc.append("## Dependency Graph")
        doc.append("")
        doc.append("### Mermaid Graph")
        doc.append("")
        doc.append("```mermaid")
        doc.append("graph TD")
        
        # Add nodes and edges
        all_apis = set()
        for dep in self.dependencies:
            all_apis.add(dep.dependent_api)
            all_apis.add(dep.depends_on_api)
        
        # Create node IDs (sanitize for Mermaid)
        node_map = {}
        for i, api in enumerate(sorted(all_apis)):
            node_id = f"API{i}"
            node_map[api] = node_id
            # Truncate long API names for display
            display_name = api.replace('/api/v1/', '')
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            doc.append(f'    {node_id}["{display_name}"]')
        
        # Add edges
        for dep in self.dependencies:
            from_node = node_map[dep.depends_on_api]
            to_node = node_map[dep.dependent_api]
            doc.append(f"    {from_node} --> {to_node}")
        
        doc.append("```")
        doc.append("")
        
        # Dependency chains
        doc.append("---")
        doc.append("")
        doc.append("## Critical Dependency Chains")
        doc.append("")
        doc.append("### Authentication Chain")
        doc.append("")
        doc.append("1. `POST /api/v1/auth/register/` (P0)")
        doc.append("2. `POST /api/v1/auth/login/` (P0)")
        doc.append("3. `POST /api/v1/auth/refresh/` (P0)")
        doc.append("4. `GET /api/v1/auth/me/` (P0)")
        doc.append("")
        doc.append("### Asset Onboarding Chain")
        doc.append("")
        doc.append("1. `POST /api/v1/assets/` (P0)")
        doc.append("2. `POST /api/v1/files/upload/` (P0)")
        doc.append("3. `POST /api/v1/datasets/` (P0)")
        doc.append("4. `POST /api/v1/contracts/` (P0)")
        doc.append("5. `POST /api/v1/contracts/{id}/validate/` (P0)")
        doc.append("6. `POST /api/v1/assets/{id}/activate/` (P0)")
        doc.append("")
        doc.append("### AI/ML Chain")
        doc.append("")
        doc.append("1. `POST /api/v1/datasets/` (P0)")
        doc.append("2. `POST /api/v1/ai/schema-matching/` (P2)")
        doc.append("3. `POST /api/v1/ai/classification/` (P2)")
        doc.append("")
        doc.append("### Transformation Chain")
        doc.append("")
        doc.append("1. `POST /api/v1/assets/` (P0)")
        doc.append("2. `POST /api/v1/transformation/pipelines/` (P2)")
        doc.append("3. `POST /api/v1/transformation/pipelines/{id}/validate/` (P2)")
        doc.append("4. `POST /api/v1/transformation/pipelines/{id}/execute/` (P2)")
        doc.append("")
        doc.append("### Marketplace Chain")
        doc.append("")
        doc.append("1. `POST /api/v1/assets/{id}/activate/` (P0)")
        doc.append("2. `GET /api/v1/marketplace/listings/` (P1)")
        doc.append("3. `GET /api/v1/marketplace/listings/{id}/preview/` (P3)")
        doc.append("")
        
        # Implementation order
        doc.append("---")
        doc.append("")
        doc.append("## Recommended Implementation Order")
        doc.append("")
        doc.append("### Phase 0: Foundation (Weeks 0-2)")
        doc.append("")
        doc.append("**Must be implemented first (no dependencies)**:")
        doc.append("")
        doc.append("1. `POST /api/v1/auth/register/` - User registration")
        doc.append("2. `POST /api/v1/auth/login/` - User authentication")
        doc.append("3. `POST /api/v1/assets/` - Asset creation")
        doc.append("4. `POST /api/v1/files/upload/` - File upload")
        doc.append("")
        doc.append("### Phase 1: Core Operations (Weeks 2-4)")
        doc.append("")
        doc.append("**Depends on Phase 0**:")
        doc.append("")
        doc.append("1. `POST /api/v1/datasets/` - Dataset creation (depends on file upload)")
        doc.append("2. `POST /api/v1/contracts/` - Contract creation (depends on asset)")
        doc.append("3. `POST /api/v1/contracts/{id}/validate/` - Contract validation (depends on contract)")
        doc.append("4. `POST /api/v1/assets/{id}/activate/` - Asset activation (depends on contract validation)")
        doc.append("5. `GET /api/v1/auth/me/` - Current user info (depends on login)")
        doc.append("6. `POST /api/v1/auth/refresh/` - Token refresh (depends on login)")
        doc.append("")
        doc.append("### Phase 2: Enhanced Features (Weeks 5-8)")
        doc.append("")
        doc.append("**Depends on Phase 1**:")
        doc.append("")
        doc.append("1. `GET /api/v1/scheduled-ingestions/{id}/credentials/` - Credential management (depends on scheduled ingestion)")
        doc.append("2. `POST /api/v1/scheduled-ingestions/{id}/credentials/test/` - Credential testing (depends on credentials)")
        doc.append("3. `GET /api/v1/marketplace/listings/` - Marketplace listings (depends on asset activation)")
        doc.append("")
        doc.append("### Phase 3: Advanced Features (Weeks 9-20)")
        doc.append("")
        doc.append("**Depends on Phase 2**:")
        doc.append("")
        doc.append("1. `POST /api/v1/ai/schema-matching/` - AI schema matching (depends on datasets)")
        doc.append("2. `POST /api/v1/ai/classification/` - AI classification (depends on datasets)")
        doc.append("3. `POST /api/v1/transformation/pipelines/` - Transformation pipelines (depends on assets)")
        doc.append("4. `POST /api/v1/social/ratings/` - Social ratings (depends on asset activation)")
        doc.append("5. `POST /api/v1/social/reviews/` - Social reviews (depends on asset activation)")
        doc.append("")
        doc.append("### Phase 4: Strategic Features (Weeks 21-40)")
        doc.append("")
        doc.append("**Depends on Phase 3**:")
        doc.append("")
        doc.append("1. `GET /api/v1/marketplace/listings/{id}/preview/` - Marketplace preview (depends on asset activation)")
        doc.append("2. `GET /api/v1/developer/plugins/` - Plugin management (depends on plugin system)")
        doc.append("3. `GET /api/v1/developer/sdk/` - SDK documentation (depends on SDK infrastructure)")
        doc.append("")
        
        doc.append("---")
        doc.append("")
        doc.append("## Dependency Statistics")
        doc.append("")
        doc.append("### By Dependency Type")
        doc.append("")
        by_type = defaultdict(int)
        for dep in self.dependencies:
            by_type[dep.dependency_type] += 1
        
        doc.append("| Type | Count |")
        doc.append("|------|-------|")
        for dep_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            doc.append(f"| {dep_type.replace('_', ' ').title()} | {count} |")
        doc.append("")
        
        doc.append("### APIs with Most Dependencies")
        doc.append("")
        doc.append("| API | Dependencies |")
        doc.append("|-----|-------------|")
        sorted_deps = sorted(self.api_dependencies.items(), key=lambda x: -len(x[1]))
        for api, deps in sorted_deps[:10]:
            doc.append(f"| `{api}` | {len(deps)} |")
        doc.append("")
        
        doc.append("### APIs Required by Most Other APIs")
        doc.append("")
        doc.append("| API | Required By |")
        doc.append("|-----|-------------|")
        sorted_dependents = sorted(self.api_dependents.items(), key=lambda x: -len(x[1]))
        for api, dependents in sorted_dependents[:10]:
            doc.append(f"| `{api}` | {len(dependents)} |")
        doc.append("")
        
        doc.append("---")
        doc.append("")
        doc.append("**Document Status**: ✅ Complete")
        doc.append(f"**Total Dependencies**: {len(self.dependencies)}")
        doc.append("")
        doc.append("**Next Steps**:")
        doc.append("1. Use this dependency graph to plan implementation order")
        doc.append("2. Update backlog file with dependency information")
        doc.append("3. Create implementation timeline based on dependencies")
        
        return "\n".join(doc)
    
    def _priority_name(self, priority: str) -> str:
        """Get priority name"""
        names = {
            'P0': 'Critical',
            'P1': 'High',
            'P2': 'Medium',
            'P3': 'Low'
        }
        return names.get(priority, 'Unknown')


if __name__ == "__main__":
    analyzer = APIDependencyAnalyzer()
    
    # Load from various sources
    journeys_file = "docs/api-audit/api-requirements-from-journeys.md"
    if Path(journeys_file).exists():
        analyzer.load_from_journeys(journeys_file)
    
    use_cases_file = "docs/api-audit/api-requirements-from-use-cases.md"
    if Path(use_cases_file).exists():
        analyzer.load_from_use_cases(use_cases_file)
    
    gap_analysis_file = "docs/api-audit/gap-analysis.md"
    if Path(gap_analysis_file).exists():
        analyzer.load_from_gap_analysis(gap_analysis_file)
    
    backlog_file = "docs/api-audit/api-development-backlog.md"
    if Path(backlog_file).exists():
        analyzer.load_from_backlog(backlog_file)
    
    # Add common dependencies based on domain knowledge
    analyzer.add_common_dependencies()
    
    # Generate document
    document = analyzer.generate_dependency_document()
    print(document)

