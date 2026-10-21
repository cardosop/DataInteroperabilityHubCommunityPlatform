# CLI Backward Compatibility Contract

**Status**: Authoritative — MUST be followed for all CLI changes.
**Phase**: 279.J.4
**Updated**: 2026-05-14

## Core rule

**Existing subcommand names, option flags, defaults, output formats, and
exit codes MUST NOT change.**  New subcommands are additive-only.

This contract ensures that scripts, CI pipelines, and operator runbooks
that depend on CLI behavior do not break across releases.

## Immutable surface

### Subcommand names
- `datahub <group> <action>` — the group and action names are stable.
- Adding a new action to an existing group is safe.
- Renaming or removing an existing action is a BREAKING CHANGE that
  requires a major version bump and a deprecation cycle.

### Option flags
- `--format json|table` is the universal output format flag.
- `--limit`, `--offset`, `--page-size` are stable pagination flags.
- Short-flag aliases (`-f` for `--format`) are stable once shipped.

### Defaults
- `--format` defaults to `table` for human readability.
- `--limit` defaults to values documented in command help text.
- Changing a default is a MINOR version bump (behavioral change,
  not a syntax break).

### Output formats
- `--format json` MUST produce valid JSON on stdout.
- `--format table` MUST produce human-readable columnar text.
- The JSON schema for a given command may ADD fields but MUST NOT
  remove or rename existing fields.

### Exit codes
| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error (ClickException) |
| 65 | Validation error (CLIValidationError) |
| 68 | Not found (CLINotFoundError) |
| 75 | Network/temporary error (CLINetworkError) |
| 77 | Auth error (CLIAuthError) |

Adding a new exit code for a new error class is safe. Changing the
meaning of an existing exit code is a BREAKING CHANGE.

## Additive-only policy

- ✅ Add a new `datahub <group> <action>` subcommand.
- ✅ Add a new `--option` flag to an existing command.
- ✅ Add a new field to an existing JSON output.
- ❌ Rename `datahub contracts` to `datahub odps`.
- ❌ Change `--format json` default to `--format table`.
- ❌ Remove the `--limit` flag.
- ❌ Change exit code 65 to mean something other than validation error.

## Verification

Before and after each Phase 1/5 change:

```bash
# Run existing CLI integration tests — zero regressions
pytest cli/tests/ -x --tb=short -k "not e2e"

# Verify help text for all command groups
for cmd in assets contracts datasets files jobs lineage mesh \
  virtualization tenants users compliance dq governance gdpr audit \
  billing observability webhooks health config marketplace \
  scheduled-ingestion scheduled-export transformation search semantic \
  baas ml phase232; do
  datahub $cmd --help > /dev/null || echo "FAIL: $cmd"
done
```

## Maintenance

- **Owner**: Developer Experience
- **Last reviewed**: 2026-05-14
- **Next review**: After every CLI command group addition (Phase 1/5 changes)
