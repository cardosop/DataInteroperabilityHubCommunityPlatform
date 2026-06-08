# Warehouse Connectivity — Disaster Recovery

**Phase 275.E** — DR procedures for warehouse connectivity.

## 1. Scope
Covers Snowflake, BigQuery, Databricks, and Athena connector recovery.

## 2. RTO/RPO
RTO: 1 hour. RPO: 0 (warehouse-native path doesn't store customer data).

## 3. Failover Procedure
1. Verify credential availability in AWS Secrets Manager secondary region.
2. Update WarehouseConnection config with failover warehouse/region.
3. Re-test connections via API.
4. Verify LIVE_QUERY assets resolve via new warehouse.

## 4. Rollback
Revert config to primary warehouse. Re-test connections.

## 5. Test Schedule
Quarterly DR test via `scripts/smoke_tests_warehouse.sh`.

## 6. Known Limitations
Athena is regional-only (no cross-region failover). Delta Sharing requires re-provisioning.

## 7. Contacts
Platform engineering on-call rotation.
