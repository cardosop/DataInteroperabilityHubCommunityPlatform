# Support Material for Manual Testing

**Version**: 1.0.0  
**Last Updated**: 2026-02-17

---

## Contents

| Material | Description | Path (from repo root) |
|----------|-------------|------------------------|
| [test-users.md](test-users.md) | Test user credentials matrix | This directory |
| ODPS valid samples | Valid ODPS 4.1 product documents | `tests/fixtures/odps/v4.1/valid/` |
| ODPS marketplace | Marketplace pricing, access, payment | `tests/fixtures/odps/v4.1/marketplace/` |
| Contract definition | Data contract YAML | `tests/fixtures/odps/v2.x/with_refs/contract-definition.yaml` |
| Quality rules | DQ quality rules YAML | `tests/fixtures/odps/v4.1/with_refs/quality-rules.yaml` |
| Marketplace CKAN | CKAN dataset/resource samples | `tests/fixtures/marketplace/ckan/` |

---

## Usage

- **Test users**: Use credentials from [test-users.md](test-users.md) when a script requires a specific persona.
- **ODPS**: Copy or reference sample JSON when testing ODPS product creation, linking, or export.
- **Contracts**: Use contract YAML for contract validation and ODCS flows.
- **Quality rules**: Use for data quality configuration tests.
