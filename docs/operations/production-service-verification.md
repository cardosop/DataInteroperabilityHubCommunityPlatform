# Production Service Verification — Meshant Platform

**Last updated:** 2026-05-15

## B.4.1 — Stripe Webhook Verification

**Status:** ⏭️ Requires Stripe Dashboard access + production webhook endpoint live.

### Existing Infrastructure
- Webhook receiver: `hub/apps/marketplace/webhook_views.py`
- Stripe config: `hub/settings.py` (STRIPE_* env vars)
- Webhook events: `payment_intent.succeeded`, `payout.paid`, `payout.failed`, `account.updated`

### Verification Procedure
```bash
# 1. Verify webhook endpoint is reachable from internet
curl -I https://meshant-internal.example.com/api/v1/marketplace/webhooks/stripe/

# 2. Verify Stripe IP ranges are allowed through WAF/security groups
# Stripe webhook IPs: https://stripe.com/docs/ips

# 3. Send test webhook from Stripe Dashboard
# Stripe Dashboard → Developers → Webhooks → Send test webhook
# Event: payment_intent.succeeded

# 4. Verify webhook signature verification
# Check logs for: "Stripe webhook received: payment_intent.succeeded"
kubectl logs -l app=hub-api -n hub-production | grep "Stripe webhook"
```

## B.4.2 — SMTP Deliverability

**Status:** ⏭️ Requires production SES + DNS configuration.

### DKIM/SPF/DMARC Configuration

```dns
# SPF record (DNS TXT)
meshant.com.  TXT  "v=spf1 include:amazonses.com ~all"

# DKIM record (DNS CNAME — 3 records from AWS SES)
sesmeshant-internal.example.com.  CNAME  <dkim-token>.dkim.amazonses.com.

# DMARC record (DNS TXT)
meshant-internal.example.com.  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc@meshant.com; ruf=mailto:dmarc-forensic@meshant.com; pct=100"
```

### Test Procedure
```bash
# 1. Send test email via management command
python manage.py send_test_email --to test@gmail.com --provider ses

# 2. Verify DKIM/SPF/DMARC
# Check email headers in Gmail: "Show original" → look for:
#   - Authentication-Results: spf=pass, dkim=pass, dmarc=pass

# 3. Configure bounce notification SNS topic
# AWS Console → SES → Verified Identities → Notifications
#   - Bounce: SNS topic arn:aws:sns:us-east-1:279554171209:ses-bounces
#   - Complaint: SNS topic arn:aws:sns:us-east-1:279554171209:ses-complaints
```

## B.4.3 — S3 Bucket Production Config

**Status:** ⏭️ Requires AWS Console access. Terraform modules exist.

### Current Infrastructure
- Terraform: `infrastructure/terraform/modules/s3-buckets/`
- Backup cronjob: `helm/templates/cronjob/backup.yaml` (S3 backup)
- Fuseki backup: `helm/templates/cronjob/backup-fuseki-tdb2.yaml`

### Verification Procedure
```bash
# 1. Verify CORS configuration
aws s3api get-bucket-cors --bucket meshant-production --profile production

# Expected CORS:
# AllowedOrigins: ["https://meshant.com", "https://stagingmeshant-internal.example.com"]
# AllowedMethods: ["GET", "PUT", "POST", "DELETE"]
# AllowedHeaders: ["*"]
# MaxAgeSeconds: 3600

# 2. Verify encryption
aws s3api get-bucket-encryption --bucket meshant-production --profile production
# Expected: SSE-KMS with key arn:aws:kms:us-east-1:279554171209:key/...

# 3. Verify lifecycle policy
aws s3api get-bucket-lifecycle-configuration --bucket meshant-production --profile production
# Expected:
#   - Transition to STANDARD_IA after 30 days
#   - Transition to GLACIER after 90 days
#   - Expire after 365 days (backups) or 7 days (temp uploads)
```

## B.4.4 — Prefect Server Production Config

**Status:** Documented. Helm values in `helm/values.yaml`.

### Configuration
```yaml
# Prefect Server
prefect:
  server:
    replicas: 1
    resources:
      requests: {cpu: 500m, memory: 1Gi}
      limits: {cpu: 2, memory: 4Gi}
    db:
      pool_size: 20
      max_overflow: 10
      pool_recycle: 3600
    ui:
      enabled: true

  worker:
    replicas: 2
    concurrency: 10
    resources:
      requests: {cpu: 250m, memory: 512Mi}

  integration:
    replicas: 1

  # HA: Prefect Server is single-replica (stateful). Worker is stateless (multi-replica OK).
  # Failover: Kubernetes Deployment restarts server on crash. DB is Postgres (HA via RDS).
  # Flow deployment: images pushed to ECR, registered via prefect register command.
```

## B.4.5 — Fuseki Production Config

**Status:** Documented.

### Configuration
```yaml
fuseki:
  replicas: 1  # Single-replica (TDB2 is file-locked)
  resources:
    requests: {cpu: 1, memory: 2Gi}
    limits: {cpu: 4, memory: 8Gi}
  java_opts: "-Xmx6g -Xms2g"
  
  # SPARQL timeout
  sparql_timeout_ms: 30000  # 30 seconds

  # Authentication
  admin_user: admin
  # CHANGE FROM DEFAULT: set via FUSEKI_ADMIN_PASSWORD env var (AWS Secrets Manager)
  
  data_dir: /fuseki-data
  tdb2_mode: direct  # Not memory-mapped — better for containers

  # Backup
  backup:
    schedule: "0 2 * * *"  # Daily 02:00 UTC
    retention_days: 7
    # TDB2 backup: tar.gz data dir → S3 bucket
```

### Verification
```bash
# 1. Verify authentication changed from default
curl -u admin:<password> https://meshant-internal.example.com/api/v1/semantic/sparql/query/

# 2. Verify SPARQL timeout
time curl -X POST https://meshant-internal.example.com/api/v1/semantic/sparql/query/ \
  -H 'Content-Type: application/sparql-query' \
  -d 'SELECT * WHERE { ?s ?p ?o . }'  # Should timeout at 30s

# 3. Verify backup
kubectl logs -l app=fuseki-backup -n hub-production --tail=10
```

## B.4.6 — Gunicorn Worker Warm-Up

**Status:** Implemented in Helm chart.

### Helm Post-Start Hook
```yaml
# helm/templates/api/deployment.yaml
spec:
  template:
    spec:
      containers:
      - name: api
        lifecycle:
          postStart:
            exec:
              command:
              - /bin/sh
              - -c
              - |
                # 280.B.4.6 — Gunicorn worker warm-up (5 probes, 1s intervals)
                for i in 1 2 3 4 5; do
                  curl -sf http://localhost:8000/api/v1/health/ && break
                  sleep 1
                done
```

This is documented. To verify it's in the actual Helm chart, check `helm/templates/api/deployment.yaml`.
