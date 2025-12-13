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

### Features
- **[Features](FEATURES.md)** - Complete feature documentation

### Development
- **[Development Guide](DEVELOPMENT_GUIDE.md)** - Development workflows and practices
- **[Developer Onboarding](DEVELOPER_ONBOARDING.md)** - Complete onboarding guide
- **[Testing Guide](TESTING_GUIDE.md)** - Testing strategies and test execution
- **[Code Quality Standards](CODE_QUALITY_STANDARDS.md)** - Coding standards and best practices
- **[Bug Prevention Patterns](BUG_PREVENTION_PATTERNS.md)** - Bug prevention strategies
- **[Error Handling](ERROR_HANDLING.md)** - Error handling patterns and practices

### Deployment
- **[Docker Compose Deployment](DOCKER_COMPOSE_DEPLOYMENT.md)** - Deploy using Docker Compose
- **[Kubernetes Deployment](KUBERNETES_DEPLOYMENT.md)** - Production Kubernetes deployment
- **[Service Deployment Guide](SERVICE_DEPLOYMENT_GUIDE.md)** - Individual service deployment
- **[Docker Compose Structure](DOCKER_COMPOSE_STRUCTURE.md)** - Docker Compose configuration

### Operations
- **[Monitoring](MONITORING.md)** - Monitoring and observability
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Runbooks](RUNBOOKS.md)** - Operational runbooks

### Infrastructure
- **[Event Bus](EVENT_BUS.md)** - Event-driven communication
- **[Event Types Reference](EVENT_TYPES_REFERENCE.md)** - Event type documentation

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
│   └── WEBSOCKET_API.md        # WebSocket API
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
│   ├── DOCKER_COMPOSE_DEPLOYMENT.md # Docker Compose
│   ├── KUBERNETES_DEPLOYMENT.md     # Kubernetes
│   ├── SERVICE_DEPLOYMENT_GUIDE.md  # Service deployment
│   └── DOCKER_COMPOSE_STRUCTURE.md  # Docker structure
│
├── Operations
│   ├── MONITORING.md            # Monitoring
│   ├── TROUBLESHOOTING.md        # Troubleshooting
│   └── RUNBOOKS.md              # Runbooks
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
