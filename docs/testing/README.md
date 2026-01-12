# Testing Documentation

This directory contains comprehensive documentation for testing the Data Interoperability Hub.

## Overview

The Data Interoperability Hub uses a comprehensive testing strategy with multiple test types:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user journeys and workflows
- **Performance Tests**: Test system performance under load
- **Contract Tests**: Test API contracts

## Documentation

### [Connector End-to-End Testing Guide](./CONNECTOR_E2E_TESTING.md)

Comprehensive guide for end-to-end testing of marketplace connectors, including:

- **Overview**: Purpose and scope of E2E testing
- **Prerequisites**: Environment variables, database setup, service dependencies
- **Test Plan Structure**: Four-phase testing approach (Connection → Discovery → Asset Creation → Verification)
- **Detailed Test Scenarios**: Step-by-step test scenarios for dados.gov.br and Snowflake connectors
- **Verification Checklist**: Comprehensive checklist for validating test results
- **Troubleshooting Guide**: Common issues and resolution steps
- **Running Tests**: Instructions for running tests via pytest and management commands
- **Best Practices**: Engineering-grade testing practices

**Key Features**:
- Real connections only (no mocks/stubs)
- Root cause analysis and fixes
- Complete workflow verification
- Comprehensive error handling

## Testing Strategy

### E2E Testing

E2E tests validate complete workflows from connection establishment through asset creation and verification. They use **real marketplace instances and real connections** - no mocks or stubs.

**See**: [Connector End-to-End Testing Guide](./CONNECTOR_E2E_TESTING.md)

### Integration Testing

Integration tests verify component interactions within the system, including:
- Service-to-service communication
- Database operations
- Workflow orchestration
- Event handling

**See**: [Testing Guide](../TESTING_GUIDE.md)

### Unit Testing

Unit tests verify individual components in isolation, including:
- Model validation
- Service methods
- Utility functions
- Business logic

**See**: [Testing Guide](../TESTING_GUIDE.md)

## Quick Start

### Running E2E Tests

```bash
# Test both connectors
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source both \
  --limit 5 \
  --wait \
  --verify-assets

# Test only dados.gov.br
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 10 \
  --wait \
  --verify-assets
```

### Running Pytest Tests

```bash
# Run all E2E tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py \
  -v \
  -m integration

# Run specific test
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_connection_and_discovery \
  -v
```

## Related Documentation

- [Testing Guide](../TESTING_GUIDE.md): General testing guide for the platform
- [Troubleshooting Guide](../TROUBLESHOOTING.md): General troubleshooting guide
- [Runbooks](../RUNBOOKS.md): Operational runbooks including marketplace connector deployment
- [Marketplace Connector Development Guide](../connectors/DEVELOPMENT.md): Development guide for marketplace connectors

