# ODPS $ref Resolver Configuration

This directory contains configuration files for the ODPS $ref resolver security settings.

## Configuration File

### `odps_refs.yaml`

The main configuration file for ODPS $ref resolver security settings.

**Location:** `hub/apps/contracts/config/odps_refs.yaml`

**Structure:**
```yaml
allowed_base_dirs:
  - "./contracts/refs"
  - "./odps-refs"
```

## Configuration Loading

Configuration is loaded in the following order (later sources override earlier ones):

1. **Default values** - Hardcoded defaults in `odps_refs_config.py`
2. **YAML file** - Values from `odps_refs.yaml` (if file exists and YAML library is available)
3. **Environment variables** - Override YAML values

## Environment Variables

### `ODPS_REFS_DIR`

Additional directory to add to the allowed base directories list.

**Usage:**
```bash
export ODPS_REFS_DIR="/custom/path/to/refs"
```

This directory will be appended to the `allowed_base_dirs` list from the YAML configuration.

**Example:**
- YAML config: `["./contracts/refs", "./odps-refs"]`
- Environment: `ODPS_REFS_DIR="/custom/refs"`
- Final allowed directories: `["./contracts/refs", "./odps-refs", "/custom/refs"]`

## Usage

### Basic Usage

```python
from hub.apps.contracts.config.odps_refs_config import get_odps_refs_config, get_allowed_base_dirs

# Get configuration instance
config = get_odps_refs_config()

# Get allowed base directories
allowed_dirs = config.allowed_base_dirs
# Returns: ['./contracts/refs', './odps-refs']

# Or use convenience function
dirs = get_allowed_base_dirs()
```

### Path Validation

```python
from pathlib import Path
from hub.apps.contracts.config.odps_refs_config import get_odps_refs_config

config = get_odps_refs_config()

# Check if a path is allowed
file_path = Path("./contracts/refs/schema.yaml")
is_allowed = config.is_path_allowed(file_path)
# Returns: True

# Path traversal attempt
malicious_path = Path("../../../etc/passwd")
is_allowed = config.is_path_allowed(malicious_path)
# Returns: False
```

### Custom Configuration File

```python
from pathlib import Path
from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig

# Load from custom location
custom_config = ODPSRefsConfig(config_file=Path("/path/to/custom/config.yaml"))
allowed_dirs = custom_config.allowed_base_dirs
```

## Security Features

### Directory Whitelist

Only files within whitelisted directories can be referenced via local $ref. This prevents path traversal attacks.

**How it works:**
1. All local $ref paths are resolved to absolute paths
2. Each path is checked against the list of allowed base directories
3. Only paths that are within (or subdirectories of) allowed directories are permitted

**Example:**
- Allowed: `./contracts/refs/schema.yaml` (within `./contracts/refs`)
- Allowed: `./contracts/refs/subdir/file.yaml` (subdirectory of allowed dir)
- Blocked: `../../../etc/passwd` (outside allowed directories)
- Blocked: `/absolute/path/outside.yaml` (not within any allowed directory)

### Path Traversal Prevention

The configuration automatically prevents path traversal attacks by:
- Resolving all paths to absolute paths
- Normalizing paths (resolving symlinks, removing `..`, etc.)
- Checking that resolved paths are within allowed directories

## Configuration File Format

The YAML configuration file supports the following fields:

### `allowed_base_dirs` (required)

List of directory paths that are allowed for local $ref resolution.

- Can be relative paths (relative to project root)
- Can be absolute paths
- Supports multiple directories
- Default: `["./contracts/refs", "./odps-refs"]`

**Example:**
```yaml
allowed_base_dirs:
  - "./contracts/refs"
  - "./odps-refs"
  - "/absolute/path/to/refs"
```

## Testing

See `hub/apps/contracts/tests/test_odps_refs_config.py` for comprehensive test coverage.

## Troubleshooting

### Configuration Not Loading

1. **Check file exists:** Ensure `odps_refs.yaml` exists in `hub/apps/contracts/config/`
2. **Check YAML library:** Ensure `pyyaml` is installed (`pip install pyyaml`)
3. **Check file permissions:** Ensure the file is readable
4. **Check logs:** Check application logs for configuration loading errors

### Path Validation Failing

1. **Check path format:** Ensure paths are relative to project root or absolute
2. **Check directory exists:** Allowed directories don't need to exist, but paths being validated must be within them
3. **Check symlinks:** Symlinks are resolved, so ensure the resolved path is within allowed directories

### Environment Variable Not Working

1. **Check variable name:** Must be exactly `ODPS_REFS_DIR`
2. **Check export:** Ensure variable is exported: `export ODPS_REFS_DIR="/path"`
3. **Check application restart:** Some applications require restart to pick up new environment variables

## Future Configuration Options

The configuration file structure supports future additions:

```yaml
# URL allowlist/denylist (for external $ref)
url_allowlist: []
url_denylist: []

# Size limits
max_ref_size: 1048576  # 1MB
max_total_size: 10485760  # 10MB

# Timeouts
timeout_per_ref: 5  # seconds
timeout_total: 30  # seconds
```

These options are defined in the YAML file but not yet implemented in the configuration loader.

