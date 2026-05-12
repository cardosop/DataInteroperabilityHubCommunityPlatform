# Migrating Files to Live Query (Phase 275.E.3h)

Per-warehouse setup → register asset → flip data-strategy → validate flow.

1. Create a WarehouseConnection with credentials
2. Register an Asset with data_strategy=LIVE_QUERY + warehouse_connection FK
3. Validate: records API returns data from live warehouse
4. Monitor: warehouse_query metrics populate in Grafana
