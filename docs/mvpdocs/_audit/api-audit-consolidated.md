# API Audit Consolidation

> Consolidated from `docs/api-audit/` — Phase 217.0.3.
> Original files archived to `archive/api-audit-2025/` via `git mv`.

## Overview

The `docs/api-audit/` directory contained a service-client audit
(generated 2026-03-24) documenting all service-to-service HTTP
interactions in the DataInteroperabilityHub system.  The original
2026-01-26 documentation audit cataloged 97 files under `api-audit/`;
most were cleaned up in earlier phases, leaving only the JSON audit
below.

## Service-Client Audit Summary

**Source**: `service-client-audit.json` (2026-03-24)

| Metric | Value |
|--------|-------|
| Service clients audited | 5 |
| Total methods | 27 |
| Service-to-service HTTP calls | 19 |

### Audited Service Clients

| Client Class | Target Service | Key Endpoints |
|-------------|----------------|---------------|
| `WebhookDeliveryClient` | webhook-delivery | Event dispatch, retry |
| `ComplianceServiceClient` | compliance | Compliance checks, reports |
| `DQServiceClient` | d-q | Data quality rule execution |
| `SemanticServiceClient` | semantic | SPARQL/RDF operations |
| `DataContractCLIClient` | data-contract-c-l-i | Contract validation |

### Key Findings

1. **5 internal service clients** handle all inter-service communication
2. **19 documented HTTP calls** map the service dependency graph
3. All clients follow the same pattern: class-based, with typed
   parameters and return values
4. No authentication between internal services was documented in the
   audit (relies on network-level isolation within the K8s cluster)

## Disposition

- The original `service-client-audit.json` is preserved in
  `archive/api-audit-2025/` for historical reference
- The service dependency information is superseded by the live OpenAPI
  schema and the `mkdocs-swagger-ui-tag` auto-generated reference
  (Phase 217.2)
- No action items remain from this audit for MVP launch
