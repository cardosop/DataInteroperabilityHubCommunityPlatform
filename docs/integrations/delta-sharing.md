# Delta Sharing Integration (Phase 275.D.3)

## Endpoint
GET /api/v1/datasets/{id}/share/

## Protocol
Delta Sharing 1.0 protocol served with Hub auth + audit injection.

## Rate Limit
warehouse-query-share: 30 req/min/tenant

## Audit
WAREHOUSE_SHARE_ACCESSED emitted per access.

## Opt-Out
Reuses Phase 230.8.9 Dataset.semantic_federate_optout pattern.
Assets with opt-out flag return 403 from the share endpoint.
