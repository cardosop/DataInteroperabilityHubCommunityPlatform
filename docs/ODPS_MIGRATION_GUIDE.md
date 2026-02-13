# ODPS Migration Guide

Complete engineering-grade guide for migrating ODPS and ODCS contracts in the Data Interoperability Hub.

**Last Updated**: 2026-01-26
**Version**: 1.0.0

## Table of Contents

1. [Overview](#overview)
2. [Migrating from ODCS-only to ODPS+ODCS](#migrating-from-odcs-only-to-odpsodcs)
3. [Migrating ODPS Versions](#migrating-odps-versions)
4. [Migrating ODCS Versions](#migrating-odcs-versions)
5. [Best Practices for Migration](#best-practices-for-migration)
6. [Common Migration Issues](#common-migration-issues)
7. [Migration Tools and Commands](#migration-tools-and-commands)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers three types of migrations:

1. **ODCS-only → ODPS+ODCS**: Migrating existing ODCS contracts to include ODPS products
2. **ODPS Version Migration**: Upgrading ODPS contracts from one version to another (e.g., 4.0 → 4.1)
3. **ODCS Version Migration**: Upgrading ODCS contracts from one version to another (e.g., 2.2.2 → 3.0.2)

### Migration Principles

- **Data Preservation**: All data is preserved during migration
- **Bidirectional Linking**: ODPS ↔ ODCS links maintained throughout
- **Validation**: Comprehensive validation ensures migration success
- **Rollback Support**: Rollback capabilities for all migration types
- **Incremental Migration**: Support for batch and incremental migrations

---

## Migrating from ODCS-only to ODPS+ODCS

This migration creates ODPS contracts from existing ODCS contracts, enabling marketplace features while preserving all technical contract data.

### When to Migrate

Migrate when you want to:
- Add marketplace capabilities to existing technical contracts
- Enable product catalog features
- Support data product lifecycle management
- Prepare for marketplace integrations

### Migration Process

The migration process is documented in detail in [ODCS_TO_ODPS_MIGRATION_GUIDE.md](ODCS_TO_ODPS_MIGRATION_GUIDE.md).

**Quick Summary:**

1. **Dry Run**: Always start with a dry run
2. **Validate Prerequisites**: Check contracts meet migration requirements
3. **Execute Migration**: Run migration command
4. **Validate Results**: Verify migration success
5. **Review Report**: Review validation report

### Migration Command

```bash
# Single contract migration
python manage.py migrate_contracts_to_odps \
    --contract-id <contract-uuid> \
    --validate \
    --validation-report-path /tmp/migration_report.json

# Batch migration (tenant-specific)
python manage.py migrate_contracts_to_odps \
    --tenant-id <tenant-uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate \
    --validation-report-path /tmp/migration_report.json
```

### What Gets Migrated

- **ODCS Contract**: Preserved as-is
- **HubContract**: All data preserved
- **ODPS Contract**: Generated from HubContract with marketplace focus
- **Bidirectional Links**: ODPS ↔ ODCS links established

### Rollback

```bash
python manage.py rollback_odps_migration \
    --contract-id <contract-uuid>
```

**See**: [ODCS_TO_ODPS_MIGRATION_GUIDE.md](ODCS_TO_ODPS_MIGRATION_GUIDE.md) for complete details.

---

## Migrating ODPS Versions

Migrating ODPS contracts from one version to another (e.g., 4.0 → 4.1).

### Supported ODPS Versions

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **4.1** | ✅ Current | `ODPSNormalizerV4_1` | Latest stable, recommended for new contracts |
| **4.0** | ✅ Supported | `ODPSNormalizerV4_0` | Previous stable, fully supported |
| **1.x** | ✅ Supported (Legacy) | `ODPSNormalizerV1_X` | Legacy versions, gracefully degrades newer features |

### Version Detection

ODPS versions are detected from the `version` field in the document:

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1"  // Version 4.1
}
```

### Migrating from ODPS 4.0 to 4.1

#### Key Differences

**ODPS 4.1 New Features:**
- **Product Strategy**: `product.productStrategy` (objectives, strategic alignment, KPIs)
- **Enhanced Payment Gateways**: Improved payment gateway support
- **Enhanced Marketplace**: Improved marketplace features

**ODPS 4.0 Limitations:**
- No `productStrategy` support
- Limited payment gateway features

#### Migration Steps

**Step 1: Export Current ODPS 4.0 Contract**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.0" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o contract_4.0.odps.json
```

**Step 2: Update Version and Schema**

```json
{
  "schema": "https://opendataproducts.org/schema/v4.1",  // Updated schema
  "version": "4.1",  // Updated version
  "product": {
    // ... existing product data ...
    "productStrategy": {  // New in 4.1 (optional)
      "objectives": [...],
      "strategicAlignment": "...",
      "productKPIs": [...]
    }
  }
}
```

**Step 3: Create New ODPS 4.1 Contract**

```bash
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "<updated-odps-4.1-content>",
    "original_format": "JSON",
    "resolve_external_refs": true
  }'
```

**Step 4: Link to Existing ODCS Contract**

If the ODCS contract should remain linked:

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odcs-contract-id}/link-odps/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odps_contract_id": "<new-odps-4.1-contract-id>"
  }'
```

**Step 5: Archive Old ODPS 4.0 Contract**

```bash
# Update old contract status to ARCHIVED
curl -X PATCH "https://api.example.com/api/v1/contracts/{old-odps-4.0-id}/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ARCHIVED"
  }'
```

#### Python SDK Example

```python
from datahub_interoperability import DataHubClient, Config

config = Config(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

async with DataHubClient(config) as client:
    # Step 1: Export ODPS 4.0 contract
    odps_40 = await client.contracts.export_odps(
        contract_id="odps-4.0-contract-id",
        format="json",
        version="4.0"
    )

    # Step 2: Update to 4.1
    odps_41_content = odps_40["content"]
    odps_41_content["schema"] = "https://opendataproducts.org/schema/v4.1"
    odps_41_content["version"] = "4.1"

    # Add productStrategy if needed (optional)
    if "productStrategy" not in odps_41_content.get("product", {}):
        odps_41_content["product"]["productStrategy"] = {
            "objectives": [],
            "strategicAlignment": "",
            "productKPIs": []
        }

    # Step 3: Create new ODPS 4.1 contract
    result = await client.contracts.create_odps(
        original_raw=json.dumps(odps_41_content),
        extract_odcs=False,  # Keep existing ODCS
        original_format="JSON"
    )

    # Step 4: Link to existing ODCS
    odcs_contract_id = odps_40.get("linked_odcs_id")
    if odcs_contract_id:
        await client.contracts.link_odps_to_odcs(
            odcs_id=odcs_contract_id,
            odps_id=result["odps_contract"]["id"]
        )
```

### Graceful Degradation

ODPS 4.0 contracts continue to work with ODPS 4.1 normalizer:

- **Missing `productStrategy`**: Silently skipped (not available in 4.0)
- **Missing payment gateway features**: Gracefully handled
- **All 4.0 features**: Fully supported

### Migration Validation

After migration, validate the new contract:

```bash
python manage.py validate_migration \
    --contract-ids <new-odps-4.1-contract-id> \
    --format json \
    --report-path /tmp/validation_report.json
```

---

## Migrating ODCS Versions

Migrating ODCS contracts from one version to another (e.g., 2.2.2 → 3.0.2).

### Supported ODCS Versions

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **3.0.2** | ✅ Current | `ODCSNormalizerV3_0_2` | Latest stable, recommended for new contracts |
| **3.0.1** | ✅ Supported | `ODCSNormalizerV3_0_1` | Previous stable, fully supported |
| **3.0.0** | ✅ Supported | `ODCSNormalizerV3_0_0` | Initial 3.x release, fully supported |
| **2.2.2** | ✅ Supported (Legacy) | `ODCSNormalizerV2_2_2` | Legacy version, gracefully degrades 3.x features |

**See**: [ODCS_VERSION_SUPPORT.md](ODCS_VERSION_SUPPORT.md) for complete version details.

### Migrating from ODCS 2.2.2 to 3.0.2

#### Key Differences

**ODCS 3.0.2 New Features:**
- Enhanced marketplace features
- Enhanced lifecycle features
- Improved schema support
- Enhanced quality rules and compliance features

**ODCS 2.2.2 Limitations:**
- Limited marketplace features
- Limited lifecycle features
- Older schema format

#### Migration Steps

**Step 1: Export Current ODCS 2.2.2 Contract**

```bash
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odcs&version=2.2.2" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o contract_2.2.2.odcs.json
```

**Step 2: Update apiVersion**

```yaml
# Before (ODCS 2.2.2)
apiVersion: odcs.io/v2.2.2
kind: DataContract
id: my-contract
# ... rest of contract ...

# After (ODCS 3.0.2)
apiVersion: odcs.io/v3.0.2  # Updated version
kind: DataContract
id: my-contract
# ... rest of contract ...
```

**Step 3: Update Schema Format (if needed)**

ODCS 3.0.2 uses a different schema format:

```yaml
# ODCS 2.2.2 format
schema:
  type: object
  properties:
    field1:
      type: string

# ODCS 3.0.2 format
schema:
  fields:
    - name: field1
      type: string
      nullable: false
```

**Step 4: Create New ODCS 3.0.2 Contract**

```bash
curl -X POST https://api.example.com/api/v1/contracts/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "original_raw": "<updated-odcs-3.0.2-content>",
    "original_format": "JSON",
    "original_spec_type": "ODCS"
  }'
```

**Step 5: Link to Existing ODPS Contract (if exists)**

```bash
curl -X POST "https://api.example.com/api/v1/contracts/{odps-contract-id}/link-odcs/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "odcs_contract_id": "<new-odcs-3.0.2-contract-id>"
  }'
```

**Step 6: Archive Old ODCS 2.2.2 Contract**

```bash
curl -X PATCH "https://api.example.com/api/v1/contracts/{old-odcs-2.2.2-id}/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ARCHIVED"
  }'
```

#### Python SDK Example

```python
from hub.apps.contracts.services import ContractService

contract_service = ContractService(
    tenant_id=tenant_id,
    user_id=user_id
)

# Step 1: Export ODCS 2.2.2 contract
odcs_222_contract = contract_service.get_contract(
    contract_id="odcs-2.2.2-contract-id",
    tenant_id=tenant_id
)

# Step 2: Parse and update version
import json
odcs_222_content = json.loads(odcs_222_contract.original_raw)
odcs_222_content["apiVersion"] = "odcs.io/v3.0.2"

# Step 3: Update schema format if needed
# (Convert from 2.2.2 format to 3.0.2 format)

# Step 4: Create new ODCS 3.0.2 contract
odcs_302_contract = contract_service.create_contract(
    original_raw=json.dumps(odcs_222_content),
    original_format="JSON",
    original_spec_type="ODCS"
)

# Step 5: Link to existing ODPS if exists
odps_contract_id = odcs_222_contract.hub_contract_json.get(
    "extensions", {}
).get("x_odps", {}).get("odps_link")

if odps_contract_id:
    await client.contracts.link_odps_to_odcs(
        odcs_id=str(odcs_302_contract.id),
        odps_id=odps_contract_id
    )
```

### Graceful Degradation

ODCS 2.2.2 contracts continue to work with ODCS 3.0.2 normalizer:

- **Missing 3.x features**: Gracefully handled
- **All 2.2.2 features**: Fully supported
- **Backward compatibility**: Maintained

### Migration Validation

After migration, validate the new contract:

```bash
python manage.py validate_migration \
    --contract-ids <new-odcs-3.0.2-contract-id> \
    --format json \
    --report-path /tmp/validation_report.json
```

---

## Best Practices for Migration

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
3. **Test Functionality**: Verify features work correctly
4. **Monitor Logs**: Check for errors or warnings
5. **Document Changes**: Document what was migrated

### Version Migration Specific

1. **Review Version Differences**: Understand what changed between versions
2. **Test New Features**: Verify new features work correctly
3. **Update Documentation**: Update any documentation referencing versions
4. **Plan Rollback**: Understand rollback procedure before migrating
5. **Incremental Migration**: Migrate versions incrementally when possible

---

## Common Migration Issues

### Issue 1: Contract Not Eligible for Migration

**Symptoms:**
```
Contract <uuid> not found or not eligible
```

**Causes:**
- Contract type mismatch
- Contract lacks required data
- Contract already migrated

**Solutions:**
1. Verify contract type matches migration type
2. Check contract has required fields
3. Check if contract already has links

### Issue 2: Version Mismatch Errors

**Symptoms:**
```
Version mismatch: Expected 4.1, got 4.0
```

**Solutions:**
1. Update contract version field
2. Update schema URL
3. Verify version format matches expected format

### Issue 3: Data Loss During Migration

**Symptoms:**
```
Validation completed with X error(s)
Data loss detected in HubContract comparison
```

**Solutions:**
1. Review validation report for missing sections
2. Verify HubContract structure is complete
3. Check normalization status
4. Consider rolling back if critical data loss

### Issue 4: Broken Links After Migration

**Symptoms:**
```
Link validation failed: ODPS contract does not link back to ODCS contract
```

**Solutions:**
1. Verify links exist in both contracts
2. Check tenant matches
3. Manually restore links if needed
4. Re-run validation

### Issue 5: Schema Format Mismatch

**Symptoms:**
```
Schema validation failed: Invalid schema format
```

**Solutions:**
1. Convert schema format to target version
2. Review version-specific schema documentation
3. Use schema conversion tools if available

---

## Migration Tools and Commands

### ODCS to ODPS Migration

```bash
# Single contract
python manage.py migrate_contracts_to_odps \
    --contract-id <uuid> \
    --validate

# Batch migration
python manage.py migrate_contracts_to_odps \
    --tenant-id <uuid> \
    --batch-size 100 \
    --skip-linked \
    --validate

# Rollback
python manage.py rollback_odps_migration \
    --contract-id <uuid>
```

### Validation

```bash
# Validate migration
python manage.py validate_migration \
    --contract-ids <id1>,<id2> \
    --format json \
    --report-path /tmp/report.json
```

### Export/Import

```bash
# Export contract
curl -X GET "https://api.example.com/api/v1/contracts/{id}/export/?format=odps&version=4.1" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Import contract
curl -X POST https://api.example.com/api/v1/contracts/products/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"original_raw": "...", "original_format": "JSON"}'
```

---

## Troubleshooting

### Migration Fails with Validation Error

**Diagnosis:**
```bash
# Check contract structure
python manage.py shell
>>> from hub.apps.contracts.models import Contract
>>> contract = Contract.objects.get(id='<uuid>')
>>> print(contract.hub_contract_json)
```

**Solutions:**
1. Verify contract structure is valid
2. Check required fields are present
3. Review validation errors
4. Fix contract structure and retry

### Migration Performance Issues

**Symptoms:**
- Migration takes too long
- Timeout errors
- Database connection issues

**Solutions:**
1. Reduce batch size
2. Migrate by tenant
3. Check database performance
4. Use smaller batches

### Rollback Fails

**Symptoms:**
```
Rollback failed: Contract not found
```

**Solutions:**
1. Check contract existence
2. Verify contract IDs match
3. Manual cleanup if needed
4. Review database state

---

## Additional Resources

- [ODCS to ODPS Migration Guide](ODCS_TO_ODPS_MIGRATION_GUIDE.md) - Detailed ODCS→ODPS migration guide
- [ODCS Version Support](ODCS_VERSION_SUPPORT.md) - Complete ODCS version documentation
- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Creation Flows](ODPS_CREATION_FLOWS.md) - Creation flow documentation
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) - Marketplace integration architecture
- [API Reference](API_REFERENCE.md) - Complete API documentation

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-26
**Maintained By**: Data Interoperability Hub Team
