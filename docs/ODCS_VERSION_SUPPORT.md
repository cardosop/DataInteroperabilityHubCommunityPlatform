# ODCS Version Support

Complete guide for Open Data Contract Standard (ODCS) version support in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [Supported Versions](#supported-versions)
3. [Version-Specific Features](#version-specific-features)
4. [Graceful Degradation](#graceful-degradation)
5. [Version Detection](#version-detection)
6. [Normalization Behavior](#normalization-behavior)
7. [Migration Guidance](#migration-guidance)
8. [Best Practices](#best-practices)

---

## Overview

The Data Interoperability Hub supports multiple versions of the Open Data Contract Standard (ODCS) to ensure backward compatibility and smooth migration paths. Each version is handled by a dedicated normalizer that understands version-specific features and gracefully handles missing features from newer versions.

### Key Principles

- **Backward Compatibility**: Older ODCS versions continue to be supported
- **Graceful Degradation**: Missing features from newer versions are handled without errors
- **Version-Specific Normalizers**: Each version has a dedicated normalizer for optimal handling
- **Consistent Output**: All versions normalize to the same HubContract format

---

## Supported Versions

The following ODCS versions are fully supported:

| Version | Status | Normalizer | Notes |
|---------|--------|------------|-------|
| **3.0.2** | ✅ Current (Baseline) | `ODCSNormalizerV3_0_2` | Latest stable version, recommended for new contracts |
| **3.0.1** | ✅ Supported | `ODCSNormalizerV3_0_1` | Previous stable version, fully supported |
| **3.0.0** | ✅ Supported | `ODCSNormalizerV3_0_0` | Initial 3.x release, fully supported |
| **3.0.0-preview** | ✅ Supported | `ODCSNormalizerV3_0_0_Preview` | Preview version, gracefully handles incomplete features |
| **2.2.2** | ✅ Supported (Legacy) | `ODCSNormalizerV2_2_2` | Legacy version, gracefully degrades 3.x features |

### Version Detection

ODCS versions are detected from the `apiVersion` field in the contract:

```yaml
apiVersion: odcs.io/v3.0.2  # Version 3.0.2
apiVersion: odcs.io/v3.0.1  # Version 3.0.1
apiVersion: odcs.io/v3.0.0  # Version 3.0.0
apiVersion: odcs.io/v3.0.0-preview  # Version 3.0.0-preview
apiVersion: odcs.io/v2.2.2  # Version 2.2.2
```

---

## Version-Specific Features

### ODCS 3.0.2 (Current/Baseline)

**Status**: Current stable version, recommended for new contracts

**Features**:
- Full support for all ODCS 3.x features
- Enhanced marketplace features
- Enhanced lifecycle features
- Complete schema support
- All quality rules and compliance features

**Normalizer**: `ODCSNormalizerV3_0_2`

**Example**:
```yaml
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.1

**Status**: Fully supported, previous stable version

**Features**:
- Full support for ODCS 3.0.1 features
- Graceful degradation for 3.0.2+ features (if present, they are ignored)
- All core ODCS 3.x functionality

**Normalizer**: `ODCSNormalizerV3_0_1`

**Graceful Degradation**:
- If 3.0.2-specific features are present, they are logged but not processed
- Normalization continues with available 3.0.1 features
- No errors are raised for missing 3.0.2 features

**Example**:
```yaml
apiVersion: odcs.io/v3.0.1
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.0

**Status**: Fully supported, initial 3.x release

**Features**:
- Full support for ODCS 3.0.0 features
- Graceful degradation for 3.0.1+ and 3.0.2+ features
- Core ODCS 3.x functionality

**Normalizer**: `ODCSNormalizerV3_0_0`

**Graceful Degradation**:
- If 3.0.1+ or 3.0.2+ features are present, they are logged but not processed
- Normalization continues with available 3.0.0 features
- No errors are raised for missing newer features

**Example**:
```yaml
apiVersion: odcs.io/v3.0.0
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 3.0.0-preview

**Status**: Supported, preview version

**Features**:
- Support for ODCS 3.0.0-preview features
- Graceful handling of incomplete or experimental features
- May have missing optional fields compared to stable versions

**Normalizer**: `ODCSNormalizerV3_0_0_Preview`

**Special Considerations**:
- Preview versions may have incomplete feature sets
- Experimental features may change
- Missing optional fields are handled gracefully
- Warnings may be generated for incomplete contracts

**Example**:
```yaml
apiVersion: odcs.io/v3.0.0-preview
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

### ODCS 2.2.2 (Legacy)

**Status**: Supported for backward compatibility

**Features**:
- Full support for ODCS 2.2.2 features
- Graceful degradation for all 3.x features:
  - Enhanced marketplace features (limited support)
  - Enhanced lifecycle features (limited support)
  - Other 3.x-specific features

**Normalizer**: `ODCSNormalizerV2_2_2`

**Graceful Degradation**:
- 3.x-specific features are not processed
- Core 2.2.2 features are normalized correctly
- No errors are raised for missing 3.x features
- Contracts normalize successfully to HubContract format

**Example**:
```yaml
apiVersion: odcs.io/v2.2.2
kind: DataContract
id: my-contract
name: My Contract
version: 1.0.0
schema:
  fields:
    - name: id
      type: string
      nullable: false
```

---

## Graceful Degradation

The normalization system implements graceful degradation to ensure that older ODCS versions can be normalized successfully even when they lack features present in newer versions.

### How It Works

1. **Version Detection**: The system detects the ODCS version from the `apiVersion` field
2. **Normalizer Selection**: A version-specific normalizer is selected
3. **Feature Mapping**: Only features available in that version are processed
4. **Missing Features**: Features from newer versions are ignored (not errors)
5. **Consistent Output**: All versions produce valid HubContract output

### Degradation Strategy by Version

#### ODCS 3.0.1 → 3.0.2 Features

- **Behavior**: 3.0.2-specific features are logged but not processed
- **Result**: Normalization succeeds with available 3.0.1 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`

#### ODCS 3.0.0 → 3.0.1+/3.0.2+ Features

- **Behavior**: 3.0.1+ and 3.0.2+ features are logged but not processed
- **Result**: Normalization succeeds with available 3.0.0 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`

#### ODCS 2.2.2 → 3.x Features

- **Behavior**: All 3.x-specific features are gracefully ignored
- **Result**: Normalization succeeds with available 2.2.2 features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
- **Note**: Enhanced marketplace and lifecycle features have limited support

#### ODCS 3.0.0-preview → Missing Features

- **Behavior**: Missing optional features are handled gracefully
- **Result**: Normalization succeeds with available preview features
- **Status**: `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
- **Note**: Warnings may be generated for incomplete contracts

### Example: Graceful Degradation in Action

**ODCS 3.0.1 Contract with 3.0.2 Feature**:
```yaml
apiVersion: odcs.io/v3.0.1
kind: DataContract
id: my-contract
name: My Contract
# 3.0.2-specific feature (will be ignored)
newFeature: "value"
schema:
  fields:
    - name: id
      type: string
```

**Result**:
- ✅ Normalization succeeds
- ⚠️ Warning logged: "3.0.2-specific feature 'newFeature' ignored in 3.0.1 contract"
- ✅ HubContract created with available 3.0.1 features
- ✅ Status: `NORMALIZED_WITH_WARNINGS`

---

## Version Detection

### Automatic Detection

The system automatically detects ODCS version from the contract:

```python
from hub.apps.contracts.spec_detection import detect_spec_type

contract_data = {
    "apiVersion": "odcs.io/v3.0.2",
    "kind": "DataContract",
    # ... rest of contract
}

spec_type, spec_version = detect_spec_type(contract_data)
# spec_type = "ODCS"
# spec_version = "3.0.2"
```

### Manual Version Specification

You can also specify the version explicitly:

```python
from hub.apps.contracts.normalization import normalize_contract

result = normalize_contract(
    raw_contract=contract_json_string,
    format="json",
    spec_type="ODCS"  # Optional, auto-detected if not provided
)
```

---

## Normalization Behavior

### Normalization Flow

1. **Version Detection**: Extract version from `apiVersion` field
2. **Normalizer Selection**: Select version-specific normalizer
3. **Contract Validation**: Validate contract structure
4. **Feature Mapping**: Map version-specific features to HubContract
5. **Graceful Degradation**: Handle missing features gracefully
6. **Output Generation**: Produce normalized HubContract

### Normalization Status

All versions can produce the following statuses:

- **`NORMALIZED_OK`**: Successfully normalized with no warnings
- **`NORMALIZED_WITH_WARNINGS`**: Normalized successfully but with warnings (e.g., missing optional features)
- **`NORMALIZATION_FAILED`**: Normalization failed (e.g., invalid contract structure)

### Consistent Output Format

All ODCS versions normalize to the same HubContract format:

```json
{
  "hub_contract_version": "1.0.0",
  "id": "my-contract",
  "info": {
    "name": "My Contract",
    "version": "1.0.0"
  },
  "schema": {
    "fields": [
      {
        "name": "id",
        "data_type": "string",
        "nullable": false
      }
    ]
  },
  "normalization": {
    "original_spec_type": "ODCS",
    "original_spec_version": "3.0.2"
  }
}
```

---

## Migration Guidance

### Upgrading from Older Versions

#### From ODCS 2.2.2 to 3.0.0+

1. **Update `apiVersion`**: Change from `odcs.io/v2.2.2` to `odcs.io/v3.0.2`
2. **Review Features**: Check for 3.x-specific features you want to use
3. **Test Normalization**: Ensure normalization works correctly
4. **Update Documentation**: Update any documentation referencing version

#### From ODCS 3.0.0 to 3.0.2

1. **Update `apiVersion`**: Change from `odcs.io/v3.0.0` to `odcs.io/v3.0.2`
2. **Review New Features**: Check for 3.0.2-specific features
3. **Test Normalization**: Ensure all features work correctly

#### From ODCS 3.0.0-preview to 3.0.2

1. **Update `apiVersion`**: Change from `odcs.io/v3.0.0-preview` to `odcs.io/v3.0.2`
2. **Review Experimental Features**: Some preview features may have changed
3. **Test Thoroughly**: Preview versions may have had experimental features
4. **Update Contract**: Ensure contract matches stable 3.0.2 specification

### Backward Compatibility

- **Older versions remain supported**: No need to upgrade immediately
- **Gradual migration**: Migrate at your own pace
- **No breaking changes**: Older versions continue to work

---

## Best Practices

### Version Selection

1. **New Contracts**: Use ODCS 3.0.2 (latest stable)
2. **Existing Contracts**: Keep current version unless you need new features
3. **Preview Versions**: Avoid in production; use for testing only

### Contract Structure

1. **Always specify `apiVersion`**: Required for version detection
2. **Include `kind` field**: Required for ODCS contracts
3. **Version consistency**: Ensure `apiVersion` matches contract structure

### Normalization

1. **Check normalization status**: Always check `NORMALIZED_OK` or `NORMALIZED_WITH_WARNINGS`
2. **Review warnings**: Warnings indicate missing optional features
3. **Handle errors**: `NORMALIZATION_FAILED` indicates contract issues

### Testing

1. **Test with your version**: Ensure your ODCS version normalizes correctly
2. **Test backward compatibility**: Older versions should still work
3. **Test graceful degradation**: Verify missing features don't cause errors

---

## Version Support Matrix

| Feature | 3.0.2 | 3.0.1 | 3.0.0 | 3.0.0-preview | 2.2.2 |
|---------|-------|-------|-------|---------------|-------|
| Core Schema | ✅ | ✅ | ✅ | ✅ | ✅ |
| Info Section | ✅ | ✅ | ✅ | ✅ | ✅ |
| Quality Rules | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Lifecycle | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Marketplace | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Compliance | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| Enhanced Marketplace (3.0.2+) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Enhanced Lifecycle (3.0.2+) | ✅ | ❌ | ❌ | ❌ | ❌ |

**Legend**:
- ✅ Fully supported
- ⚠️ Limited support or graceful degradation
- ❌ Not available (gracefully ignored)

---

## References

- **ODCS Specification**: https://bitol-io.github.io/open-data-contract-standard/
- **ODCS 3.0.2**: https://bitol-io.github.io/open-data-contract-standard/v3.0.2/
- **Normalization Guide**: See [DEVELOPER_GUIDE_NORMALIZATION.md](deprecated-doc/feature-docs/DEVELOPER_GUIDE_NORMALIZATION.md)
- **Backward Compatibility Tests**: See `hub/apps/contracts/tests/test_odcs_backward_compatibility.py`

---

## Support

For questions or issues with ODCS version support:

1. **Check this documentation**: Review version-specific features and graceful degradation
2. **Review test suite**: See backward compatibility tests for examples
3. **Check normalization status**: Review warnings and errors in normalization results
4. **Contact support**: Reach out to the development team for assistance

---

**Last Updated**: 2024-12-10
**Maintained By**: Data Interoperability Hub Team

