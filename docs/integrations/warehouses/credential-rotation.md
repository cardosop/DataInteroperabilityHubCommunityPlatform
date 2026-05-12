# Warehouse Credential Rotation (Phase 275.E.3i)

## Tenant Rotation
1. Generate new credential (PAT/JWT/keypair) in warehouse console
2. Update WarehouseConnection.config via API (overlapping-creds window)
3. Verify: connection test returns SELECT 1
4. Revoke old credential in warehouse console

## Hub Admin — Compromised Credential
1. Set WarehouseConnection.is_active=False (instant deactivation)
2. Rotate credential in ExternalSecrets
3. Audit: search AuditEvent for WAREHOUSE_CONNECTION_UPDATED
4. Notify tenant admin
