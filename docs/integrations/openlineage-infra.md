# OpenLineage infrastructure plan

**Phase:** 228 F4 (228.F4.14, F4.15, F4.16)
**Owner:** Data Platform Eng + SRE
**Status:** Documented; deployment is operator-driven (Helm / Terraform)
**Last reviewed:** 2026-04-30

This doc captures the canonical infrastructure shape for the F4
OpenLineage integration: AWS Secrets Manager namespacing,
Marquez Helm chart values, and the mTLS / VPC-internal TLS posture
for Hub ↔ Marquez. The actual provisioning happens via the
existing IaC pipeline (Helm + Terraform); this doc is the spec
the operator follows.

## 228.F4.14 — AWS Secrets Manager

All OpenLineage secrets live under the namespace
`meshant/<env>/openlineage/`. Every secret carries the tag
`cost-center=lineage-feature` (per the Phase 228.0 cost-tagging
policy in [docs/capacity/lineage-cost-12mo.md](../capacity/lineage-cost-12mo.md))
and rotates **every 90 days** via AWS Secrets Manager's automatic
rotation.

| Secret | Purpose | Rotation handler |
|---|---|---|
| `meshant/staging/openlineage/marquez_admin` | Admin key for the Marquez UI / API. Used by ops, not by Hub. | Operator-rotated via Marquez UI; Lambda template in `infrastructure/terraform/secrets/openlineage_marquez_admin.tf`. |
| `meshant/staging/openlineage/hmac_signing_key` | HMAC signing key for the inbound `/events/` endpoint. | Lambda template generates 32-byte URL-safe random; Hub reads via `OPENLINEAGE_HMAC_SIGNING_KEY` env var (settings.py, 228.F4.13). |
| `meshant/staging/openlineage/producer_keys/<tenant_uuid>` | Per-tenant producer ingest key (the plaintext shown ONCE on creation). Customer-success populates this via the admin UI; Secrets Manager just persists the value for ops audit. | Manual via the `rotate_openlineage_keys --tenant=<id>` management command. |
| `meshant/staging/openlineage/mtls_cert` | mTLS cert + private key for Hub ↔ Marquez. | ACM Private CA renewal; 90-day cycle. |

Same shape repeats for `prod` (replace `staging` with `prod`).

The Hub reads each secret via the existing `aws-secrets-helper`
sidecar that mounts `/var/run/secrets/openlineage/*` into the API
pods. Helm value reference:

```yaml
# helm/values-staging.yaml
api:
  secretsMounts:
    - name: openlineage-secrets
      mountPath: /var/run/secrets/openlineage
      secretRef:
        secretsManager: meshant/staging/openlineage
```

The Hub `settings.py` reads the mounted files lazily so a secret
rotation doesn't require a pod restart (the cache TTL is 5 minutes
matching the AWS SDK default).

## 228.F4.15 — Marquez Helm chart

We deploy Marquez via the upstream chart at
`https://marquezproject.github.io/charts`. The chart is **pinned**
to a specific version per `helm/values-staging.yaml` /
`helm/values-prod.yaml`. Quarterly upgrades follow the procedure in
[docs/runbooks/marquez-upgrade.md](../runbooks/marquez-upgrade.md).

### Required values

```yaml
# helm/values-staging.yaml — marquez section
marquez:
  image:
    repository: marquezproject/marquez
    tag: 0.46.0  # PINNED; bump per marquez-upgrade.md
  replicaCount: 2  # 228.F4.15 — replicas≥2 anti-affinity required.
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - { key: app.kubernetes.io/name, operator: In, values: [marquez] }
          topologyKey: kubernetes.io/hostname
  postgres:
    # 228.F4.15 — Multi-AZ Postgres required.
    deploymentStrategy: external  # we provision RDS Multi-AZ via Terraform
    host: marquez-rds-multi-az.example.rds.amazonaws.com
    database: marquez
    user: marquez_app
    passwordSecret: marquez-rds-password  # Secrets Manager-backed
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"
  podDisruptionBudget:
    enabled: true
    minAvailable: 1
  # 228.F4.15 — NetworkPolicy locked: only the hub-api namespace +
  # the marquez itself ingress; no other inbound.
  networkPolicy:
    enabled: true
    ingress:
      - from:
          - namespaceSelector:
              matchLabels:
                kubernetes.io/metadata.name: hub-staging
        ports:
          - port: 5000
            protocol: TCP
```

### RDS provisioning (Terraform)

The Marquez Postgres lives in the same VPC as the Hub RDS but in
a separate database. Multi-AZ for HA. Backups / PITR per the
platform DR baseline.

```hcl
# infrastructure/terraform/marquez/main.tf (sketch)
resource "aws_db_instance" "marquez" {
  identifier            = "meshant-marquez-${var.environment}"
  engine                = "postgres"
  engine_version        = "16.6"
  instance_class        = "db.t4g.medium"  # staging; prod uses db.r6g.large
  multi_az              = true
  storage_encrypted     = true
  backup_retention_period = 30
  deletion_protection   = true
  tags = {
    "cost-center" = "lineage-feature"
    "phase"       = "228-F4"
  }
}
```

## 228.F4.16 — mTLS / VPC-internal TLS Hub ↔ Marquez

Two layers of transport security between Hub and Marquez:

1. **VPC-internal TLS** — both deployments live in the same VPC; the
   `OPENLINEAGE_URL` defaults to the in-cluster service name
   (`marquez.marquez.svc.cluster.local`) so traffic never traverses
   public internet.
2. **mTLS** — service-mesh-managed mutual TLS via the existing Istio
   sidecars. The mesh policy in
   `helm/templates/peerauthentication-marquez.yaml` enforces
   `mtls.mode: STRICT` for the Marquez namespace; non-mTLS traffic
   is dropped.

The cert lifecycle is handled by ACM Private CA (90-day
rotation, see 228.F4.14). The mesh's automatic cert reload picks
up rotation without a pod restart.

### Verification

After deployment, an operator confirms mTLS is enforced:

```bash
# From a sidecar-less pod (should FAIL):
kubectl run debug --rm -it --image=curlimages/curl --restart=Never -- \
    curl -sS http://marquez.marquez.svc.cluster.local:5000/api/v1/namespaces

# Expected: connection reset / 503. The sidecar-less pod has no
# mesh identity, so the Marquez sidecar rejects the request.
```

```bash
# From a sidecar-meshed pod (should SUCCEED):
kubectl exec -n hub-staging deploy/api -- \
    curl -sS http://marquez.marquez.svc.cluster.local:5000/api/v1/namespaces

# Expected: 200 + JSON body. The mesh-meshed pod presents an
# mTLS client cert that Marquez accepts.
```

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Marquez RDS becomes a single failure domain. | Multi-AZ + 30-day PITR + quarterly DR drill (`destroy-staging.md`). |
| HMAC key rotation breaks producers in flight. | The Hub's `_verify_hmac` reads the live setting on every request; rotation propagates within the SDK's 5-minute cache TTL. Producers must re-fetch the secret before signing if their rotation window aligns with the Hub's. Documented in `openlineage.md`. |
| Marquez schema migrations during release require downtime. | Quarterly upgrade window per `marquez-upgrade.md`; pre-migration RDS snapshot for rollback. |
| Operator accidentally points `OPENLINEAGE_URL` at a non-Meshant Marquez instance. | The default value targets the in-cluster service name; production override is gated by Helm chart review + a settings-pin config-map. |

## Related

- [REQ-LIN-F4 spec](../../openspec/changes/preprod01/specs/lineage-foundations/spec.md)
- [Cost forecast](../capacity/lineage-cost-12mo.md) — tagging policy
- [Marquez outage runbook](../runbooks/marquez-outage.md)
- [Quarterly upgrade procedure](../runbooks/marquez-upgrade.md)
