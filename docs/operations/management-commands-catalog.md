# Management Commands Catalog

**Version**: 1.0 | **Generated**: auto-generated  
**Total commands**: 122 (Django management commands across all apps)

## Classification

| Classification | Definition |
|---------------|------------|
| **Read-only** | No database writes; safe to run in production |
| **Destructive** | Modifies or deletes data; requires confirmation |
| **Idempotent** | Safe to run multiple times; same result each run |
| **Audit-emitting** | Writes to `audit_events` table |

## Commands by App

### tenants

| Command | Classification | Audit | Description |
|---------|---------------|-------|-------------|
| `seed_default_plans` | Idempotent | No | Seeds canonical plans from plan_defaults.py |
| `validate_plan_config` | Read-only | No | Validates plan config integrity |
| `backfill_enterprise_limits` | Destructive | Yes | Backfills Enterprise plan limits |
| `tenant_hard_delete_sweep` | Destructive | Yes | Cascading tenant hard-delete sweep |
| `expire_impersonation_sessions` | Destructive | Yes | Expires stale impersonation sessions |
| `init_tenant_configs` | Idempotent | No | Initializes configs for existing tenants |
| `send_deprecation_notices` | Read-only | No | Sends deprecation notices |
| `refresh_kyc_status` | Read-only | No | Refreshes KYC status from provider |
| `purge_test_data` | Destructive | No | Purges E2E test data |
| `enable_ux_v2_for_tenant` | Destructive | Yes | Enables UX v2 for a tenant |
| `disable_ux_v2_for_tenant` | Destructive | Yes | Disables UX v2 for a tenant |
| `list_ux_v2_tenants` | Read-only | No | Lists tenants with UX v2 |
| `ensure_e2e_subscription` | Idempotent | No | Ensures E2E test subscription exists |

### billing

| Command | Classification | Audit | Description |
|---------|---------------|-------|-------------|
| `sync_stripe_products` | Idempotent | No | Syncs plans to Stripe Products |
| `reconcile_stripe` | Read-only | No | Reconciles subscriptions with Stripe |
| `billing_cleanup` | Destructive | No | Cleans up stale billing records |

### audit

| Command | Classification | Audit | Description |
|---------|---------------|-------|-------------|
| `check_throttle_coverage` | Read-only | No | AST-scans views for throttle_classes |

### core

| Command | Classification | Audit | Description |
|---------|---------------|-------|-------------|
| `check_config_validation` | Read-only | No | Validates Django configuration |

## Running Safely

```bash
# Always dry-run first for destructive commands
python hub/manage.py <command> --dry-run

# Read-only commands are always safe
python hub/manage.py <command>

# Destructive commands need confirmation
python hub/manage.py <command> --confirm
```

## CI-Integrated Commands

These run in CI on every push:

| Command | CI Job | Blocks Merge |
|---------|--------|-------------|
| `check_throttle_coverage` | `django-tests` | Yes |
| `validate_plan_config --strict` | `django-tests` | Yes |
| `check_ga_gate_scores.py` | `lint` | Yes |
| `check_stale_defaults.py` | `lint` | Yes |
| `lint_rls_policies.py` | `lint-rls-policies` | Yes |
