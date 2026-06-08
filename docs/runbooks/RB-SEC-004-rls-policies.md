# RB-SEC-004 — RLS Policy Management

**Owner**: Security Engineering
**Severity**: Critical (tenant data isolation)

## Purpose

Every model with a `tenant_id` ForeignKey MUST have a paired RLS (Row-Level Security) `CREATE POLICY` migration. This runbook covers the lifecycle: adding RLS to new models, auditing existing coverage, and triaging RLS leaks.

## Quick Reference

```bash
# Check RLS coverage (CI gate)
python scripts/lint_rls_policies.py --fail-on-new

# Check a specific app
python scripts/lint_rls_policies.py --app billing

# List all exemptions
cat scripts/exemptions/rls_exemptions.yaml
```

## Adding RLS to a New Model

1. Follow the template in `docs/rls-migration-template.md`
2. CREATE POLICY before ENABLE ROW LEVEL SECURITY
3. Naming: `tenant_isolation_{table_name}`
4. Direct FK: `USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`
5. Run pre-flight tenant_context audit (285.14.1.3)
6. Document findings in migration docstring

## Triage: RLS Leak Detected

If `lint_rls_policies.py` reports a violation:

1. Identify the model and its `tenant_id` field
2. Check if an exemption applies (see `scripts/exemptions/rls_exemptions.yaml`)
3. If no exemption: create RLS migration following the template
4. If exemption: add entry to `rls_exemptions.yaml` with reason, review_date, sunset_date
5. Re-run lint to verify

## Exemption Lifecycle

- Review all exemptions monthly
- Remove stale exemptions where sunset_date has passed (model must get RLS or new exemption)
- Do NOT let exemptions accumulate — each one is a tenant isolation gap

## CI Enforcement

- `lint-rls-policies` job in `.github/workflows/ci.yml`
- Blocks PRs that add new `tenant_id` columns without paired RLS migrations
- Exemptions reviewed in `validate-security` job
