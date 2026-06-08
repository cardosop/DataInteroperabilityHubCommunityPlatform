# Operations Test Procedures — Drill Runbooks

**Date:** 2026-05-22
**Phase:** 312.18.5 — OpenSpec Integration
**Status:** Active

---

## 1. Backup/Restore Drill

### Purpose
Verify PostgreSQL backups can be restored to a point-in-time state.

### Prerequisites
- `scripts/backup-postgres.sh` available
- AWS S3 bucket accessible (`BACKUP_S3_BUCKET` env var set)
- Target PostgreSQL instance reachable
- `pg_restore` binary matching PostgreSQL version (16)

### Step-by-Step

```bash
# 1. Create a test table with known data
docker compose exec postgres-test psql -U hub_test -d hub_test -c "
  CREATE TABLE IF NOT EXISTS drill_backup_test (id SERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT NOW());
  INSERT INTO drill_backup_test DEFAULT VALUES;
  SELECT * FROM drill_backup_test ORDER BY id DESC LIMIT 1;
"

# 2. Run the backup script
export BACKUP_S3_BUCKET="meshant-backup-drill"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5434"
export POSTGRES_USER="hub_test"
export PGPASSWORD="hub_test"
bash scripts/backup-postgres.sh

# 3. Verify backup exists in S3
aws s3 ls "s3://${BACKUP_S3_BUCKET}/" --recursive | tail -5

# 4. Drop the test table (simulate data loss)
docker compose exec postgres-test psql -U hub_test -d hub_test -c "DROP TABLE drill_backup_test;"

# 5. Restore from backup
BACKUP_FILE=$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/" --recursive | sort | tail -1 | awk '{print $4}')
aws s3 cp "s3://${BACKUP_S3_BUCKET}/${BACKUP_FILE}" /tmp/restore-test.sql.gz
gunzip /tmp/restore-test.sql.gz
docker compose exec -T postgres-test psql -U hub_test -d hub_test < /tmp/restore-test.sql

# 6. Verify data restored
docker compose exec postgres-test psql -U hub_test -d hub_test -c "SELECT * FROM drill_backup_test;"
```

### Expected Output
- Backup creates `.sql.gz` file + SHA-256 manifest
- S3 upload confirms size match
- After restore, the `drill_backup_test` table exists with the inserted row

### Failure Scenarios
- **S3 access denied:** Check IAM role / AWS credentials
- **pg_dump version mismatch:** Ensure backup script's PostgreSQL client matches server version
- **Insufficient disk space:** Verify `/tmp` has enough space for uncompressed backup

---

## 2. Secrets Rotation Drill

### Purpose
Verify AWS Secrets Manager secrets can be rotated without service disruption.

### Prerequisites
- AWS Secrets Manager configured (`AWS_SECRETS_ENABLED=true`)
- AWS CLI with `secretsmanager` permissions
- Target secrets identified (SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY, REDIS passwords)

### Step-by-Step

```bash
# 1. Record current secret versions
SECRET_ID="meshant/staging/hub"
aws secretsmanager describe-secret --secret-id "$SECRET_ID" --query 'VersionIdsToStages'

# 2. Generate new secret values
NEW_SECRET_KEY=$(openssl rand -hex 32)
NEW_JWT_KEY=$(openssl rand -hex 32)
NEW_ENCRYPTION_KEY=$(openssl rand -hex 32)

# 3. Update secret with new version
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_ID" \
  --secret-string "{\"SECRET_KEY\":\"$NEW_SECRET_KEY\",\"JWT_SECRET_KEY\":\"$NEW_JWT_KEY\",\"ENCRYPTION_KEY\":\"$NEW_ENCRYPTION_KEY\"}"

# 4. Verify new version exists
aws secretsmanager describe-secret --secret-id "$SECRET_ID" --query 'VersionIdsToStages'

# 5. Rolling restart: restart pods to pick up new secrets
kubectl rollout restart deployment/api-service -n hub-staging
kubectl rollout restart deployment/worker-service -n hub-staging

# 6. Verify services are healthy after restart
curl -f https://stagingmeshant-internal.example.com/health/
echo "Exit code: $?"  # Should be 0

# 7. Test authentication with new secret
curl -X POST https://stagingmeshant-internal.example.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@meshant.com","password":"test"}' | jq .
```

### Expected Output
- Secret updated with new version
- Pods restart and become healthy
- Authentication endpoint returns valid (non-500) response
- Old JWT tokens invalidated (expected — clients must re-authenticate)

### Failure Scenarios
- **Secret update fails:** IAM permission issue — check `secretsmanager:PutSecretValue`
- **Pods crash after restart:** New secret values incompatible — roll back to previous version
- **Health check fails:** Check pod logs `kubectl logs -l app=api-service -n hub-staging`

---

## 3. TLS Certificate Renewal Drill

### Purpose
Verify TLS certificates can be renewed before expiry without downtime.

### Prerequisites
- cert-manager or manual TLS certificate management
- Access to the Kubernetes cluster
- Traefik ingress controller configured

### Step-by-Step

```bash
# 1. Check current certificate expiry
echo | openssl s_client -servername stagingmeshant-internal.example.com \
  -connect stagingmeshant-internal.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates

# 2. Check cert-manager certificate status (if using cert-manager)
kubectl get certificates -n hub-staging
kubectl describe certificate hub-tls -n hub-staging | grep -A5 "Status:"

# 3. Force certificate renewal (cert-manager)
kubectl delete secret hub-tls -n hub-staging  # Delete old secret
kubectl annotate certificate hub-tls -n hub-staging \
  cert-manager.io/issuer-kind=ClusterIssuer \
  cert-manager.io/issuer-name=letsencrypt-prod --overwrite

# 4. Wait for new certificate issuance
kubectl wait --for=condition=Ready certificate/hub-tls -n hub-staging --timeout=120s

# 5. Verify new certificate
echo | openssl s_client -servername stagingmeshant-internal.example.com \
  -connect stagingmeshant-internal.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates -issuer

# 6. Verify HTTPS endpoints work
curl -f -I https://stagingmeshant-internal.example.com/health/
echo "Exit code: $?"  # Should be 0

# 7. Check browser-trusted chain
openssl s_client -servername stagingmeshant-internal.example.com \
  -connect stagingmeshant-internal.example.com:443 -showcerts </dev/null 2>/dev/null | \
  openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt
```

### Expected Output
- New certificate issued with expiry date ~90 days from now
- Issuer is the expected CA (e.g., Let's Encrypt R3)
- All HTTPS endpoints return 200
- Certificate chain verifies against system trust store

### Failure Scenarios
- **ACME challenge fails:** DNS record missing — verify domain resolves to cluster IP
- **Rate limited by CA:** Too many renewal attempts — wait and retry
- **Old cert still served:** Traefik cache — restart Traefik pods

---

## 4. Helm Rollback Drill

### Purpose
Verify Helm can roll back a failed deployment to the last known good release.

### Prerequisites
- `helm` CLI installed and configured for the cluster
- At least 2 successful releases in the deployment history
- Access to `helm/` chart directory

### Step-by-Step

```bash
# 1. Check current release
helm list -n hub-staging
REVISION=$(helm list -n hub-staging -o json | jq -r '.[0].revision')
echo "Current revision: $REVISION"

# 2. Record current pod versions before rollback
kubectl get pods -n hub-staging -o json | jq -r '.items[] | "\(.metadata.name): \(.spec.containers[0].image)"'

# 3. Simulate a bad deploy (deploy with invalid image tag)
# (Skip in drill — this is documented for reference)
# helm upgrade hub helm/ -n hub-staging --set image.tag=broken-tag

# 4. Rollback to previous revision
helm rollback hub $((REVISION - 1)) -n hub-staging

# 5. Wait for rollout to complete
kubectl rollout status deployment/api-service -n hub-staging --timeout=120s
kubectl rollout status deployment/worker-service -n hub-staging --timeout=120s

# 6. Verify health after rollback
curl -f https://stagingmeshant-internal.example.com/health/
echo "Exit code: $?"  # Should be 0

# 7. Verify correct image tags after rollback
kubectl get pods -n hub-staging -o json | jq -r '.items[] | "\(.metadata.name): \(.spec.containers[0].image)"'

# 8. Check Helm release history
helm history hub -n hub-staging
```

### Expected Output
- `helm rollback` completes without errors
- Pods restart with previous version's image tags
- Health endpoint returns 200
- Helm history shows rollback as the latest revision
- Rollback completes within 3 minutes

### Failure Scenarios
- **Rollback target has deleted resources:** Helm state mismatch — use `helm rollback --force`
- **Database migration conflict:** New migrations applied that old code can't handle — manually revert migrations
- **ConfigMap drift:** Rolled-back version references deleted ConfigMap — restore from backup

---

## Drill Schedule

| Drill | Frequency | Owner | Duration |
|---|---|---|---|
| Backup/Restore | Monthly | DevOps | 30 min |
| Secrets Rotation | Quarterly | Security | 20 min |
| TLS Renewal | Quarterly (or before expiry) | DevOps | 15 min |
| Helm Rollback | Monthly | DevOps | 20 min |

## Related Documentation
- [docs/test-infrastructure/README.md](README.md) — Test infrastructure index
- [CLAUDE.md](../../CLAUDE.md) — Project conventions
