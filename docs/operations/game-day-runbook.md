# Game Day Runbook — Meshant Platform

**Last updated:** 2026-05-15

## A.6.1 — Game Day 1: PostgreSQL Primary Failure

**Objective:** Verify RDS Multi-AZ automated failover within 60s. Measure application recovery time.

### Setup
```bash
# 1. Verify multi-AZ is enabled
aws rds describe-db-instances --db-instance-identifier meshant-staging \
  --query 'DBInstances[0].MultiAZ' --profile staging

# 2. Start monitoring
watch -n 2 'curl -s https://api.stagingmeshant-internal.example.com/api/v1/health/ | jq .status'

# 3. In another terminal, tail logs
kubectl logs -f -l app=hub-api -n hub-staging --tail=5
```

### Execution
```bash
# Trigger RDS failover (reboot with failover)
aws rds reboot-db-instance --db-instance-identifier meshant-staging \
  --force-failover --profile staging
```

### Success Criteria
- [ ] RDS failover completes in <60s (check AWS Console → Events)
- [ ] API health check returns `healthy` within 120s of failover start
- [ ] All pods reconnect to new primary without restart
- [ ] No data loss: verify last 10 audit events present after failover
- [ ] PgBouncer reconnects to new primary automatically

### Recovery Verification
```bash
# Verify DB is writable
datahub assets create --name "game-day-test-$(date +%s)" --key "gd-$(date +%s)"

# Verify data integrity
datahub assets list --limit 5

# Cleanup
datahub assets delete <asset_id> --confirm
```

## A.6.2 — Game Day 2: Redis Primary Failure

**Objective:** Verify ElastiCache automatic failover for all 4 Redis instances.

### Setup
```bash
# 1. Identify primaries
for group in cache channels events queue; do
  aws elasticache describe-replication-groups \
    --replication-group-id "meshant-staging-${group}" \
    --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint' \
    --profile staging
done

# 2. Start monitoring session activity
kubectl logs -f -l app=hub-api -n hub-staging | grep -i redis
```

### Execution
```bash
# Trigger failover on Redis cache (highest impact)
aws elasticache test-failover \
  --replication-group-id meshant-staging-cache \
  --node-group-id 0001 --profile staging

# Repeat for channels, events, queue
```

### Success Criteria
- [ ] Redis failover completes in <60s (ElastiCache SLA)
- [ ] Django `django-redis` auto-reconnects (IGNORE_EXCEPTIONS=True)
- [ ] Cache misses fall back to direct DB reads (no 5xx errors)
- [ ] WebSocket connections via channels re-establish within 30s
- [ ] Queued tasks resume processing within 60s

## A.6.3 — Game Day 3: Stripe API Outage

**Objective:** Verify marketplace graceful degradation when Stripe is unreachable.

### Setup
```bash
# 1. Create a test listing in marketplace
datahub marketplace listings create --title "Game Day Test" --asset-id <id>

# 2. Start monitoring Stripe API health
curl -I https://api.stripe.com/v1/
```

### Execution
```bash
# Simulate Stripe outage by blocking outbound Stripe traffic
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-stripe-gameday
  namespace: hub-staging
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except: [54.187.0.0/16, 54.88.0.0/16]  # Stripe IP ranges
EOF

# Attempt marketplace checkout
datahub marketplace orders create --listing-id <listing_id>
```

### Success Criteria
- [ ] Checkout returns 503 (not 500) — graceful degradation
- [ ] Payment intents queued in Redis for retry
- [ ] "Payments temporarily unavailable" message shown in UI
- [ ] Non-marketplace APIs unaffected
- [ ] Existing entitlements still valid (read-only)

### Cleanup
```bash
kubectl delete networkpolicy block-stripe-gameday -n hub-staging
```

## A.6.4 — Chaos Engineering Tooling

**Status:** ⏭️ Not deployed. Documented for setup.

### Tool Selection: Chaos Mesh
```bash
# Install Chaos Mesh on staging cluster
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

### Monthly Experiment Schedule
| Experiment | Type | Target | Frequency | Duration |
|---|---|---|---|---|
| Pod kill (API) | `PodChaos` | `app=hub-api` | 1st Monday | 5 min |
| Network latency | `NetworkChaos` | `app=hub-api` → `role=db` | 2nd Monday | 10 min |
| CPU stress | `StressChaos` | `app=worker` | 3rd Monday | 5 min |
| DNS failure | `DNSChaos` | `app=hub-api` | 4th Monday | 5 min |

## A.6.5 — Postmortem Tracking

**Status:** ⏭️ Requires real incidents. No postmortems exist yet (zero SEV1 incidents is good).

### Template
Use `docs/runbooks/postmortem-template.md` for all postmortems.

### MTTR Tracking
| Quarter | Incidents | MTTR | Action Items | Trending |
|---|---|---|---|---|
| Q2 2026 | 0 | N/A | N/A | Baseline |
| Q3 2026 | TBD | TBD | TBD | vs Q2 |
| Q4 2026 | TBD | TBD | TBD | vs Q3 |

## A.6.6 — Runbook Game Day

**Status:** ⏭️ Requires simulated failures against each runbook.

### Runbook Inventory (16 runbooks)
| Runbook | Game Day Test | Status |
|---|---|---|
| `RB-DB-001.md` (DB connection exhaustion) | Kill PgBouncer → verify reconnection | ⏭️ |
| `RB-DB-002.md` (DB failover) | Covered by A.6.1 | ⏭️ |
| `RB-QUEUE-001.md` (Redis failure) | Covered by A.6.2 | ⏭️ |
| `RB-SVC-001.md` (API 5xx spike) | Kill API pods → verify K8s restart | ⏭️ |
| `RB-DEPLOY-001.md` (Deploy failure) | Deploy broken image → verify rollback | ⏭️ |
| `RB-SEC-001.md` (Security incident) | Simulate credential leak → verify rotation | ⏭️ |
| `RB-MKT-003.md` (Payout failure) | Covered by A.6.3 (Stripe outage) | ⏭️ |
| `RB-WH-001.md` (Webhook DLQ) | Send malformed webhooks → verify DLQ | ⏭️ |
| `RB-DB-003.md` (Disk full) | Fill volume → verify alert + cleanup | ⏭️ |
| `RB-DEPLOY-002.md` (Rollback) | Deploy broken migration → verify rollback | ⏭️ |
| `RB-AUTH-001.md` (RLS kill switch) | Enable RLS → verify tenant isolation | ⏭️ |
| `RB-MKT-001.md` (KYC failure) | Simulate Stripe Connect failure | ⏭️ |
| `RB-MKT-002.md` (Refund discrepancy) | Create test refund → verify idempotency | ⏭️ |
| `RB-SEC-001-credential-rotation.md` | Rotate DB password → verify ExternalSecret sync | ⏭️ |
| `RB-CMP-002.md` (Legal basis strict mode) | Enable strict mode → verify compliance gate | ⏭️ |
| `prefect-runbook.md` | Kill Prefect server → verify flow recovery | ⏭️ |

### Game Day Procedure (per runbook)
1. Read runbook fully (5 min)
2. Simulate the failure described (5 min)
3. Execute recovery steps per runbook (10 min)
4. Verify service returns to healthy state (5 min)
5. Document any gaps or outdated steps (5 min)
6. Update runbook if needed (10 min)

**Total per runbook:** ~40 min. **All 16 runbooks:** ~11 hours (spread over 3-4 sessions).
