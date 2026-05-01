# ADR-LIN-009 — Phase 0 IaC pattern audit

**Status:** Accepted (Phase 228 Foundations — audit document, 228.0.6)
**Date:** 2026-04-30
**Related:** ADR-LIN-008 (async-workers); 228.0.5 cost-tagging policy

## Audit summary

Phase 228 introduces new worker manifests (the change-notification dispatcher and the OpenLineage adapter, per ADR-LIN-008). The audit confirms **the existing IaC pattern is Helm + Terraform** and Phase 228 manifests SHALL be added under the existing structure rather than introducing a new pattern.

## What exists

### Helm

[`helm/Chart.yaml`](../../../helm/Chart.yaml) defines a single umbrella chart `meshant` covering all backend services. Sub-templates under [`helm/templates/`](../../../helm/templates/) define `Deployment`, `Service`, `Ingress`, and `HorizontalPodAutoscaler` per service. Per-environment values live at:

- [`helm/values-staging.yaml`](../../../helm/values-staging.yaml)
- [`helm/values-prod.yaml`](../../../helm/values-prod.yaml)
- [`helm/values-dev.yaml`](../../../helm/values-dev.yaml)

### Terraform

[`infrastructure/terraform/`](../../../infrastructure/terraform/) contains:

- `bootstrap/` — IAM roles + S3 backend setup.
- `s3/` — S3 buckets (per-tenant + cost-center tagging).
- `environments/staging/` and `environments/prod/` — top-level env wiring.

Existing convention: every new AWS resource in Terraform takes a `tags` map that includes at minimum `cost-center=<feature>` (per FinOps doctrine — see `docs/capacity/lineage-cost-12mo.md`).

### Kubernetes raw manifests (legacy)

[`k8s/`](../../../k8s/) contains raw `*.yaml` manifests for cluster-scoped resources (PriorityClass, NetworkPolicy, namespaces). New service deployments do NOT land here; they go through Helm.

## Where Phase 228 worker manifests will land

| New manifest | Path | Reason |
|---|---|---|
| Lineage change-notification dispatcher (Phase 228 F3) | New Deployment in [`helm/templates/`](../../../helm/templates/) named `lineage-notification-dispatcher.yaml`; values block in `values-{env}.yaml` under `lineageNotificationDispatcher:` | Follows existing per-service template convention; lets ops scale replicas via Helm value, not by editing raw YAML. |
| OpenLineage adapter worker (Phase 228 F4) | New Deployment `helm/templates/openlineage-adapter.yaml` + values block `openlineageAdapter:` | Same pattern. |
| OpenLineage receiver Service + Ingress (if subscribers POST to us — they don't in v1) | N/A v1 | The adapter is purely outbound (we POST to subscribers); no new ingress. Out of scope. |

Resource tagging: both new manifests carry `tags: cost-center=lineage-feature` in the Deployment annotations + the `topologySpreadConstraints` to spread across AZ per the existing pattern in `helm/templates/api-deployment.yaml`.

## What Phase 228 does NOT add

- **No new Helm chart** — the umbrella `meshant` chart absorbs the new templates.
- **No new Terraform module** — the new RDS table is created by a Django migration (no Terraform), the new metrics are created by Prometheus auto-discovery (no Terraform), the new SES sender is reused (no Terraform).
- **No new IAM roles** — the new workers reuse the existing `meshant-worker` service-account / IAM role.
- **No new VPC peering, no new security groups** — all calls are via the existing service mesh.

## Risks identified during audit

- **Risk:** the umbrella chart is becoming large (~30 templates). **Mitigation:** out of scope for Phase 228; flagged for SRE retrospective if templates exceed 50.
- **Risk:** Terraform state divergence between `staging/` and `prod/`. **Mitigation:** unchanged — Phase 228 adds no Terraform-managed resources, so the divergence risk does not increase.

## Conclusion

The Helm + Terraform pattern is sufficient for Phase 228. Two new Helm Deployment templates land under `helm/templates/`; values per environment land under `values-{env}.yaml`. No new Terraform, no new IaC primitive.
