# Athena Warehouse Integration (Phase 275)

## Connection Setup
1. Create WarehouseConnection with warehouse_type=ATHENA
2. Provide credentials via encrypted config (KMS+Fernet)
3. Test connection: connector.connect() → SELECT 1

## Supported Operations
- Live SELECT via parameterised binding
- Schema reflection (INFORMATION_SCHEMA / Glue Catalog)
- Cost attribution per query

## Rate Limits
See `docs/api/search.md` for per-endpoint throttle scopes.
