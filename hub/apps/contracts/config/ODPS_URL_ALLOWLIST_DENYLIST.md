# ODPS URL Allowlist/Denylist Configuration

This document describes how to configure URL allowlist and denylist for ODPS $ref resolver security.

## Overview

The ODPS $ref resolver supports URL allowlist and denylist configuration to control which external URLs can be resolved when processing ODPS documents. This provides security by preventing resolution of URLs from untrusted sources.

## Configuration Hierarchy

Configuration is loaded in the following order (later sources override earlier ones):

1. **Default values** - Hardcoded defaults (empty lists)
2. **YAML configuration file** - `hub/apps/contracts/config/odps_refs.yaml`
3. **Environment variables** - Global overrides
4. **Per-tenant configuration** - Database overrides (highest precedence)

## Configuration Sources

### 1. YAML Configuration File

Edit `hub/apps/contracts/config/odps_refs.yaml`:

```yaml
url_allowlist:
  - "https://schemas.example.com"
  - "https://*.trusted.com"
url_denylist:
  - "http://*"
  - "https://*.malicious.com"
```

### 2. Environment Variables

Set global allowlist/denylist via environment variables:

```bash
# Comma-separated list of allowed URL patterns
export ODPS_URL_ALLOWLIST="https://schemas.example.com,https://*.trusted.com"

# Comma-separated list of denied URL patterns
export ODPS_URL_DENYLIST="http://*,https://*.malicious.com"
```

Environment variables are merged with YAML config (both are applied).

### 3. Per-Tenant Configuration

Per-tenant overrides are stored in the `TenantConfig.odps_refs_config` JSONField.

#### Database Schema

The `odps_refs_config` field is a JSONField with the following structure:

```json
{
  "url_allowlist": ["https://tenant-specific.com", "https://*.tenant-trusted.com"],
  "url_denylist": ["https://*.tenant-blocked.com"]
}
```

#### Setting Per-Tenant Configuration

**Via Django Admin:**
1. Navigate to Tenant Config in Django admin
2. Edit the tenant configuration
3. Set `odps_refs_config` field with JSON:
   ```json
   {"url_allowlist": ["https://tenant.com"], "url_denylist": []}
   ```

**Via API:**
```python
from hub.apps.tenants.models import TenantConfig

tenant_config = TenantConfig.objects.get(tenant=tenant)
tenant_config.odps_refs_config = {
    "url_allowlist": ["https://tenant.com"],
    "url_denylist": ["https://*.blocked.com"]
}
tenant_config.save()
```

**Via Management Command:**
```bash
python manage.py shell
>>> from hub.apps.tenants.models import Tenant, TenantConfig
>>> tenant = Tenant.objects.get(slug="example-tenant")
>>> config = tenant.config
>>> config.odps_refs_config = {"url_allowlist": ["https://tenant.com"]}
>>> config.save()
```

## URL Pattern Format

Patterns support the following formats:

### Exact URL Match
Matches the exact URL including path:
- `"https://schemas.example.com/schema.json"` - Matches only that exact URL

### Domain Wildcard
Matches any subdomain with any path:
- `"https://*.example.com"` - Matches `https://api.example.com`, `https://schemas.example.com`, etc.
- `"https://*.trusted.com"` - Matches any subdomain of trusted.com

### Host Wildcard (No Scheme)
Matches any scheme and any path:
- `"*.example.com"` - Matches `http://api.example.com`, `https://api.example.com`, etc.

### Full Wildcard
Matches any host with specified scheme:
- `"https://*"` - Matches any HTTPS URL
- `"http://*"` - Matches any HTTP URL (useful for denylist)

### Scheme + Host (No Path)
Matches any path on that host:
- `"https://example.com"` - Matches `https://example.com/any/path.json`

### Host Only
Matches any scheme and any path:
- `"example.com"` - Matches `http://example.com` or `https://example.com` with any path

## Precedence Rules

1. **Denylist takes precedence** - If a URL matches both allowlist and denylist, it's denied
2. **Empty allowlist allows all** - If allowlist is empty, all URLs are allowed (unless in denylist)
3. **Non-empty allowlist restricts** - If allowlist is not empty, URL must match at least one pattern
4. **Per-tenant overrides global** - Tenant-specific config completely replaces global config (not merged)

## Usage Examples

### Example 1: Allow Only Specific Domains

**YAML Config:**
```yaml
url_allowlist:
  - "https://schemas.example.com"
  - "https://*.trusted-domain.com"
url_denylist: []
```

**Result:**
- ✅ `https://schemas.example.com/schema.json` - Allowed
- ✅ `https://api.trusted-domain.com/schema.json` - Allowed
- ❌ `https://other.com/schema.json` - Denied

### Example 2: Deny HTTP, Allow HTTPS

**YAML Config:**
```yaml
url_allowlist: []
url_denylist:
  - "http://*"
```

**Result:**
- ✅ `https://example.com/schema.json` - Allowed (empty allowlist allows all)
- ❌ `http://example.com/schema.json` - Denied (matches denylist)

### Example 3: Per-Tenant Override

**Global Config (YAML):**
```yaml
url_allowlist:
  - "https://global.example.com"
url_denylist: []
```

**Tenant Config (Database):**
```json
{
  "url_allowlist": ["https://tenant-specific.com"],
  "url_denylist": ["https://*.blocked.com"]
}
```

**Result for that tenant:**
- ✅ `https://tenant-specific.com/schema.json` - Allowed
- ❌ `https://global.example.com/schema.json` - Denied (not in tenant allowlist)
- ❌ `https://api.blocked.com/schema.json` - Denied (in tenant denylist)

## Programmatic Usage

### Get Configuration

```python
from hub.apps.contracts.config.odps_refs_config import get_odps_refs_config

# Global config
config = get_odps_refs_config()
allowlist = config.url_allowlist
denylist = config.url_denylist

# With tenant config
tenant_config_dict = tenant.config.odps_refs_config or {}
config = get_odps_refs_config(tenant_config=tenant_config_dict)
```

### Check URL

```python
from hub.apps.contracts.config.odps_refs_config import is_url_allowed

# Global check
is_allowed = is_url_allowed("https://example.com/schema.json")

# With tenant config
tenant_config_dict = tenant.config.odps_refs_config or {}
is_allowed = is_url_allowed("https://example.com/schema.json", tenant_config=tenant_config_dict)
```

### Direct Config Object

```python
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig

# Global config
config = ODPSRefsConfig()

# With tenant config
tenant_config_dict = {"url_allowlist": ["https://tenant.com"]}
config = ODPSRefsConfig(tenant_config=tenant_config_dict)

# Check URL
is_allowed = config.is_url_allowed("https://example.com/schema.json")
```

## Security Best Practices

1. **Use denylist for broad blocks** - Deny HTTP, known malicious domains
2. **Use allowlist for restrictions** - When allowlist is set, only listed patterns are allowed
3. **Prefer HTTPS** - Deny HTTP in denylist: `["http://*"]`
4. **Use wildcards carefully** - `https://*` allows all HTTPS URLs (use only if needed)
5. **Per-tenant isolation** - Use per-tenant configs for tenant-specific security requirements
6. **Regular updates** - Keep allowlist/denylist updated as security requirements change

## Troubleshooting

### URL Not Allowed

1. Check if URL matches denylist patterns
2. Check if allowlist is empty (allows all) or non-empty (requires match)
3. Verify pattern format (exact match vs wildcard)
4. Check per-tenant overrides if applicable

### Configuration Not Applied

1. Verify YAML file syntax is correct
2. Check environment variables are set correctly
3. Verify per-tenant config JSON is valid
4. Check configuration precedence (tenant > env > YAML > defaults)

### Pattern Not Matching

1. Verify pattern format matches expected format
2. Check scheme matching (http vs https)
3. Verify wildcard placement (`*.example.com` not `*example.com`)
4. Test with exact URL first, then try wildcards

## Related Files

- Configuration module: `hub/apps/contracts/config/odps_refs_config.py`
- YAML config file: `hub/apps/contracts/config/odps_refs.yaml`
- Database model: `hub/apps/tenants/models.py` (TenantConfig.odps_refs_config)
- Tests: `hub/apps/contracts/tests/test_odps_url_allowlist_denylist.py`

