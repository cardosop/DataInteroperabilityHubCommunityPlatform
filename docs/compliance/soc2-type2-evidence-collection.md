# SOC 2 Type II — Evidence Collection & Audit Readiness (281.B.4.1)

**Date:** 2026-05-15  
**Framework:** AICPA SOC 2 Type II (Security, Availability, Confidentiality)  
**Audit Period:** 6 months (target: 2026-07-01 to 2026-12-31)

## 1. Trust Services Criteria (TSC) Mapping

### Security (Common Criteria — CC)

| TSC Ref | Control | Evidence Source | Status |
|---|---|---|---|
| CC1.1 | Code of conduct / ethics policy | `docs/process/` — code of conduct | ✅ |
| CC1.2 | Responsibility assignments | `docs/raci/` — responsibility matrix | ✅ |
| CC2.1 | Risk assessment process | `docs/risk-register/` — risk register | ⚠️ Needs quarterly update |
| CC2.2 | Vendor risk management | `docs/operations/third-party-risk-assessment.md` | ✅ |
| CC3.1 | Security policies | `docs/security/` — security policy suite | ✅ |
| CC3.2 | Security awareness training | HR records (external) | ⚠️ Needs evidence upload |
| CC4.1 | Monitoring activities | `monitoring/prometheus/alerts/` — alert rules (33 files) | ✅ |
| CC4.2 | Vulnerability management | `.github/workflows/dependency-review.yml` + `security-scan.yml` | ✅ |
| CC5.1 | Logical access controls | RLS policies (`scripts/lint_rls_policies.py`) + ABAC engine | ✅ |
| CC5.2 | User access provisioning | `hub/apps/governance/` — access request workflow | ✅ |
| CC5.3 | User access review | `scripts/access_review.py` (281.B.4.3) | ⚠️ Needs automation |
| CC6.1 | Change management | `docs/process/` — change management policy | ⚠️ Needs doc |
| CC6.2 | Deployment pipeline | `.github/workflows/deploy.yml` — CI/CD pipeline | ✅ |
| CC6.3 | Separation of duties | Terraform plan + apply separation (CI vs manual approval) | ✅ |
| CC7.1 | Incident response | `docs/runbooks/postmortem-template.md` + PagerDuty | ✅ |
| CC7.2 | Business continuity | `docs/operations/bcp-supply-chain.md` | ✅ |
| CC8.1 | Backup and recovery | RDS automated backups (14d prod), S3 versioning | ✅ |
| CC9.1 | Risk mitigation | Risk register + acceptance process | ⚠️ |

### Availability (A)

| TSC Ref | Control | Evidence Source | Status |
|---|---|---|---|
| A1.1 | Availability monitoring | Prometheus + AlertManager + synthetic probers | ✅ |
| A1.2 | Capacity management | `docs/operations/capacity-planning-guide.md` | ✅ |
| A1.3 | Backup and recovery testing | Game day exercises (GD-INF-01, GD-INF-02) | ✅ |

### Confidentiality (C)

| TSC Ref | Control | Evidence Source | Status |
|---|---|---|---|
| C1.1 | Data classification | `docs/compliance/data-retention-schedule.md` | ✅ |
| C1.2 | Data disposal | Loki retention (30d), RDS audit-event purging | ✅ |
| C2.1 | Encryption at rest | S3 SSE-S3, RDS KMS, ElastiCache KMS | ✅ |
| C2.2 | Encryption in transit | TLS 1.2+ everywhere (Traefik + internal CA) | ✅ |

## 2. Evidence Collection Automation (281.B.4.3)

### Per-Release Evidence Package

Each release (`git tag v*`) triggers `.github/workflows/compliance-evidence.yml` which generates:

| Artifact | Source | Format |
|---|---|---|
| Change log | `git log --oneline <prev-tag>..HEAD` | `evidence/CHANGELOG-<version>.txt` |
| Access review | `scripts/access_review.py` — lists IAM users, roles, access entries | `evidence/ACCESS_REVIEW-<version>.json` |
| Vulnerability scan | `pip-audit` + `npm audit` reports | `evidence/VULN_SCAN-<version>.json` |
| Dependency inventory | `pip-licenses` + `license-checker` SBOM | `evidence/SBOM-<version>.spdx.json` |
| Config drift | `terraform plan` diff output | `evidence/TERRAFORM_DRIFT-<version>.txt` |
| Audit event summary | `python manage.py audit_summary --since <prev-tag>` | `evidence/AUDIT_SUMMARY-<version>.json` |

### Monthly Evidence Collection

| Artifact | Schedule | Retention |
|---|---|---|
| Access review (full) | 1st of month | 12 months |
| Vulnerability scan (full) | Weekly Monday | 12 months |
| Backup verification log | Daily (automated) | 90 days |
| Incident summary | Monthly rollup | 7 years |

## 3. Audit Readiness Checklist

### Pre-Audit (30 days before)

- [ ] All TSC evidence sources verified as current (dated within audit period)
- [ ] Access review completed for all production IAM roles/users
- [ ] Vulnerability scan with zero critical/high CVEs open >30 days
- [ ] Incident response tested (game day exercise)
- [ ] Backup restoration tested
- [ ] Risk register updated with current risks and mitigations
- [ ] Subprocessor DPA inventory current (281.B.4.5)
- [ ] Data retention schedule verified (281.B.4.6 auto-enforcement running)

### During Audit

- [ ] Evidence package assembled per TSC category
- [ ] Auditor walkthroughs scheduled (architecture, SDLC, incident response)
- [ ] Sample testing data prepared (10 random access requests, 10 random changes)
- [ ] Remediation tracker for auditor findings

### Post-Audit

- [ ] Findings documented with severity and remediation plan
- [ ] Management response letter drafted
- [ ] SOC 2 report published to compliance portal
- [ ] Gap closure sprint scheduled for all findings

## 4. Evidence Retention

All audit evidence is stored in an S3 bucket (`meshant-compliance-evidence`) with:
- SSE-KMS encryption
- Versioning enabled
- Lifecycle: Glacier after 1 year, delete after 7 years
- Access: restricted to Platform Engineering + Legal roles via IAM policy
