# Security Maturity — Meshant Platform

**Last updated:** 2026-05-15

## A.3.1 — Third-Party Penetration Test

**Status:** ⏭️ Requires procurement. Previous pen test ledger exists at `docs/audit-reports/232-pen-test-ledger.md` (Phase 232 public DSAR endpoints).

### Procurement Checklist
- [ ] Select vendor (recommendations: Bishop Fox, Cure53, Trail of Bits)
- [ ] Define scope: staging environment, all API endpoints, frontend, auth system
- [ ] Schedule: 2-week test window
- [ ] Remediate all high/critical findings before production launch
- [ ] Document accepted risks for medium/low

## A.3.2 — Bug Bounty Program (Private)

**Status:** ⏭️ Documented 2026-05-15. Requires program setup on platform.

### Program Configuration
- **Platform:** HackerOne or Bugcrowd (private, invitation-only)
- **Scope:** `meshant.com`, `*meshant-internal.example.com`, API endpoints
- **Reward tiers:** Critical ($2,500), High ($1,000), Medium ($500), Low ($100)
- **First 3 months:** Private — 5-10 invited researchers
- **Month 4+:** Public (based on private program performance)

### Security Policy
See `SECURITY.md` at repo root for vulnerability disclosure policy.

### Safe Harbor
Researchers acting in good faith under this program are authorized to test:
- `https://stagingmeshant-internal.example.com`
- `https://api.stagingmeshant-internal.example.com`
- No DDoS, no social engineering, no physical testing

## A.3.3 — SOC 2 Type II Audit

**Status:** ⏭️ Requires audit firm engagement. Automated evidence collection infrastructure exists.

### Existing Evidence Sources
- **AWS Config:** Resource compliance history (via Terraform `aws_config` module)
- **CloudTrail:** API activity logs (S3 bucket, 90-day retention)
- **GitHub Audit Log:** Repository activity (via `gh audit-log`)
- **PagerDuty:** Incident response records
- **1Password:** Access control records

### Evidence Automation
```bash
# Collect evidence for audit period
python scripts/collect_soc2_evidence.py --start 2026-01-01 --end 2026-06-30

# Generates:
#   evidence/aws_config_compliance.json
#   evidence/cloudtrail_security_events.csv
#   evidence/github_audit_log.csv
#   evidence/incident_response_timeline.json
```

### Timeline
- Month 1-2: Select audit firm, define scope
- Month 3-4: Evidence collection automation
- Month 4-8: Audit period (minimum 6 months for Type II)
- Month 9: Report delivery

## A.3.4 — Secrets Rotation Automation

**Status:** ✅ INFRASTRUCTURE EXISTS. 12 helm template files with ExternalSecret/SecretStore.

### Secrets Inventory (17 total)
| Secret | Rotation Method | Rotation Period |
|---|---|---|
| Database password | AWS Secrets Manager + ExternalSecrets | 90 days |
| Redis auth token | AWS Secrets Manager + ExternalSecrets | 90 days |
| Django SECRET_KEY | AWS Secrets Manager | 180 days |
| Internal API key | AWS Secrets Manager + ExternalSecrets | 90 days |
| Stripe secret key | AWS Secrets Manager | 90 days |
| Stripe webhook secret | AWS Secrets Manager | 90 days |
| AWS SES SMTP password | AWS Secrets Manager | 90 days |
| PgBouncer auth password | AWS Secrets Manager | 90 days |
| PgBouncer admin password | AWS Secrets Manager | 90 days |
| Fuseki admin password | AWS Secrets Manager | 90 days |
| Grafana admin password | AWS Secrets Manager | 180 days |
| MinIO root password | AWS Secrets Manager | 90 days |
| Prefect DB password | AWS Secrets Manager | 90 days |
| Redis cache password | AWS Secrets Manager | 90 days |
| Redis channels password | AWS Secrets Manager | 90 days |
| Redis events password | AWS Secrets Manager | 90 days |
| Redis queue password | AWS Secrets Manager | 90 days |

### Zero-Touch Rotation
All 17 secrets use AWS Secrets Manager with automatic rotation via Lambda. ExternalSecrets operator syncs to K8s secrets within refresh interval. Pods mount via volume or envFrom.

### Rotation Verification
```bash
# Check ExternalSecret status for all secrets
kubectl get externalsecrets -n hub-staging
# All should show: STATUS=SecretSynced, SYNCED=2026-05-15T...
```

## A.3.5 — Dependabot Auto-Merge

**Status:** ⏭️ Workflow documented 2026-05-15. Requires `.github/workflows/dependabot-auto-merge.yml`.

### Configuration
```yaml
# .github/workflows/dependabot-auto-merge.yml
name: Dependabot Auto-Merge
on: pull_request_target
permissions:
  contents: write
  pull-requests: write
jobs:
  auto-merge:
    if: github.actor == 'dependabot[bot]'
    steps:
      - uses: dependabot/fetch-metadata@v2
      - if: steps.metadata.outputs.update-type == 'version-update:semver-patch' ||
            steps.metadata.outputs.update-type == 'version-update:semver-minor'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Policy:**
- **Patch updates** (e.g., 1.2.3 → 1.2.4): auto-merge if CI passes
- **Minor updates** (e.g., 1.2.3 → 1.3.0): auto-merge if CI passes
- **Major updates** (e.g., 1.2.3 → 2.0.0): manual review required
- **Security updates**: auto-merge if CI passes (urgency overrides policy)
