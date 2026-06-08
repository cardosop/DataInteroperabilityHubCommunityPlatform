# Dependency Approval Process (281.A.14.8)

**Effective:** 2026-05-15  
**Owner:** Platform Engineering + Security  
**Enforcement:** CI gate (`.github/workflows/license-scan.yml`)

## Default Policy

**New dependencies are BLOCKED by default.** All new third-party packages require explicit approval before they can be merged.

## Approval Requirements

### Python Dependencies (pip)

| Check | Tool | Gate |
|---|---|---|
| License scan | `pip-licenses` | Block GPL/AGPL |
| Vulnerability audit | `pip-audit` (monthly) | Advisory (informational) |
| Maintainer health | Manual review | Reviewer judgment |
| Transitive dependency count | `pip-licenses --with-system` | Warn if >5 new transitive deps |

### JavaScript Dependencies (npm)

| Check | Tool | Gate |
|---|---|---|
| License scan | `license-checker` | Block GPL/AGPL |
| Vulnerability audit | `npm audit` | Block critical/high CVEs |
| Bundle size impact | `bundle-size-check.yml` | Warn if >10KB gzipped |
| Maintainer health | Manual review | Reviewer judgment |

## Approval Workflow

1. **Developer** adds dependency to `requirements.txt` / `package.json` in a PR
2. **CI runs** `license-scan.yml` — auto-blocks if GPL/AGPL detected
3. **Developer** fills in the PR template section:
   ```
   ### New Dependencies
   - **Package:** <name> <version>
   - **License:** <license>
   - **Purpose:** <why this package is needed>
   - **Alternatives considered:** <other packages evaluated>
   - **Transitive deps:** <count> new packages
   ```
4. **Reviewer** verifies: license acceptable (MIT/Apache/BSD/ISC), no known CVEs, purpose justified, alternatives documented
5. **Security reviewer** (for packages touching auth, crypto, networking, or data processing) approves
6. **Merge** — dependency is now approved

## Exemptions

### Pre-Approved Licenses (auto-approved)

- MIT, Apache 2.0, BSD (2-clause, 3-clause), ISC, Python-2.0, MPL-2.0
- Public Domain (CC0, Unlicense)
- PSF, PostgreSQL, Zlib

### Blocked Licenses (auto-rejected)

- GPL (any version), AGPL (any version), LGPL (requires security review)
- SSPL, BSL (Business Source License), WTFPL
- Any custom/"source-available" license without explicit legal review

### Emergency Exemption (SEV1 fixes only)

- On-call engineer may merge a dependency without full review for SEV1 fixes
- Must file a **dependency exception ticket** within 24 hours
- Exception ticket triggers retroactive review within 5 business days
- Unapproved emergency deps are flagged in the next monthly audit

## Quarterly Audit

| Activity | Owner | Schedule |
|---|---|---|
| Review all dependency exception tickets | Platform + Security | Monthly |
| Audit stale/outdated pinned deps | Platform | Quarterly |
| Review deprecated packages for removal | Platform | Quarterly |
| Update blocked-license list | Legal + Security | Annually |

## SBOM

Every release generates an SPDX-format Software Bill of Materials (`.github/workflows/license-scan.yml` `sbom-generate` job). SBOMs are:
- Uploaded as release artifacts (365-day retention)
- Named `sbom.spdx.json` with `documentNamespace: https://meshant.com/sbom/<git-sha>`
- List all Python dependencies with name, version, and license
