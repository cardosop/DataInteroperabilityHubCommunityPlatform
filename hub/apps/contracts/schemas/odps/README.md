# ODPS JSON Schema Files

This directory contains JSON Schema files for validating Open Data Product Standard (ODPS) documents.

## Directory Structure

```
schemas/odps/
├── v4.1/
│   └── odps-schema.json    # ODPS 4.1 schema
├── v4.0/
│   └── odps-schema.json    # ODPS 4.0 schema
├── v3.x/
│   └── odps-schema.json    # ODPS 3.x schema (latest 3.x version)
├── v2.x/
│   └── odps-schema.json    # ODPS 2.x schema (latest 2.x version)
└── v1.x/
    └── odps-schema.json    # ODPS 1.x schema (latest 1.x version)
```

## Schema Files

Each version directory contains an `odps-schema.json` file that validates ODPS documents of that version.

### Current Status

The schema files in this repository are **initial implementations** that provide:
- Valid JSON structure
- Valid JSON Schema (Draft 2020-12 compatible)
- Basic ODPS structure validation
- Version-specific patterns and requirements

### Obtaining Official Schemas

**Note**: These schema files should be replaced with official ODPS JSON Schema files when available from the official ODPS specification repository.

To obtain official ODPS schemas:

1. **Check Official ODPS Repository**:
   - Visit the official Open Data Product Standard repository
   - Look for schema files in the `schemas/` or `schema/` directory
   - Download the appropriate version-specific schema files

2. **Schema File Locations**:
   - Official schemas may be available at: `https://opendataproducts.org/schema/v{version}/odps-schema.json`
   - Or in the official GitHub repository under the schemas directory

3. **Replacing Schema Files**:
   - Replace the placeholder schema files with official ones
   - Ensure the filename remains `odps-schema.json`
   - Verify the schema files are valid JSON and valid JSON Schema
   - Run tests: `python manage.py test apps.contracts.tests.test_odps_schema_files`

## Validation

All schema files are validated to ensure:
- ✅ Valid JSON syntax
- ✅ Valid JSON Schema structure
- ✅ Can validate sample ODPS documents
- ✅ Version-specific identifiers present

Run validation tests:
```bash
python manage.py test apps.contracts.tests.test_odps_schema_files
```

## Usage

Schema files are loaded by the ODPS parser and validator to validate incoming ODPS documents. See `hub/apps/contracts/odps_parser.py` (when implemented) for usage.

## Maintenance

When official ODPS schemas are updated:
1. Download the new schema file
2. Replace the corresponding `odps-schema.json` file
3. Run validation tests to ensure compatibility
4. Update this README with the source and version information

