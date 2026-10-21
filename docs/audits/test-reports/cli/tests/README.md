# CLI Tests

## Test Structure

### Unit Tests (`tests/unit/`)
- **Purpose**: Test CLI code logic, parsing, formatting, configuration, and authentication logic
- **Location**: `tests/unit/`
- **Mocks**: These tests may use mocks for external dependencies (API client) since they test CLI code itself, not API integration
- **Run**: `pytest tests/unit/`

### Integration Tests (`tests/integration/`)

#### `test_commands.py`
- **Purpose**: Test CLI command parsing, help text, and argument validation
- **Mocks**: Minimal - only tests CLI command structure, not API calls
- **Run**: `pytest tests/integration/test_commands.py`

#### `test_commands_real_api.py`
- **Purpose**: Test CLI commands against **real API services**
- **Requirements**: 
  - Django API service running (default: `http://localhost:8000`)
  - Database with test data
  - Services can be started with: `docker-compose up -d api db redis`
- **No Mocks**: Uses real API endpoints, real database, real authentication
- **Run**: `pytest tests/integration/test_commands_real_api.py`

## Running Tests

### Unit Tests Only
```bash
cd cli
pytest tests/unit/ -v
```

### Integration Tests (Command Parsing)
```bash
cd cli
pytest tests/integration/test_commands.py -v
```

### Integration Tests (Real API)
```bash
# Start services first
docker-compose up -d api db redis

# Run tests
cd cli
export API_BASE_URL=http://localhost:8000/api/v1
pytest tests/integration/test_commands_real_api.py -v
```

## Test Philosophy

Following the project's testing philosophy:
- **Unit tests**: Test individual components in isolation (may use mocks for external dependencies)
- **Integration tests**: Test components working together with **real services** (no mocks)
- **E2E tests**: Test complete user workflows with real services

The CLI integration tests (`test_commands_real_api.py`) follow this pattern by using real API services, real database, and real authentication - no mocks or stubs.

