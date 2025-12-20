#!/usr/bin/env python3
"""
Document Integration Requirements for OpenAPI Specifications

This script analyzes API endpoints and documents:
- Service dependencies (internal services)
- Database requirements (models, tables)
- External service dependencies (LLM, connectors, etc.)
- Event publishing requirements
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import re

@dataclass
class ServiceDependency:
    """Service dependency definition"""
    service_name: str
    service_type: str  # 'internal', 'external', 'infrastructure'
    endpoint: Optional[str] = None
    description: str = ""
    required: bool = True
    timeout_ms: Optional[int] = None

@dataclass
class DatabaseRequirement:
    """Database requirement definition"""
    model_name: str
    operations: List[str]  # ['read', 'write', 'delete']
    description: str = ""
    indexes: List[str] = field(default_factory=list)

@dataclass
class EventRequirement:
    """Event publishing requirement"""
    event_type: str
    event_data: Dict
    description: str = ""
    required: bool = True

@dataclass
class IntegrationRequirements:
    """Complete integration requirements for an endpoint"""
    endpoint_path: str
    method: str
    service_dependencies: List[ServiceDependency] = field(default_factory=list)
    database_requirements: List[DatabaseRequirement] = field(default_factory=list)
    external_services: List[ServiceDependency] = field(default_factory=list)
    event_requirements: List[EventRequirement] = field(default_factory=list)
    infrastructure_dependencies: List[str] = field(default_factory=list)

class IntegrationRequirementsDocumenter:
    """Documents integration requirements for API endpoints"""
    
    def __init__(self):
        # Internal service mappings
        self.internal_services = {
            'datacontract-service': {
                'url': 'http://datacontract-service:8080',
                'description': 'Contract validation and conversion',
                'endpoints': ['/validate', '/lint', '/convert']
            },
            'dq-service': {
                'url': 'http://dq-service:8083',
                'description': 'Data quality checks',
                'endpoints': ['/run', '/profiles']
            },
            'compliance-service': {
                'url': 'http://compliance-service:8082',
                'description': 'Compliance scanning and PII detection',
                'endpoints': ['/run', '/regulations']
            },
            'semantic-service': {
                'url': 'http://semantic-service:8081',
                'description': 'RDF mapping and SPARQL queries',
                'endpoints': ['/map/contract', '/map/asset', '/sparql']
            },
            'search-service': {
                'url': 'http://search-service:8085',
                'description': 'Full-text search',
                'endpoints': ['/search', '/suggest']
            },
            'observability-service': {
                'url': 'http://observability-service:8086',
                'description': 'Data observability and monitoring',
                'endpoints': ['/freshness', '/volume', '/schema-drift']
            },
        }
        
        # External service mappings
        self.external_services = {
            'llm-service': {
                'description': 'Large Language Model service for natural language processing',
                'providers': ['OpenAI', 'Anthropic', 'Self-hosted'],
                'timeout_ms': 30000
            },
            'ai-service': {
                'description': 'AI service for schema matching and classification',
                'providers': ['OpenAI', 'Anthropic', 'Self-hosted'],
                'timeout_ms': 15000
            },
            'connector-services': {
                'description': 'Data source connectors (S3, GCS, Azure, Database, FTP, etc.)',
                'timeout_ms': 5000
            },
            'email-service': {
                'description': 'Email delivery service for notifications',
                'providers': ['SMTP', 'SendGrid', 'AWS SES'],
                'timeout_ms': 5000
            },
        }
        
        # Infrastructure dependencies
        self.infrastructure = {
            'postgresql': {
                'description': 'Primary database for all data persistence',
                'required': True
            },
            'redis': {
                'description': 'Job queue, caching, and event bus',
                'required': True
            },
            'minio': {
                'description': 'S3-compatible object storage for files and datasets',
                'required': True
            },
            'jena-fuseki': {
                'description': 'RDF triple store for semantic data',
                'required': False
            },
        }
        
        # Endpoint-specific integration mappings
        self.endpoint_integrations = {
            # Authentication endpoints
            'POST /auth/register/': {
                'database': [
                    DatabaseRequirement('User', ['write'], 'Create new user account'),
                    DatabaseRequirement('Tenant', ['read'], 'Validate tenant if provided'),
                    DatabaseRequirement('APIKey', ['read'], 'Check for existing API keys'),
                ],
                'external_services': [
                    ServiceDependency('email-service', 'external', description='Send welcome email (optional)', required=False)
                ],
                'events': [
                    EventRequirement('user.created', {'user_id': 'uuid'}, 'User registration event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/auth/register/': {
                'database': [
                    DatabaseRequirement('User', ['write'], 'Create new user account'),
                    DatabaseRequirement('Tenant', ['read'], 'Validate tenant if provided'),
                    DatabaseRequirement('APIKey', ['read'], 'Check for existing API keys'),
                ],
                'external_services': [
                    ServiceDependency('email-service', 'external', description='Send welcome email (optional)', required=False)
                ],
                'events': [
                    EventRequirement('user.created', {'user_id': 'uuid'}, 'User registration event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'GET /auth/me/': {
                'database': [
                    DatabaseRequirement('User', ['read'], 'Get current user information'),
                    DatabaseRequirement('Tenant', ['read'], 'Get tenant information'),
                ],
                'infrastructure': ['postgresql', 'redis']  # Redis for caching
            },
            'GET /api/v1/auth/me/': {
                'database': [
                    DatabaseRequirement('User', ['read'], 'Get current user information'),
                    DatabaseRequirement('Tenant', ['read'], 'Get tenant information'),
                ],
                'infrastructure': ['postgresql', 'redis']  # Redis for caching
            },
            
            # Credential management endpoints
            'GET /scheduled-ingestions/{id}/credentials/': {
                'database': [
                    DatabaseRequirement('ScheduledIngestion', ['read'], 'Get scheduled ingestion'),
                ],
                'infrastructure': ['postgresql']
            },
            'GET /api/v1/scheduled-ingestions/{id}/credentials/': {
                'database': [
                    DatabaseRequirement('ScheduledIngestion', ['read'], 'Get scheduled ingestion'),
                ],
                'infrastructure': ['postgresql']
            },
            'POST /scheduled-ingestions/{id}/credentials/test/': {
                'database': [
                    DatabaseRequirement('ScheduledIngestion', ['read'], 'Get scheduled ingestion and credentials'),
                ],
                'external_services': [
                    ServiceDependency('connector-services', 'external', description='Test connection to data source', timeout_ms=30000)
                ],
                'infrastructure': ['postgresql']
            },
            'POST /api/v1/scheduled-ingestions/{id}/credentials/test/': {
                'database': [
                    DatabaseRequirement('ScheduledIngestion', ['read'], 'Get scheduled ingestion and credentials'),
                ],
                'external_services': [
                    ServiceDependency('connector-services', 'external', description='Test connection to data source', timeout_ms=30000)
                ],
                'infrastructure': ['postgresql']
            },
            
            # AI/ML endpoints
            'POST /ai/natural-language-search/': {
                'database': [
                    DatabaseRequirement('Asset', ['read'], 'Search assets'),
                    DatabaseRequirement('Contract', ['read'], 'Search contracts'),
                ],
                'external_services': [
                    ServiceDependency('llm-service', 'external', description='Natural language query understanding', timeout_ms=30000)
                ],
                'internal_services': [
                    ServiceDependency('search-service', 'internal', '/search', 'Execute search query', timeout_ms=5000)
                ],
                'infrastructure': ['postgresql', 'redis']  # Redis for query caching
            },
            'POST /api/v1/ai/natural-language-search/': {
                'database': [
                    DatabaseRequirement('Asset', ['read'], 'Search assets'),
                    DatabaseRequirement('Contract', ['read'], 'Search contracts'),
                ],
                'external_services': [
                    ServiceDependency('llm-service', 'external', description='Natural language query understanding', timeout_ms=30000)
                ],
                'internal_services': [
                    ServiceDependency('search-service', 'internal', '/search', 'Execute search query', timeout_ms=5000)
                ],
                'infrastructure': ['postgresql', 'redis']  # Redis for query caching
            },
            'POST /ai/schema-matching/': {
                'database': [
                    DatabaseRequirement('Contract', ['read'], 'Get target contract schema'),
                    DatabaseRequirement('Asset', ['read'], 'Get source asset schema'),
                ],
                'external_services': [
                    ServiceDependency('ai-service', 'external', description='AI-powered schema matching', timeout_ms=15000)
                ],
                'events': [
                    EventRequirement('ai.schema_matching.completed', {'matching_id': 'uuid', 'confidence': 'float'}, 'Schema matching completion event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/ai/schema-matching/': {
                'database': [
                    DatabaseRequirement('Contract', ['read'], 'Get target contract schema'),
                    DatabaseRequirement('Asset', ['read'], 'Get source asset schema'),
                ],
                'external_services': [
                    ServiceDependency('ai-service', 'external', description='AI-powered schema matching', timeout_ms=15000)
                ],
                'events': [
                    EventRequirement('ai.schema_matching.completed', {'matching_id': 'uuid', 'confidence': 'float'}, 'Schema matching completion event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            
            # Social feature endpoints
            'POST /social/ratings/': {
                'database': [
                    DatabaseRequirement('Rating', ['write'], 'Create rating'),
                    DatabaseRequirement('Asset', ['read', 'write'], 'Update asset quality score'),
                ],
                'events': [
                    EventRequirement('social.rating.created', {'rating_id': 'uuid', 'asset_id': 'uuid'}, 'Rating creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/social/ratings/': {
                'database': [
                    DatabaseRequirement('Rating', ['write'], 'Create rating'),
                    DatabaseRequirement('Asset', ['read', 'write'], 'Update asset quality score'),
                ],
                'events': [
                    EventRequirement('social.rating.created', {'rating_id': 'uuid', 'asset_id': 'uuid'}, 'Rating creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /social/reviews/': {
                'database': [
                    DatabaseRequirement('Review', ['write'], 'Create review'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                ],
                'events': [
                    EventRequirement('social.review.created', {'review_id': 'uuid', 'asset_id': 'uuid'}, 'Review creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/social/reviews/': {
                'database': [
                    DatabaseRequirement('Review', ['write'], 'Create review'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                ],
                'events': [
                    EventRequirement('social.review.created', {'review_id': 'uuid', 'asset_id': 'uuid'}, 'Review creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /social/comments/': {
                'database': [
                    DatabaseRequirement('Comment', ['write'], 'Create comment'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                ],
                'events': [
                    EventRequirement('social.comment.created', {'comment_id': 'uuid', 'asset_id': 'uuid'}, 'Comment creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/social/comments/': {
                'database': [
                    DatabaseRequirement('Comment', ['write'], 'Create comment'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                ],
                'events': [
                    EventRequirement('social.comment.created', {'comment_id': 'uuid', 'asset_id': 'uuid'}, 'Comment creation event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /social/communities/': {
                'database': [
                    DatabaseRequirement('Community', ['write'], 'Create or join community'),
                    DatabaseRequirement('User', ['read'], 'Get user information'),
                ],
                'events': [
                    EventRequirement('social.community.created', {'community_id': 'uuid'}, 'Community creation event'),
                    EventRequirement('social.community.joined', {'community_id': 'uuid', 'user_id': 'uuid'}, 'Community join event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            'POST /api/v1/social/communities/': {
                'database': [
                    DatabaseRequirement('Community', ['write'], 'Create or join community'),
                    DatabaseRequirement('User', ['read'], 'Get user information'),
                ],
                'events': [
                    EventRequirement('social.community.created', {'community_id': 'uuid'}, 'Community creation event'),
                    EventRequirement('social.community.joined', {'community_id': 'uuid', 'user_id': 'uuid'}, 'Community join event')
                ],
                'infrastructure': ['postgresql', 'redis']
            },
            
            # Marketplace endpoints
            'GET /marketplace/listings/{id}/preview/': {
                'database': [
                    DatabaseRequirement('MarketplaceListing', ['read'], 'Get marketplace listing'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                    DatabaseRequirement('Dataset', ['read'], 'Get dataset for preview'),
                ],
                'internal_services': [
                    ServiceDependency('dq-service', 'internal', '/run', 'Get data quality metrics for preview', required=False)
                ],
                'infrastructure': ['postgresql', 'minio']  # MinIO for dataset access
            },
            'GET /api/v1/marketplace/listings/{id}/preview/': {
                'database': [
                    DatabaseRequirement('MarketplaceListing', ['read'], 'Get marketplace listing'),
                    DatabaseRequirement('Asset', ['read'], 'Get asset information'),
                    DatabaseRequirement('Dataset', ['read'], 'Get dataset for preview'),
                ],
                'internal_services': [
                    ServiceDependency('dq-service', 'internal', '/run', 'Get data quality metrics for preview', required=False)
                ],
                'infrastructure': ['postgresql', 'minio']  # MinIO for dataset access
            },
            
            # Developer experience endpoints
            'GET /developer/plugins/': {
                'database': [
                    DatabaseRequirement('Plugin', ['read'], 'List available plugins'),
                ],
                'infrastructure': ['postgresql']
            },
            'GET /api/v1/developer/plugins/': {
                'database': [
                    DatabaseRequirement('Plugin', ['read'], 'List available plugins'),
                ],
                'infrastructure': ['postgresql']
            },
            'GET /developer/sdk/': {
                'database': [
                    DatabaseRequirement('SDKDocumentation', ['read'], 'Get SDK documentation'),
                ],
                'infrastructure': ['postgresql']
            },
            'GET /api/v1/developer/sdk/': {
                'database': [
                    DatabaseRequirement('SDKDocumentation', ['read'], 'Get SDK documentation'),
                ],
                'infrastructure': ['postgresql']
            },
        }
    
    def get_integration_requirements(self, endpoint_path: str, method: str) -> IntegrationRequirements:
        """Get integration requirements for an endpoint"""
        # Try exact match first
        key = f"{method.upper()} {endpoint_path}"
        
        # Also try with /api/v1/ prefix
        key_with_prefix = f"{method.upper()} /api/v1{endpoint_path}"
        
        # Try both keys
        config = None
        if key in self.endpoint_integrations:
            config = self.endpoint_integrations[key]
        elif key_with_prefix in self.endpoint_integrations:
            config = self.endpoint_integrations[key_with_prefix]
        else:
            # Try pattern matching (e.g., /auth/register/ matches /api/v1/auth/register/)
            for pattern_key, pattern_config in self.endpoint_integrations.items():
                pattern_method, pattern_path = pattern_key.split(' ', 1)
                if pattern_method == method.upper():
                    # Remove /api/v1/ prefix from pattern if present
                    pattern_path_clean = pattern_path.replace('/api/v1', '')
                    if endpoint_path == pattern_path_clean or endpoint_path.endswith(pattern_path_clean):
                        config = pattern_config
                        break
        
        if config:
            return IntegrationRequirements(
                endpoint_path=endpoint_path,
                method=method.upper(),
                service_dependencies=config.get('internal_services', []),
                database_requirements=config.get('database', []),
                external_services=config.get('external_services', []),
                event_requirements=config.get('events', []),
                infrastructure_dependencies=config.get('infrastructure', ['postgresql', 'redis'])
            )
        
        # Default requirements for unknown endpoints
        return IntegrationRequirements(
            endpoint_path=endpoint_path,
            method=method.upper(),
            infrastructure_dependencies=['postgresql', 'redis']
        )
    
    def add_integration_requirements_to_spec(self, spec_path: Path) -> bool:
        """Add integration requirements to OpenAPI spec"""
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            
            if not spec or 'paths' not in spec:
                print(f"Warning: Invalid OpenAPI spec: {spec_path}")
                return False
            
            modified = False
            
            # Process each path
            for path, path_item in spec['paths'].items():
                # Normalize path - ensure it starts with /
                normalized_path = path
                if not path.startswith('/'):
                    normalized_path = f"/{path}"
                
                # Process each method
                for method in ['get', 'post', 'put', 'patch', 'delete']:
                    if method not in path_item:
                        continue
                    
                    operation = path_item[method]
                    
                    # Get integration requirements
                    requirements = self.get_integration_requirements(normalized_path, method)
                    
                    # Add integration requirements to operation description
                    if 'description' not in operation:
                        operation['description'] = ""
                    
                    integration_section = self._format_integration_requirements(requirements)
                    
                    if integration_section and integration_section not in operation['description']:
                        operation['description'] += f"\n\n{integration_section}"
                        modified = True
                    
                    # Add/update x-integration-requirements extension
                    serialized = self._serialize_requirements(requirements)
                    if 'x-integration-requirements' not in operation or operation['x-integration-requirements'] != serialized:
                        operation['x-integration-requirements'] = serialized
                        modified = True
            
            if modified:
                # Write back
                with open(spec_path, 'w', encoding='utf-8') as f:
                    yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                return True
            
            return False
        
        except Exception as e:
            print(f"Error processing {spec_path}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _format_integration_requirements(self, requirements: IntegrationRequirements) -> str:
        """Format integration requirements as markdown"""
        sections = []
        
        # Service Dependencies
        if requirements.service_dependencies:
            sections.append("**Service Dependencies:**")
            for dep in requirements.service_dependencies:
                timeout = f" (timeout: {dep.timeout_ms}ms)" if dep.timeout_ms else ""
                sections.append(f"- {dep.service_name}: {dep.description}{timeout}")
        
        # Database Requirements
        if requirements.database_requirements:
            sections.append("**Database Requirements:**")
            for db_req in requirements.database_requirements:
                ops = ', '.join(db_req.operations)
                sections.append(f"- {db_req.model_name} model: {ops} operations - {db_req.description}")
        
        # External Services
        if requirements.external_services:
            sections.append("**External Service Dependencies:**")
            for ext in requirements.external_services:
                timeout = f" (timeout: {ext.timeout_ms}ms)" if ext.timeout_ms else ""
                required = "Required" if ext.required else "Optional"
                sections.append(f"- {ext.service_name}: {ext.description} ({required}){timeout}")
        
        # Event Publishing
        if requirements.event_requirements:
            sections.append("**Event Publishing:**")
            for event in requirements.event_requirements:
                required = "Required" if event.required else "Optional"
                sections.append(f"- Publishes `{event.event_type}` event: {event.description} ({required})")
        
        # Infrastructure
        if requirements.infrastructure_dependencies:
            sections.append("**Infrastructure Dependencies:**")
            for infra in requirements.infrastructure_dependencies:
                infra_info = self.infrastructure.get(infra, {})
                desc = infra_info.get('description', infra)
                sections.append(f"- {infra}: {desc}")
        
        return "\n".join(sections) if sections else ""
    
    def _serialize_requirements(self, requirements: IntegrationRequirements) -> Dict:
        """Serialize requirements to dict for x-integration-requirements extension"""
        return {
            'service_dependencies': [
                {
                    'service_name': dep.service_name,
                    'service_type': dep.service_type,
                    'endpoint': dep.endpoint,
                    'description': dep.description,
                    'required': dep.required,
                    'timeout_ms': dep.timeout_ms
                }
                for dep in requirements.service_dependencies
            ],
            'database_requirements': [
                {
                    'model_name': db.model_name,
                    'operations': db.operations,
                    'description': db.description,
                    'indexes': db.indexes
                }
                for db in requirements.database_requirements
            ],
            'external_services': [
                {
                    'service_name': ext.service_name,
                    'service_type': ext.service_type,
                    'description': ext.description,
                    'required': ext.required,
                    'timeout_ms': ext.timeout_ms
                }
                for ext in requirements.external_services
            ],
            'event_requirements': [
                {
                    'event_type': event.event_type,
                    'event_data': event.event_data,
                    'description': event.description,
                    'required': event.required
                }
                for event in requirements.event_requirements
            ],
            'infrastructure_dependencies': requirements.infrastructure_dependencies
        }
    
    def process_all_specs(self, contracts_dir: Path) -> Dict[str, bool]:
        """Process all OpenAPI specs in directory"""
        results = {}
        
        yaml_files = list(contracts_dir.rglob('*.yaml')) + list(contracts_dir.rglob('*.yml'))
        
        for spec_file in yaml_files:
            if spec_file.name in ['README.md']:
                continue
            
            print(f"Processing: {spec_file.relative_to(contracts_dir.parent)}")
            success = self.add_integration_requirements_to_spec(spec_file)
            results[str(spec_file)] = success
        
        return results

def main():
    """Main execution"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    contracts_dir = repo_root / 'docs' / 'api-contracts' / 'missing'
    
    if not contracts_dir.exists():
        print(f"Error: Contracts directory not found at {contracts_dir}")
        return 1
    
    documenter = IntegrationRequirementsDocumenter()
    results = documenter.process_all_specs(contracts_dir)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\n✅ Processed {total_count} OpenAPI specs")
    print(f"   - Modified: {success_count}")
    print(f"   - Unchanged: {total_count - success_count}")
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())

