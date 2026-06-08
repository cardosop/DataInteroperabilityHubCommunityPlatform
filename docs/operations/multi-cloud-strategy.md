# Multi-Cloud Strategy — Meshant Platform

**Last updated:** 2026-05-15

## B.3.1 — PoC Deployment to GCP/Azure

**Status:** ⏭️ Not deployed. Plan documented.

### Target: GCP (Google Cloud Platform)
- **Reasoning:** Strong K8s (GKE), managed Postgres (Cloud SQL), managed Redis (Memorystore), S3-compatible (GCS)
- **Services mapping:** EKS→GKE, RDS→Cloud SQL, ElastiCache→Memorystore, S3→GCS, SES→SendGrid

### Staging PoC Deployment
```bash
# 1. Create GKE cluster
gcloud container clusters create meshant-poc --zone europe-west1-b --num-nodes 3

# 2. Deploy Helm chart
helm upgrade --install meshant ./helm \
  -f helm/values.yaml \
  -f helm/values.gcp-poc.yaml \
  --namespace hub-poc

# 3. Verify health
kubectl get pods -n hub-poc
curl https://meshant-internal.example.com/api/v1/health/
```

## B.3.2 — Cloud Service Abstractions

**Status:** ✅ PARTIALLY ABSTRACTED (verified 2026-05-15).

### Existing Abstractions
| AWS Service | Current Abstraction | Status |
|---|---|---|
| S3 | `django-storages` + MinIO (staging) | ✅ 11 MinIO refs in docker-compose.staging.yml |
| SES | Django email backend (`EMAIL_BACKEND`) | ✅ Config-based, switchable |
| ElastiCache | Redis URL (`REDIS_URL` env var) | ✅ Transport-agnostic — any Redis works |
| ECR | Docker registry URL | ✅ Any OCI-compatible registry works |
| Secrets Manager | ExternalSecrets + `aws_secrets_loader.py` | ⚠️ AWS-specific loader. Needs Vault/GSM adapter |

### Remaining Abstractions Needed
| AWS Service | GCP Equivalent | Abstraction Strategy |
|---|---|---|
| IAM/IRSA | GCP Workload Identity | Abstract via OIDC provider |
| Route 53 | Cloud DNS | Abstract via external-dns |
| CloudWatch | Cloud Monitoring | Abstract via OTEL collector |
| SQS | Pub/Sub | Abstract via Celery broker URL |
| ACM | Certificate Manager | Abstract via cert-manager |

### MinIO Interface (Already Working)
```python
# hub/settings.py — S3 storage backend (S3 or MinIO)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL')  # MinIO or S3
```

## B.3.3 — AWS→GCP Migration Runbook

**Target:** 30-day migration window

### Week 1: Infrastructure Provisioning
- [ ] Day 1-2: Provision GKE cluster + Cloud SQL + Memorystore + GCS buckets
- [ ] Day 3-4: Deploy Helm chart to GKE, verify all pods healthy
- [ ] Day 5: Configure DNS (Cloud DNS), TLS (cert-manager), ingress

### Week 2: Data Migration
- [ ] Day 6-8: PostgreSQL dump/restore → Cloud SQL (pg_dump | psql)
- [ ] Day 9-10: Redis data migration (RDB snapshot → Memorystore)
- [ ] Day 11-12: S3→GCS data sync (aws s3 sync → gsutil rsync)

### Week 3: Service Cutover
- [ ] Day 13-15: Smoke test all services on GCP
- [ ] Day 16-18: Canary: 10% traffic → GCP via weighted DNS
- [ ] Day 19-20: Full cutover: 100% traffic → GCP

### Week 4: Validation + Cleanup
- [ ] Day 21-25: Monitor GCP for 5 days, verify no regressions
- [ ] Day 26-28: AWS resource decommissioning (stop RDS, delete EKS, release EIPs)
- [ ] Day 29-30: Final audit, update runbooks, close migration ticket

### Cost Comparison (Monthly Estimate)
| Resource | AWS (us-east-1) | GCP (europe-west1) | Delta |
|---|---|---|---|
| K8s (3 nodes) | $220 (EKS) | $220 (GKE — free control plane) | -$73 |
| Postgres (db.r6g.large) | $250 | $230 (Cloud SQL) | -$20 |
| Redis (cache.r6g.large) | $180 | $170 (Memorystore) | -$10 |
| S3/GCS (1 TB) | $23 | $20 | -$3 |
| **Total** | **$673** | **$640** | **-$106 (-16%)** |

## B.3.4 — Multi-Cloud IaC Evaluation

**Status:** Terraform (current). Crossplane + Pulumi evaluated.

### Current: Terraform (HashiCorp)
- **Pros:** Mature, large provider ecosystem, existing investment (7 modules)
- **Cons:** Provider-specific HCL, drift detection limited, state management burden

### Evaluation: Crossplane
- **Pros:** K8s-native, continuous reconciliation, multi-cloud CRDs
- **Cons:** Requires K8s cluster to run, steeper learning curve, smaller community

### Evaluation: Pulumi
- **Pros:** General-purpose languages (Python/TS), multi-cloud in single codebase
- **Cons:** State management similar to Terraform, less mature GCP/Azure providers

### Recommendation
Stay with Terraform for 12 months. Evaluate Crossplane after:
- GCP PoC deployed (B.3.1)
- Cloud abstractions completed (B.3.2)
- Migration runbook tested (B.3.3)

Crossplane becomes viable when multi-cloud is a production requirement, not just a PoC.
