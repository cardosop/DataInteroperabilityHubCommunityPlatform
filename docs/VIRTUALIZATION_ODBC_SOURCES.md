# Virtualization — ODBC Sources

This document describes how to configure and use ODBC sources for virtual datasets in the Data Interoperability Hub.

## Overview

ODBC (Open Database Connectivity) sources allow virtual datasets to query any database that exposes an ODBC driver. The Hub supports two configuration modes:

1. **Connection string** — Full ODBC connection string (e.g. `DRIVER={...};SERVER=...;DATABASE=...`)
2. **Host + Database** — Individual fields (host, port, database, username, password, driver)

## Configuration

### Connection String Mode

Use when you have a pre-built ODBC connection string or DSN:

```json
{
  "type": "odbc",
  "connection_string": "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=hub;UID=hub;PWD=hub"
}
```

Or with DSN:

```json
{
  "type": "odbc",
  "connection_string": "DSN=MyPostgresDSN;PWD=secret"
}
```

### Host + Database Mode

Use when configuring via individual fields (common for PostgreSQL, MySQL, SQL Server):

```json
{
  "type": "odbc",
  "host": "localhost",
  "port": 5432,
  "database": "hub",
  "username": "hub",
  "password": "hub",
  "driver": "PostgreSQL Unicode"
}
```

| Field      | Required | Description |
|-----------|----------|--------------|
| `host`    | Yes*     | Database host (*required when not using `connection_string`) |
| `port`    | No       | Port (default: 5432) |
| `database`| Yes*     | Database name (*required when not using `connection_string`) |
| `username`| No       | Username |
| `password`| No       | Password |
| `driver`  | No       | ODBC driver name (default: `PostgreSQL Unicode` for PostgreSQL) |

## Driver Requirements

### API / Docker Image

The Hub API image includes:

- `unixodbc` — ODBC driver manager
- `unixodbc-dev` — Development headers
- `odbc-postgresql` (psqlodbc) — PostgreSQL ODBC driver

For other databases (MySQL, SQL Server, etc.), install the appropriate driver in your deployment.

### PostgreSQL (psqlodbc)

Driver name is typically one of:

- `PostgreSQL Unicode`
- `PostgreSQL ANSI`
- `PostgreSQL` (depending on installation)

List available drivers:

```bash
odbcinst -q -d
```

### Local Development

For running integration tests or local API with ODBC:

```bash
# Ubuntu/Debian
sudo apt-get install -y unixodbc unixodbc-dev odbc-postgresql

# Verify
odbcinst -q -d
```

## Frontend UI

The virtual dataset create/edit UI provides:

- **Source type dropdown** — Select "ODBC"
- **Connection string** — Single text input for full connection string
- **Host + Database** — Driver, host, port, database, username, password

Toggle between modes via radio buttons. At least one mode must be filled.

## Security

- Credentials in `connection_string`, `password`, and `pwd` are masked in logs and audit events.
- Store secrets in environment variables or a secrets manager; avoid hardcoding in config.

## Troubleshooting

See [RUNBOOKS.md — ODBC Virtualization Issues](RUNBOOKS.md#odbc-virtualization-issues) for common failures and fixes.

## References

- Backend: `hub/apps/virtualization/services.py` — `_execute_odbc_query`
- Business rules: `hub/apps/virtualization/business_rules.py` — ODBC validation
- Integration tests: `hub/apps/virtualization/tests/test_real_source_integration.py` — `test_odbc_execute_against_hub_postgresql`, `test_odbc_execute_connection_string_mode`
