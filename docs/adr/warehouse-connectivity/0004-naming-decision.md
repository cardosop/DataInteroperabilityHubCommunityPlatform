# ADR-0004: WarehouseConnection naming decision (Phase 275.A.14)

**Status:** Accepted
**Date:** 2026-05-12

## Context

Phase 275 introduces a new model for warehouse connectivity. Two options:
(a) Create a parallel `WarehouseConnection` model with shared encryption base
(b) Extend `MarketplaceConnection` with a `connection_kind` discriminator
(c) Rename `MarketplaceConnection` to clarify scope

## Decision

**Option (a)** — two parallel models with shared base (KMS+Fernet encryption from `hub/apps/integrations/encryption.py`).

## Rationale

- `MarketplaceConnection` stores marketplace-specific state (sync frequency, failure counts, marketplace types)
- `WarehouseConnection` stores warehouse-specific state (region, warehouse_type, private_endpoint_url)
- Different lifecycle semantics (marketplace sync vs live query dispatch)
- Different RBAC model (WarehouseConnectionACL)
- Shared encryption pattern avoids drift without coupling the models

## Consequences

- `WarehouseConnection` in `hub/apps/warehouses/models.py`
- Encryption reused via `hub.apps/integrations.encryption.{encrypt_json_field,decrypt_json_field}`
- No migration impact on existing `MarketplaceConnection` rows
