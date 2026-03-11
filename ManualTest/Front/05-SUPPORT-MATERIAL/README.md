# Support Material for Manual Testing

**Version**: 1.1.0  
**Last Updated**: 2026-03-01

---

## Quick Reference

| Material | Location | Purpose |
|----------|----------|---------|
| [test-users.md](test-users.md) | This directory | Test user credentials matrix |
| [contracts/](contracts/) | `05-SUPPORT-MATERIAL/contracts/` | ODCS/ODPS contract samples (JSON, YAML) |
| [data/](data/) | `05-SUPPORT-MATERIAL/data/` | Sample CSV/JSON for file upload and schema inference |

---

## Contents

### In This Directory (ManualTest)

| Material | Description |
|----------|-------------|
| [test-users.md](test-users.md) | Test user credentials, setup commands |
| [contracts/](contracts/) | **ODCS** (minimal, with quality rules, with marketplace, YAML) and **ODPS** (embedded ODCS, contractURL-only). Includes invalid samples for error testing. |
| [data/](data/) | Sample CSV and JSON files for asset creation, schema inference, DQ flows |

### In Repo (tests/fixtures)

| Material | Path | Use When |
|----------|------|----------|
| ODPS valid samples | `tests/fixtures/odps/v4.1/valid/` | Need ODPS 4.1 without embedded ODCS |
| ODPS marketplace | `tests/fixtures/odps/v4.1/marketplace/` | Need marketplace-only ODPS |
| ODPS with $ref | `tests/fixtures/odps/v4.1/with_refs/` | Need local $ref samples |
| Quality rules YAML | `tests/fixtures/odps/v4.1/with_refs/quality-rules.yaml` | ODPS with $ref to quality rules |
| Marketplace CKAN | `tests/fixtures/marketplace/ckan/` | CKAN integration tests |

---

## Usage by Journey

| Journey | Support Material |
|---------|------------------|
| JOURNEY-DPO-001 (Data-First) | `data/sample-upload.csv`, `contracts/odcs-minimal.json`, `contracts/odps-with-embedded-odcs.json` |
| JOURNEY-DPO-005 (Configure Contracts) | `contracts/odps-with-embedded-odcs.json`, `odcs-minimal.json`, `odcs-with-quality-rules.json`, `odcs-minimal.yaml`, `odps-invalid-missing-schema.json` |
| JOURNEY-DPO-007 (AI Schema Matching) | `data/sample-upload.csv` |
| JOURNEY-DPO-015 (Product-First) | `contracts/odps-with-embedded-odcs.json` |
| JOURNEY-DPO-016 (Link ODPS↔ODCS) | `contracts/odps-with-contracturl-only.json` (ODPS with contractURL only; create ODCS first, then link via UI) |
| JOURNEY-DE-001 (Contract-First) | `contracts/odps-with-embedded-odcs.json`, `data/sample-upload.csv` |
| JOURNEY-DE-014 (Create ODPS via API) | `contracts/odps-with-embedded-odcs.json` |
| Error testing | `contracts/odcs-invalid-missing-required.json`, `contracts/odps-invalid-missing-schema.json` |

**Optional** (YAML ODPS, $ref samples, marketplace variants): see `tests/fixtures/odps/` in repo root.

---

## Setup Before Testing

```bash
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles
docker exec hub-test-api python hub/manage.py ensure_e2e_subscription
```
