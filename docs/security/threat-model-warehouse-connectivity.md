# Threat Model: Warehouse Connectivity (Phase 275.A.9)

Status: STUB — framework complete; connector-level threat review needed per warehouse.

## Credential Handling
- KMS+Fernet encryption at rest (reused from `hub/apps/integrations/encryption.py`)
- Per-tenant credential vault in `WarehouseConnection.config`
- Key policy: only Hub api-service + worker pods can decrypt

## Network Egress
- SSRF guard at config-save time (reuses SPARQL federation validator pattern)
- NetworkPolicy allow-list (Helm `allow-warehouse-egress.yaml`)
- PrivateLink/PSC support via `private_endpoint_url` field

## Query Forwarding
- Parameterised binding only — never string concatenation
- CI check: no `f"... {user_input} ..."` in connector source
- Query-timeout cascade: client > Hub > driver > warehouse

## SQL Injection
- All user-supplied filter values go through driver parameter-binding API
- Tenant-supplied filter `'; DROP TABLE; --` handled by driver

## Multi-Tenancy Isolation
- RLS on `warehouse_connections` + `warehouse_connection_acls`
- Per-tenant connection pool with semaphore
- Tenant A cannot use Tenant B's `connection_id`

## Share-Endpoint Auth
- Delta Sharing protocol with Hub auth + audit injection
- Opt-out filter per asset (reuses Phase 230.8.9 pattern)

## Legal Sign-Off
- [ ] Required pre-flag-flip-to-True for any production tenant
