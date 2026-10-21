# Warehouse Connectivity Quickstart (Phase 275.E.3o)

## Snowflake Setup → Register Asset → Query Rows → Schedule Export

1. Create a Snowflake WarehouseConnection with account/user/password
2. Register an Asset with data_strategy=LIVE_QUERY
3. Query rows: GET /api/v1/datasets/{id}/rows/?limit=100
4. Schedule export: POST /api/v1/scheduled-exports/ with destination_type=SNOWFLAKE_TABLE

## Adding a 5th Warehouse (Phase 276)

See docs/integrations/warehouses/adding-a-new-warehouse.md
