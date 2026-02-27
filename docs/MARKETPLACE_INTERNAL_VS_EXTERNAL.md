# Internal vs External Marketplace

This document clearly separates the **internal marketplace** (Hub’s own catalog, orders, entitlements) from the **external marketplace** (integrations with third‑party data marketplaces). Each has a different URL prefix and purpose.

---

## Summary

| Aspect | Internal marketplace | External marketplace |
|--------|----------------------|----------------------|
| **Purpose** | Hub’s data product catalog, ordering, and entitlements | Connect to external marketplaces; sync and map listings |
| **Base URL** | `/api/v1/marketplace/` | `/api/v1/integrations/marketplace/` |
| **App** | `hub.apps.marketplace` | `hub.apps.integrations` (marketplace routes) |

---

## Internal marketplace — `/api/v1/marketplace/`

The **internal marketplace** is the Hub’s own marketplace: data product **listings**, **orders**, **entitlements**, **preview**, and related configuration. All of these live under `/api/v1/marketplace/`.

### Main resources

- **Listings** — Data product listings in the Hub catalog  
  - `GET/POST /api/v1/marketplace/listings/`  
  - `GET/PUT/PATCH/DELETE /api/v1/marketplace/listings/{id}/`  
  - `GET /api/v1/marketplace/listings/{id}/preview/` — time-limited preview  
  - `GET /api/v1/marketplace/listings/{id}/download/` — contract/download  

- **Orders** — Consumer orders for listings  
  - `GET/POST /api/v1/marketplace/orders/`  
  - `GET/PUT/PATCH /api/v1/marketplace/orders/{id}/`  
  - `POST /api/v1/marketplace/orders/{id}/approve/`  
  - `POST /api/v1/marketplace/orders/{id}/reject/`  

- **Entitlements** — Granted access after order approval  
  - `GET /api/v1/marketplace/entitlements/`  
  - `GET /api/v1/marketplace/entitlements/{id}/`  

- **Configuration**  
  - Trust signals: `GET/POST/PUT/PATCH/DELETE /api/v1/marketplace/config/trust-signals/`  
  - Payment gateways: `/api/v1/marketplace/payment-gateways/`  

### When to use

Use internal marketplace APIs when you work with the Hub’s **own** catalog: publishing listings, placing or approving orders, checking entitlements, or getting preview/download URLs.

---

## External marketplace — `/api/v1/integrations/marketplace/`

The **external marketplace** APIs manage **connections** to third‑party data marketplaces (e.g. Snowflake, AWS Data Exchange, Databricks), **sync jobs** (PULL/PUSH), and **mappings** between Hub assets and external listings. All of these live under `/api/v1/integrations/marketplace/`.

### Main resources

- **Connections** — Configure and test connections to external marketplaces  
  - `GET/POST /api/v1/integrations/marketplace/connections/`  
  - `GET/PUT/PATCH/DELETE /api/v1/integrations/marketplace/connections/{id}/`  
  - `POST /api/v1/integrations/marketplace/connections/{id}/test/`  

- **Sync jobs** — Run and monitor PULL/PUSH sync  
  - `GET/POST /api/v1/integrations/marketplace/sync/`  
  - `GET /api/v1/integrations/marketplace/sync/{id}/`  
  - `POST /api/v1/integrations/marketplace/sync/{id}/cancel/`  

- **Mappings** — Hub asset ↔ external listing mapping  
  - `GET /api/v1/integrations/marketplace/mappings/`  
  - `GET/DELETE /api/v1/integrations/marketplace/mappings/{id}/`  

- **Connector metadata**  
  - `GET /api/v1/integrations/marketplace/connectors/`  
  - `GET /api/v1/integrations/marketplace/connectors/{connector_type}/`  

### When to use

Use external marketplace APIs when you **integrate with external marketplaces**: creating connections, running sync jobs, or inspecting mappings. See [Marketplace API Reference](MARKETPLACE_API_REFERENCE.md) for the full external API reference.

---

## Quick reference: URL prefixes

- **Internal (Hub catalog, orders, entitlements, preview):**  
  `/api/v1/marketplace/`

- **External (connections, sync, mappings):**  
  `/api/v1/integrations/marketplace/`

Do not confuse the two: e.g. `/api/v1/marketplace/connections/` does **not** exist; connections are under `/api/v1/integrations/marketplace/connections/`.

---

## Related documentation

- [Marketplace API Reference](MARKETPLACE_API_REFERENCE.md) — Full reference for **external** marketplace APIs (connections, sync, mappings).
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) — Architecture and concepts.
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) — Use cases and flows.
- [Docs README](README.md) — Documentation index.
