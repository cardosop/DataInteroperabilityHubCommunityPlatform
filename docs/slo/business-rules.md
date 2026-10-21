# Business Rules SLOs — Phase 274

| Chain | p95 Latency | Success Rate | Window |
|---|---|---|---|
| `contract.publish` | < 200ms | > 99.5% | 28 days |
| `asset.activate` | < 500ms | > 99.0% | 28 days |
| `marketplace.listing.publish` | < 200ms | > 99.5% | 28 days |
| `governance.approval.advance` | < 300ms | > 99.5% | 28 days |
| `semantic.query.execute` | < 100ms | > 99.9% | 28 days |
| Chain runner overhead | p95 < 50ms | — | per execution |

Metrics sourced from `business_rules_chain_completed` audit events and `rule_chain.*` OTel spans.
