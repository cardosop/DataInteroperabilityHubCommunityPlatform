# Multi-Region Active-Active DR Plan — Meshant Platform

**Last updated:** 2026-05-15 | **Target:** Month 6-9

## B.1.1 — Secondary Region Deployment

**Status:** ⏭️ Requires AWS production access. Terraform modules ready for replication.

### Target Region: eu-west-1 (Ireland)
- GDPR compliance (EU data residency option)
- <90ms latency from us-east-1 (acceptable for async replication)
- All AWS services available (RDS, ElastiCache, EKS, S3, Route 53)

### Deployment Commands
```bash
# 1. Apply Terraform to secondary region
cd infrastructure/terraform/environments/eu-west-1
terraform init
terraform plan -var-file=production.tfvars
terraform apply -var-file=production.tfvars

# 2. Deploy Helm chart to secondary EKS cluster
aws eks update-kubeconfig --region eu-west-1 --name meshant-eu
helm upgrade --install meshant ./helm \
  -f helm/values.yaml \
  -f helm/values.eu-west-1.yaml \
  --namespace hub-production

# 3. Verify all services healthy
kubectl get pods -n hub-production --context meshant-eu
```

## B.1.2 — Cross-Region Data Replication

### PostgreSQL Logical Replication
```sql
-- On primary (us-east-1):
CREATE PUBLICATION meshant_pub FOR ALL TABLES;

-- On replica (eu-west-1):
CREATE SUBSCRIPTION meshant_sub
  CONNECTION 'host=primary.us-east-1.rds.amazonaws.com dbname=hub'
  PUBLICATION meshant_pub;
```

### Redis Active-Passive with DNS Failover
```hcl
# Route 53 failover records
resource "aws_route53_record" "redis_cache" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "meshant-internal.example.com"
  type    = "CNAME"
  ttl     = 60
  records = [aws_elasticache_replication_group.cache.primary_endpoint_address]

  failover_routing_policy {
    type = "PRIMARY"
  }
}

resource "aws_route53_record" "redis_cache_secondary" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "meshant-internal.example.com"
  type    = "CNAME"
  ttl     = 60
  records = [aws_elasticache_replication_group.cache_eu.primary_endpoint_address]

  failover_routing_policy {
    type = "SECONDARY"
  }
  set_identifier = "eu-west-1"
  health_check_id = aws_route53_health_check.redis_eu.id
}
```

### S3 Cross-Region Replication
```hcl
resource "aws_s3_bucket_replication_configuration" "meshant_crr" {
  role   = aws_iam_role.s3_crr.arn
  bucket = aws_s3_bucket.primary.id

  rule {
    id     = "crr-to-eu-west-1"
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.secondary.arn
      storage_class = "STANDARD"
    }
  }
}
```

## B.1.3 — Route 53 Health-Check Failover

### Health Check Configuration
```hcl
resource "aws_route53_health_check" "api_primary" {
  fqdn              = "meshant-internal.example.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/v1/health/"
  failure_threshold = 3
  request_interval  = 30
}

resource "aws_route53_health_check" "api_secondary" {
  fqdn              = "meshant-internal.example.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/v1/health/"
  failure_threshold = 3
  request_interval  = 30
}
```

### Failover Timing
| Component | Detection | Failover | Total RTO |
|---|---|---|---|
| Route 53 health check | 30s interval × 3 failures | Instant (DNS) | <2 min |
| DNS propagation (TTL 60s) | — | — | <1 min |
| Application warm-up | — | — | <2 min |
| **Total** | | | **<5 min** |

## B.1.4 — Cross-Region Replication Lag

### Measurement
```bash
# PostgreSQL logical replication lag
psql -h primary... -c "SELECT slot_name, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes FROM pg_replication_slots;"

# S3 CRR lag
aws s3api head-object --bucket meshant-eu --key replication-lag-marker.txt \
  --query 'LastModified' --region eu-west-1
```

### RPO Targets
| Data Store | Replication Method | Expected Lag | RPO |
|---|---|---|---|
| PostgreSQL | Logical replication (pgoutput) | <100ms typical | <1 min |
| Redis | Active-passive DNS failover | N/A (no data replication) | Last backup (5 min) |
| S3 | CRR (async) | <15 min (S3 SLA) | <15 min |

## B.1.5 — Quarterly DR Drill

### Drill Schedule
- **Q3 2026** (Month 6): First drill — simulated us-east-1 outage
- **Q4 2026** (Month 9): Second drill — full failover + failback
- **Q1 2027** (Month 12): Third drill — unannounced (game day)

### Drill Procedure
```bash
# 1. Announce drill (48h notice to stakeholders)
# 2. Simulate outage: block us-east-1 at network level
kubectl apply -f chaos-mesh/network-partition-us-east-1.yaml

# 3. Verify Route 53 failover triggered
dig meshant-internal.example.com  # Should resolve to eu-west-1 IP

# 4. Verify all services healthy in eu-west-1
kubectl get pods -n hub-production --context meshant-eu

# 5. Run smoke tests against eu-west-1
E2E_BASE_URL=https://meshant-internal.example.com npx playwright test --project=production-smoke

# 6. Measure RTO (target: <5 min) and RPO (target: <1 min)

# 7. Failback to us-east-1
teraform apply  # Re-enable us-east-1 resources
kubectl apply -f chaos-mesh/restore-us-east-1.yaml

# 8. Document results in docs/operations/dr-drill-reports/
```
