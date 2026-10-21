# Adding a New Warehouse (Phase 275.E.3o — G-PROJ5)

## Against the ABC
1. Implement WarehouseConnector ABC (connect, execute_query, reflect_schema, close)
2. Add WarehouseType entry in models.py
3. Add type mapping in type_mapping.py
4. Create connector in connectors/<name>.py
5. Wire into _resolve_connector() in records_api
6. Add to dlt WriteAdapter destinations
7. Add Prometheus metrics with warehouse_type label
8. Add alert rules
9. Integration tests with sandbox account
