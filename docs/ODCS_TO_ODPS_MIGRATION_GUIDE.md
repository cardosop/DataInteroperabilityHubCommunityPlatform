# ODCS to ODPS Migration Guide

**Version**: 1.0
**Last Updated**: 2025-12-24
**Status**: Production Ready

## Table of Contents

1. [Overview](#overview)
2. [When to Run Migration](#when-to-run-migration)
3. [Prerequisites](#prerequisites)
4. [Migration Process](#migration-process)
5. [Rollback Process](#rollback-process)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Reference](#reference)

---

## Overview

This guide provides comprehensive instructions for migrating existing Open Data Contract Standard (ODCS) contracts to Open Data Product Standard (ODPS) contracts. The migration process:

- **Creates ODPS contracts** from ODCS contracts with marketplace metadata
- **Preserves all data** from the original HubContract
- **Establishes bidirectional links** between ODPS and ODCS contracts
- **Maintains marketplace metadata** throughout the migration
- **Supports validation** to ensure migration success
- **Provides rollback capabilities** if needed

### Key Concepts

- **ODCS (Open Data Contract Standard)**: The original contract format
- **ODPS (Open Data Product Standard)**: The target contract format (version 4.1)
- **HubContract**: The normalized internal representation of contracts
- **Bidirectional Linking**: ODPS ↔ ODCS links maintained in both contracts
- **Marketplace Metadata**: License, pricing, access methods, and payment gateway information

---

## When to Run Migration

### Migration Strategy: Opt-In

Migration is **opt-in** and should be performed when:

1. **You want to leverage ODPS features** such as:
   - Enhanced marketplace capabilities
   - Improved product catalog integration
   - Better support for data product lifecycle management

2. **You have ODCS contracts with marketplace metadata** that would benefit from ODPS format

3. **You're preparing for future features** that require ODPS contracts

### Migration Modes

The migration supports three execution modes:

#### 1. Per-Contract Migration (Recommended for Testing)

Migrate a single contract for testing or validation:

```bash
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --dry-run
```

**Use Cases:**
- Testing migration on a single contract
- Validating migration process before batch execution
- Migrating specific contracts on-demand

#### 2. Batch Migration (Recommended for Production)

Migrate multiple contracts in batches:

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --tenant-id <tenant-uuid> \
    --skip-linked
```

**Use Cases:**
- Migrating all eligible contracts for a tenant
- Production migrations with controlled batch sizes
- Systematic migration of contract portfolios

#### 3. Full Migration (Use with Caution)

Migrate all eligible contracts across all tenants:

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --skip-linked
```

**Use Cases:**
- System-wide migrations
- Initial migration setup
- **Warning**: Only use after thorough testing

### Migration Eligibility

A contract is eligible for migration if:

1. ✅ **Contract type**: Must be `ODCS` (original_spec_type = ODCS)
2. ✅ **HubContract exists**: Must have `hub_contract_json` populated
3. ✅ **Marketplace metadata**: Must have marketplace fields (configurable via `--min-marketplace-fields`)
4. ✅ **Not already migrated**: Must not already have an ODPS link (unless `--skip-linked` is not used)

### When NOT to Migrate

Do **NOT** migrate if:

- ❌ Contract is in active use and migration might cause disruption
- ❌ Contract has critical dependencies that require ODCS format
- ❌ You haven't tested the migration process in a staging environment
- ❌ You don't have a rollback plan in place
- ❌ Contract lacks marketplace metadata (unless you plan to add it later)

---

## Prerequisites

### System Requirements

1. **Docker Compose Environment**
   ```bash
   # Verify services are running
   docker compose -f docker-compose.dev.yml ps
   ```

2. **Database Access**
   - Database must be accessible
   - Sufficient database permissions for contract creation
   - Transaction support enabled

3. **Service Dependencies**
   - API service must be running
   - Redis (for async tasks) must be running
   - All required services operational

### Pre-Migration Checklist

Before running migration, verify:

- [ ] **Backup Database**: Create a full database backup
  ```bash
  # Example backup command (adjust for your setup)
  pg_dump -h localhost -U postgres -d hub > backup_before_migration_$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Test Environment**: Run migration in test/staging first
- [ ] **Review Contracts**: Identify contracts to migrate
- [ ] **Check Marketplace Data**: Verify contracts have marketplace metadata
- [ ] **Validate HubContract**: Ensure HubContract data is complete
- [ ] **Plan Rollback**: Understand rollback procedure
- [ ] **Notify Stakeholders**: Inform relevant teams about migration

### Required Permissions

- **Database**: Read/write access to `contracts` table
- **API Service**: Ability to execute management commands
- **Tenant Context**: Access to tenant data (if using `--tenant-id`)

### Contract Requirements

For a contract to be successfully migrated, it must have:

1. **Valid HubContract JSON**:
   ```json
   {
     "hub_contract_version": "1.0.0",
     "id": "contract-id",
     "info": { ... },
     "schema": { ... },
     "marketplace": {
       "license_summary": "...",
       "intended_use": [...],
       "restricted_use": [...],
       "x_odps": {
         "pricing_plans": [...],
         "access_methods": {...},
         "payment_gateways": {...}
       }
     }
   }
   ```

2. **Original ODCS Contract**: `original_raw` field must contain valid ODCS contract

3. **Marketplace Fields**: At least one marketplace field (configurable)

---

## Migration Process

### Step 1: Dry Run (Always Start Here)

**Always perform a dry run first** to validate the migration without making changes:

```bash
python manage.py migrate_contracts_to_odps \
    --dry-run \
    --contract-id <contract-uuid>
```

**Dry run output includes:**
- Number of contracts that would be migrated
- Validation results
- Any errors or warnings
- Estimated impact

### Step 2: Validate Prerequisites

Check that contracts meet migration requirements:

```bash
# Check specific contract
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --dry-run \
    --min-marketplace-fields 1
```

Review the output to ensure:
- Contract is eligible
- Marketplace metadata is present
- No blocking issues

### Step 3: Execute Migration

#### Option A: Single Contract Migration

```bash
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

#### Option B: Batch Migration (Tenant-Specific)

```bash
python manage.py migrate_contracts_to_odps \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

#### Option C: Full Batch Migration

```bash
python manage.py migrate_contracts_to_odps \
    --batch-size 100 \
    --skip-linked \
    --target-odps-version 4.1 \
    --min-marketplace-fields 1 \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

### Step 4: Validate Migration

After migration, validate the results:

```bash
# Validate all migrations
python manage.py validate_migration \
    --format text \
    --report-path /tmp/validation_report.json

# Validate specific contracts
python manage.py validate_migration \
    --contract-ids <id1>,<id2>,<id3> \
    --format json \
    --report-path /tmp/validation_report.json

# Validate tenant-specific migrations
python manage.py validate_migration \
    --tenant-id <tenant-uuid> \
    --format text
```

**Validation checks:**
- ✅ All contracts migrated successfully
- ✅ No data loss (HubContract comparison)
- ✅ Links are correct (bidirectional validation)
- ✅ Marketplace metadata preserved
- ✅ Statistics and report generation

### Step 5: Review Migration Report

Review the validation report:

```bash
# View text report
cat /tmp/validation_report.json | python -m json.tool

# Or use the text format
python manage.py validate_migration --format text
```

**Report includes:**
- Total contracts processed
- Migration success rate
- Issues found (errors, warnings)
- Data loss detection
- Link validation results
- Marketplace metadata preservation status

### Step 6: Verify in Application

1. **Check Contract Links**: Verify bidirectional links in UI/API
2. **Verify Marketplace Data**: Confirm marketplace metadata is accessible
3. **Test ODPS Features**: Test any ODPS-specific features
4. **Monitor Logs**: Check for any errors or warnings

---

## Rollback Process

### When to Rollback

Rollback should be performed if:

- ❌ Migration validation reveals critical issues
- ❌ Data loss is detected
- ❌ Links are broken or incorrect
- ❌ Marketplace metadata is missing or corrupted
- ❌ Application errors occur after migration
- ❌ Business requirements change

### Rollback Prerequisites

Before rolling back:

- [ ] **Backup Current State**: Create backup of current database state
- [ ] **Review Impact**: Understand what will be rolled back
- [ ] **Plan Restoration**: Know how to restore if needed
- [ ] **Notify Stakeholders**: Inform relevant teams

### Rollback Steps

#### Step 1: Dry Run Rollback

**Always start with a dry run:**

```bash
python manage.py rollback_odps_migration \
    --dry-run \
    --contract-id <contract-uuid>
```

#### Step 2: Execute Rollback

##### Option A: Single Contract Rollback

```bash
python manage.py rollback_odps_migration \
    --contract-id <contract-uuid>
```

##### Option B: Batch Rollback (Tenant-Specific)

```bash
python manage.py rollback_odps_migration \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-unlinked
```

##### Option C: Full Batch Rollback

```bash
python manage.py rollback_odps_migration \
    --batch-size 100 \
    --skip-unlinked
```

#### Step 3: Verify Rollback

After rollback, verify:

1. **ODPS Links Removed**: Check that ODCS contracts no longer have ODPS links
2. **ODPS Contracts Deleted**: Verify ODPS contracts are removed
3. **ODCS Contracts Intact**: Ensure ODCS contracts are unchanged
4. **No Orphaned Data**: Check for any orphaned references

```bash
# Validate rollback (check that contracts are unlinked)
python manage.py validate_migration \
    --contract-ids <contract-uuid> \
    --format text
```

**Expected result**: Contract should show as "NOT MIGRATED"

### Rollback What It Does

The rollback process:

1. **Removes ODPS Links**: Removes `odps_link` from ODCS contracts
2. **Removes ODCS Links**: Removes `odcs_link` from ODPS contracts
3. **Deletes ODPS Contracts**: Deletes ODPS contracts created during migration
4. **Validates State**: Verifies that rollback completed successfully

### Rollback Limitations

⚠️ **Important Notes:**

- Rollback **cannot restore** ODCS contracts if they were modified during migration
- Rollback **deletes** ODPS contracts permanently (ensure backups exist)
- Rollback **does not restore** previous ODPS links if they existed before migration
- Rollback **requires** ODPS contracts to exist (cannot rollback if already deleted)

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Contract Not Eligible for Migration

**Symptoms:**
```
Contract <uuid> not found or not eligible
```

**Causes:**
- Contract is not ODCS type
- Contract lacks HubContract JSON
- Contract lacks marketplace metadata
- Contract already has ODPS link

**Solutions:**

1. **Check Contract Type**:
   ```bash
   # Verify contract type
   python manage.py shell
   >>> from hub.apps.contracts.models import Contract
   >>> contract = Contract.objects.get(id='<uuid>')
   >>> print(contract.original_spec_type)  # Should be 'ODCS'
   ```

2. **Check HubContract**:
   ```bash
   >>> print(contract.hub_contract_json is not None)  # Should be True
   ```

3. **Check Marketplace Metadata**:
   ```bash
   >>> marketplace = contract.hub_contract_json.get('marketplace', {})
   >>> print(marketplace)  # Should have marketplace fields
   ```

4. **Check Existing Links**:
   ```bash
   >>> extensions = contract.hub_contract_json.get('extensions', {})
   >>> x_odps = extensions.get('x_odps', {})
   >>> print(x_odps.get('odps_link'))  # Should be None if not migrated
   ```

#### Issue 2: Migration Fails with Validation Error

**Symptoms:**
```
Validation error: ODPS normalization failed
```

**Causes:**
- Invalid HubContract structure
- Missing required fields
- Marketplace metadata format issues

**Solutions:**

1. **Validate HubContract**:
   ```bash
   python manage.py shell
   >>> from hub.apps.contracts.typed_models import validate_hub_contract_dict
   >>> result, errors = validate_hub_contract_dict(contract.hub_contract_json)
   >>> print(errors)  # Review validation errors
   ```

2. **Check Marketplace Format**:
   - Ensure `marketplace.license_summary` is a string
   - Ensure `marketplace.intended_use` is an array
   - Ensure `marketplace.restricted_use` is an array
   - Ensure `marketplace.x_odps` structure is correct

3. **Fix HubContract**:
   - Update HubContract JSON to fix validation errors
   - Re-run migration

#### Issue 3: Data Loss Detected During Validation

**Symptoms:**
```
Validation completed with X error(s)
Data loss detected in HubContract comparison
```

**Causes:**
- HubContract sections missing in ODPS
- Field transformations during normalization
- Marketplace metadata not preserved

**Solutions:**

1. **Review Validation Report**:
   ```bash
   python manage.py validate_migration \
       --contract-ids <uuid> \
       --format json \
       --report-path /tmp/report.json
   # Review missing_sections and differences
   ```

2. **Check Missing Sections**:
   - Review which sections are missing
   - Determine if missing sections are critical
   - Consider if sections were intentionally transformed

3. **Verify Marketplace Metadata**:
   ```bash
   # Compare marketplace data
   python manage.py shell
   >>> odcs_marketplace = odcs_contract.hub_contract_json.get('marketplace', {})
   >>> odps_marketplace = odps_contract.hub_contract_json.get('marketplace', {})
   >>> # Compare fields
   ```

4. **If Critical Data Loss**:
   - Consider rolling back the migration
   - Investigate root cause
   - Fix HubContract or migration logic
   - Re-run migration

#### Issue 4: Broken Links After Migration

**Symptoms:**
```
Link validation failed: ODPS contract does not link back to ODCS contract
```

**Causes:**
- Bidirectional links not established correctly
- Links removed or corrupted
- Contract deletion

**Solutions:**

1. **Verify Links**:
   ```bash
   python manage.py shell
   >>> # Check ODCS → ODPS link
   >>> odcs_extensions = odcs_contract.hub_contract_json.get('extensions', {})
   >>> odcs_x_odps = odcs_extensions.get('x_odps', {})
   >>> print(odcs_x_odps.get('odps_link'))

   >>> # Check ODPS → ODCS link
   >>> odps_extensions = odps_contract.hub_contract_json.get('extensions', {})
   >>> odps_x_odps = odps_extensions.get('x_odps', {})
   >>> print(odps_x_odps.get('odcs_link'))
   ```

2. **Fix Links Manually** (if needed):
   ```bash
   >>> # Restore ODCS → ODPS link
   >>> odcs_x_odps['odps_link'] = str(odps_contract.id)
   >>> odcs_contract.save(update_fields=['hub_contract_json'])

   >>> # Restore ODPS → ODCS link
   >>> odps_x_odps['odcs_link'] = str(odcs_contract.id)
   >>> odps_contract.save(update_fields=['hub_contract_json'])
   ```

3. **Re-run Validation**:
   ```bash
   python manage.py validate_migration --contract-ids <uuid>
   ```

#### Issue 5: Migration Performance Issues

**Symptoms:**
- Migration takes too long
- Timeout errors
- Database connection issues

**Solutions:**

1. **Reduce Batch Size**:
   ```bash
   python manage.py migrate_contracts_to_odps \
       --batch-size 10  # Reduce from default 100
   ```

2. **Migrate by Tenant**:
   ```bash
   # Migrate one tenant at a time
   python manage.py migrate_contracts_to_odps \
       --tenant-id <tenant-uuid> \
       --batch-size 50
   ```

3. **Check Database Performance**:
   - Monitor database connections
   - Check for locks
   - Review slow queries

4. **Use Smaller Batches**:
   - Process contracts in smaller batches
   - Add delays between batches if needed

#### Issue 6: Rollback Fails

**Symptoms:**
```
Rollback failed: Contract not found
```

**Causes:**
- ODPS contract already deleted
- Contract ID mismatch
- Database state inconsistent

**Solutions:**

1. **Check Contract Existence**:
   ```bash
   python manage.py shell
   >>> from hub.apps.contracts.models import Contract
   >>> try:
   ...     contract = Contract.objects.get(id='<uuid>')
   ...     print(f"Contract exists: {contract.original_spec_type}")
   ... except Contract.DoesNotExist:
   ...     print("Contract not found")
   ```

2. **Manual Cleanup** (if needed):
   ```bash
   >>> # Remove links manually
   >>> odcs_contract.hub_contract_json['extensions']['x_odps'].pop('odps_link', None)
   >>> odcs_contract.save(update_fields=['hub_contract_json'])
   ```

3. **Verify State**:
   ```bash
   python manage.py validate_migration --contract-ids <uuid>
   ```

### Getting Help

If you encounter issues not covered here:

1. **Check Logs**:
   ```bash
   docker compose -f docker-compose.dev.yml logs api-service | grep -i migration
   ```

2. **Review Validation Report**:
   - Check validation report for detailed error messages
   - Review statistics for patterns

3. **Contact Support**:
   - Provide migration command used
   - Include validation report
   - Share relevant logs
   - Describe steps to reproduce

---

## Best Practices

### Pre-Migration

1. **Always Test First**: Run migration in test/staging environment
2. **Backup Database**: Create full backup before migration
3. **Start Small**: Migrate one contract first, then small batches
4. **Use Dry Run**: Always use `--dry-run` first
5. **Validate Prerequisites**: Check contract eligibility before migration

### During Migration

1. **Monitor Progress**: Watch migration output for errors
2. **Use Validation**: Always use `--validate` flag
3. **Save Reports**: Save validation reports for audit
4. **Batch Appropriately**: Use appropriate batch sizes
5. **Tenant Isolation**: Migrate by tenant when possible

### Post-Migration

1. **Validate Results**: Always run validation after migration
2. **Review Reports**: Thoroughly review validation reports
3. **Test Functionality**: Verify ODPS features work correctly
4. **Monitor Logs**: Check for errors or warnings
5. **Document Changes**: Document what was migrated

### Rollback Planning

1. **Plan Before Migrating**: Understand rollback procedure
2. **Test Rollback**: Test rollback in staging first
3. **Keep Backups**: Maintain database backups
4. **Document State**: Document pre-migration state
5. **Have Rollback Ready**: Know rollback command before migrating

---

## Reference

### Command Reference

#### Migration Command

```bash
python manage.py migrate_contracts_to_odps [OPTIONS]

Options:
  --dry-run                    Run in dry-run mode (no changes)
  --contract-id UUID           Migrate specific contract
  --batch-size INT             Batch size (default: 100)
  --tenant-id UUID             Migrate for specific tenant
  --skip-linked                Skip contracts with existing ODPS links
  --target-odps-version STR    Target ODPS version (default: 4.1)
  --min-marketplace-fields INT Minimum marketplace fields (default: 1)
  --validate                   Run validation after migration
  --validation-report-path PATH Save validation report to file
```

#### Validation Command

```bash
python manage.py validate_migration [OPTIONS]

Options:
  --tenant-id UUID             Validate for specific tenant
  --contract-ids STR           Comma-separated contract IDs
  --report-path PATH           Save report to file
  --format [text|json]         Output format (default: text)
  --include-statistics         Include statistics (default: True)
```

#### Rollback Command

```bash
python manage.py rollback_odps_migration [OPTIONS]

Options:
  --dry-run                    Run in dry-run mode (no changes)
  --contract-id UUID           Rollback specific contract
  --batch-size INT             Batch size (default: 100)
  --tenant-id UUID             Rollback for specific tenant
  --skip-unlinked              Skip contracts without ODPS links
```

### Migration Flow Diagram

```
┌─────────────────┐
│  ODCS Contract  │
│  (with          │
│  marketplace)   │
└────────┬────────┘
         │
         │ migrate_contracts_to_odps
         │
         ▼
┌─────────────────┐
│  Generate ODPS  │
│  from HubContract│
└────────┬────────┘
         │
         │ create ODPS contract
         │
         ▼
┌─────────────────┐
│  ODPS Contract  │
│  (normalized)   │
└────────┬────────┘
         │
         │ link_odps_to_odcs
         │
         ▼
┌─────────────────┐
│  Bidirectional  │
│  Links Created  │
│  ODPS ↔ ODCS    │
└────────┬────────┘
         │
         │ validate_migration
         │
         ▼
┌─────────────────┐
│  Validation     │
│  Report         │
└─────────────────┘
```

### Related Documentation

- **Migration Script**: `hub/apps/contracts/management/commands/migrate_contracts_to_odps.py`
- **Validation Module**: `hub/apps/contracts/migration_validation.py`
- **Rollback Script**: `hub/apps/contracts/management/commands/rollback_odps_migration.py`
- **ODPS Generator**: `hub/apps/contracts/odps_generator.py`
- **Linking Validation**: `hub/apps/contracts/linking_validation.py`

### Support and Feedback

For questions, issues, or feedback:

1. Check this documentation first
2. Review validation reports
3. Check application logs
4. Contact the development team

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Maintained By**: Data Interoperability Hub Team






















