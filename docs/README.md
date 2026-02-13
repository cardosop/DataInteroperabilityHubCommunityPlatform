# Data Interoperability Hub - Documentation

Complete documentation for the Data Interoperability Hub platform.

## Quick Start

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in minutes
- **[Developer Onboarding](DEVELOPER_ONBOARDING.md)** - Complete guide for new developers

## Core Documentation

### Architecture & Design
- **[Architecture](ARCHITECTURE.md)** - System architecture overview
- **[Services Architecture](SERVICES_ARCHITECTURE.md)** - Microservices and service boundaries
- **[Docker Compose Structure](DOCKER_COMPOSE_STRUCTURE.md)** - Docker Compose configuration

### APIs
- **[API Reference](API_REFERENCE.md)** - Complete API documentation (REST, GraphQL, WebSocket)
- **[API Standards](API_STANDARDS.md)** - API consistency standards and conventions
- **[API Endpoints Reference](API_ENDPOINTS_REFERENCE.md)** - Detailed endpoint documentation
- **[API Error Codes](API_ERROR_CODES.md)** - Comprehensive error code reference
- **[API Best Practices](API_BEST_PRACTICES.md)** - API development best practices
- **[API Versioning Policy](API_VERSIONING_POLICY.md)** - API versioning strategy
- **[API Testing Guide](API_TESTING_GUIDE.md)** - API testing strategies
- **[GraphQL API](GRAPHQL_API.md)** - GraphQL API documentation
- **[WebSocket API](WEBSOCKET_API.md)** - WebSocket API for real-time updates
- **[Webhook API](WEBHOOK_API.md)** - Webhook subscriptions and ODPS event delivery
- **[ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md)** - Complete guide for ODPS (Open Data Product Standard) integration
- **[ODPS Creation Flows](ODPS_CREATION_FLOWS.md)** - Detailed guide for Product-First, Technical-First, and Data-First flows
- **[ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md)** - Comprehensive guide for ODPS and ODCS version migrations
- **[ODPS Examples](ODPS_EXAMPLES.md)** - Complete examples for all ODPS scenarios

### Features
- **[Features](FEATURES.md)** - Complete feature documentation
- **[Scheduled Export Guide](SCHEDULED_EXPORT_GUIDE.md)** - User and operator guide for scheduled exports

### Development
- **[Development Guide](DEVELOPMENT_GUIDE.md)** - Development workflows and practices
- **[Developer Onboarding](DEVELOPER_ONBOARDING.md)** - Complete onboarding guide
- **[Testing Guide](TESTING_GUIDE.md)** - Testing strategies and test execution
- **[Code Quality Standards](CODE_QUALITY_STANDARDS.md)** - Coding standards and best practices
- **[Bug Prevention Patterns](BUG_PREVENTION_PATTERNS.md)** - Bug prevention strategies
- **[Error Handling](ERROR_HANDLING.md)** - Error handling patterns and practices

### Deployment
- **[Release criteria and gate](RELEASE.md)** - Release gate (Green Phase 12A + test summary report + sign-off) before staging/production
- **[Docker Compose Deployment](DOCKER_COMPOSE_DEPLOYMENT.md)** - Deploy using Docker Compose
- **[Kubernetes Deployment](KUBERNETES_DEPLOYMENT.md)** - Production Kubernetes deployment
- **[Service Deployment Guide](SERVICE_DEPLOYMENT_GUIDE.md)** - Individual service deployment
- **[Docker Compose Structure](DOCKER_COMPOSE_STRUCTURE.md)** - Docker Compose configuration

### Operations
- **[Monitoring](MONITORING.md)** - Monitoring and observability
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Runbooks](RUNBOOKS.md)** - Operational runbooks
- **[ODCS to ODPS Migration Guide](ODCS_TO_ODPS_MIGRATION_GUIDE.md)** - Complete guide for migrating ODCS contracts to ODPS
- **[Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md)** - Marketplace integration architecture and framework
- **[Marketplace Connector Development Guide](MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md)** - Guide for developing marketplace connectors
- **[Marketplace API Reference](MARKETPLACE_API_REFERENCE.md)** - Complete marketplace API documentation
- **[Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)** - User guide for marketplace integrations
- **[Marketplace Use Cases](MARKETPLACE_USE_CASES.md)** - Marketplace use cases and scenarios
- **[Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md)** - Marketplace user journey documentation
- **Marketplace-Specific Guides**:
  - [CKAN Guide](MARKETPLACE_CKAN_GUIDE.md)
  - [Snowflake Guide](MARKETPLACE_SNOWFLAKE_GUIDE.md)
  - [AWS Data Exchange Guide](MARKETPLACE_AWS_GUIDE.md)
  - [Azure Marketplace Guide](MARKETPLACE_AZURE_GUIDE.md)
  - [GCP Marketplace Guide](MARKETPLACE_GCP_GUIDE.md)
  - [Databricks Guide](MARKETPLACE_DATABRICKS_GUIDE.md)
  - [SAP Guide](MARKETPLACE_SAP_GUIDE.md)
  - [IBM Guide](MARKETPLACE_IBM_GUIDE.md)
  - [Oracle Guide](MARKETPLACE_ORACLE_GUIDE.md)
  - [Salesforce Guide](MARKETPLACE_SALESFORCE_GUIDE.md)
  - [DataRade Guide](MARKETPLACE_DATARADE_GUIDE.md)
  - [Dawex Guide](MARKETPLACE_DAWEX_GUIDE.md)
  - [NASDAQ Guide](MARKETPLACE_NASDAQ_GUIDE.md)
  - [ESRI Guide](MARKETPLACE_ESRI_GUIDE.md)
  - [Collibra Guide](MARKETPLACE_COLLIBRA_GUIDE.md)

### Infrastructure
- **[Event Bus](EVENT_BUS.md)** - Event-driven communication
- **[Event Types Reference](EVENT_TYPES_REFERENCE.md)** - Event type documentation

### CLI & SDK
- **[CLI Tool](../cli/README.md)** - Command-line interface documentation
- **[Python SDK](../sdk/python/README.md)** - Python SDK documentation
- **CLI Usage Guides**:
  - [ODPS Usage Guide](../cli/docs/ODPS_USAGE.md) - ODPS contract management commands
  - [Marketplace Usage Guide](../cli/docs/MARKETPLACE_USAGE.md) - Marketplace integration commands
  - [BaaS Usage Guide](../cli/docs/BAAS_USAGE.md) - BaaS platform commands
  - [ODH Usage Guide](../cli/docs/ODH_USAGE.md) - ML/ODH integration commands
  - [Model Serving Usage Guide](../cli/docs/MODEL_SERVING_USAGE.md) - Model serving and A/B testing commands
- **SDK Usage Guides**:
  - [ODPS Usage Guide](../sdk/python/docs/ODPS_USAGE.md) - ODPS contract management APIs
  - [Marketplace Usage Guide](../sdk/python/docs/MARKETPLACE_USAGE.md) - Marketplace integration APIs
  - [BaaS Usage Guide](../sdk/python/docs/BAAS_USAGE.md) - BaaS platform APIs
  - [ODH Usage Guide](../sdk/python/docs/ODH_USAGE.md) - ML/ODH integration APIs
  - [Model Serving Usage Guide](../sdk/python/docs/MODEL_SERVING_USAGE.md) - Model serving and A/B testing APIs

## Documentation Structure

```
docs/
├── README.md                    # This file
├── QUICK_START.md               # Quick start guide
├── ARCHITECTURE.md              # System architecture
├── SERVICES_ARCHITECTURE.md     # Services architecture
├── DOCKER_COMPOSE_STRUCTURE.md  # Docker Compose structure
│
├── API Documentation
│   ├── API_REFERENCE.md         # Complete API reference
│   ├── API_STANDARDS.md         # API standards
│   ├── API_ENDPOINTS_REFERENCE.md # Endpoint reference
│   ├── API_ERROR_CODES.md       # Error codes
│   ├── API_BEST_PRACTICES.md    # Best practices
│   ├── API_VERSIONING_POLICY.md # Versioning policy
│   ├── API_TESTING_GUIDE.md     # API testing
│   ├── GRAPHQL_API.md          # GraphQL API
│   ├── WEBSOCKET_API.md        # WebSocket API
│   ├── WEBHOOK_API.md          # Webhook API
│   └── ODPS_INTEGRATION_GUIDE.md # ODPS integration guide
│
├── Features
│   └── FEATURES.md              # Feature overview
│
├── Development
│   ├── DEVELOPMENT_GUIDE.md     # Development guide
│   ├── DEVELOPER_ONBOARDING.md  # Onboarding
│   ├── TESTING_GUIDE.md         # Testing guide
│   ├── CODE_QUALITY_STANDARDS.md # Quality standards
│   ├── BUG_PREVENTION_PATTERNS.md # Bug prevention
│   └── ERROR_HANDLING.md        # Error handling
│
├── Deployment
│   ├── RELEASE.md                   # Release criteria and gate
│   ├── DOCKER_COMPOSE_DEPLOYMENT.md # Docker Compose
│   ├── KUBERNETES_DEPLOYMENT.md     # Kubernetes
│   ├── SERVICE_DEPLOYMENT_GUIDE.md  # Service deployment
│   └── DOCKER_COMPOSE_STRUCTURE.md  # Docker structure
│
├── Operations
│   ├── MONITORING.md            # Monitoring
│   ├── TROUBLESHOOTING.md        # Troubleshooting
│   ├── RUNBOOKS.md              # Runbooks
│   └── ODCS_TO_ODPS_MIGRATION_GUIDE.md # ODCS to ODPS migration guide
│
├── Infrastructure
│   ├── EVENT_BUS.md             # Event bus
│   └── EVENT_TYPES_REFERENCE.md  # Event types
│
└── deprecated-doc/              # Historical documentation
    ├── archive/                  # Archived documentation
    ├── test-docs/                # Test documentation
    ├── deployment-docs/          # Deployment details
    ├── strategy-docs/            # Strategy documents
    ├── analysis-docs/            # Analysis documents
    ├── feature-docs/             # Feature implementation details
    ├── implementation-summaries/ # Implementation summaries
    ├── phase-reports/            # Phase reports
    ├── migration-strategies/      # Migration strategies
    ├── test-results/             # Test results
    └── fix-summaries/            # Fix summaries
```

## Quick Links

- **API Base URL**: `http://localhost:8000/api/v1`
- **GraphQL Endpoint**: `http://localhost:8000/graphql`
- **API Documentation**: `http://localhost:8000/api-docs/`
- **Health Check**: `http://localhost:8000/health`
- **Swagger UI**: `http://localhost:8000/api-docs/`
- **ReDoc**: `http://localhost:8000/api-docs/redoc/`

## Deprecated Documentation

Historical documentation, detailed implementation guides, user journey mappings, and other non-essential documentation have been moved to `deprecated-doc/` for reference:

- **archive/** - Archived detailed documentation
- **test-docs/** - Test documentation
- **deployment-docs/** - Deployment details
- **strategy-docs/** - Strategy documents
- **analysis-docs/** - Analysis documents
- **feature-docs/** - Feature implementation details
- **implementation-summaries/** - Implementation summaries
- **phase-reports/** - Phase reports
- **migration-strategies/** - Migration strategies
- **test-results/** - Test results
- **fix-summaries/** - Fix summaries

**Note**: Deprecated documentation may not reflect the current state of the application. For current documentation, refer to the main documentation above.

## Contributing

When updating documentation:
1. Keep documentation current with code changes
2. Use clear, concise language
3. Include code examples where helpful
4. Update the table of contents when adding new sections
5. Mark deprecated features clearly
6. Move outdated documentation to `deprecated-doc/archive/`

## Related Resources

- [OpenSpec Specifications](../openspec/) - Specification-driven development
- [Examples](../examples/) - Code examples
- [Runbooks](runbooks/) - Operational runbooks
