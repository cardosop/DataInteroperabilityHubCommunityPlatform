# Contract Samples for Manual Testing

**Purpose**: Use these files when testing contract intake, validation, and ODPS flows.

---

## ODCS Contracts (Open Data Contract Standard)

| File | Use Case | Format | Notes |
|------|----------|--------|-------|
| `odcs-minimal.json` | Basic contract intake | JSON | Minimal valid ODCS. Use for JOURNEY-DPO-005 (Configure Data Contracts). |
| `odcs-minimal.yaml` | YAML intake validation | YAML | Same as minimal but YAML. Tests `original_format: YAML`. |
| `odcs-with-quality-rules.json` | Contract with DQ rules | JSON | Includes quality.rules. Use for DQ validation flows. |
| `odcs-with-marketplace.json` | Contract with marketplace | JSON | Includes marketplace.x_odps. Use for publish flows. |
| `odcs-invalid-missing-required.json` | Error handling (ODCS) | JSON | **Invalid** ODCS - missing schema.fields. Use for API tests. |
| `odps-invalid-missing-schema.json` | Error handling (ODPS) | JSON | **Invalid** ODPS - product.contract.spec has no schema.fields. Expect 400 Bad Request. |

---

## ODPS Contracts (Open Data Product Standard)

| File | Use Case | Notes |
|------|----------|-------|
| `odps-with-embedded-odcs.json` | Product-first flow | Has `product.contract.spec` with inline ODCS. Use for JOURNEY-DPO-015. |
| `odps-with-contracturl-only.json` | Link ODPS↔ODCS (JOURNEY-DPO-016) | Has `contractURL` only (no embedded ODCS). Create ODCS first, then upload and link via UI. |

---

## How to Use

### Contract Creation (JOURNEY-DPO-005)

1. Log in as Data Product Owner (e2e_test@example.com).
2. Navigate to **Contracts** → **Create Contract**.
3. Paste content from `odcs-minimal.json` or upload the file.
4. Select format: **JSON** (or **YAML** for `odcs-minimal.yaml`).
5. Submit. **Expected**: Contract created, normalization status NORMALIZED_OK.

### Product-First Flow (JOURNEY-DPO-015)

1. Navigate to **Contracts** → **Create ODPS Product**.
2. Upload `odps-with-embedded-odcs.json`.
3. **Expected**: ODPS and ODCS contracts created and linked.

### Link ODPS↔ODCS (JOURNEY-DPO-016)

1. Create ODCS contract first (via JOURNEY-DPO-005 or DPO-015).
2. Upload `odps-with-contracturl-only.json` to create ODPS contract.
3. Use **Link ODPS** button on ODCS contract detail to link ODPS ↔ ODCS.

### Error Scenario

1. Use `odps-invalid-missing-schema.json` (ODPS upload) or `odcs-invalid-missing-required.json` (API).
2. **Expected**: 400 Bad Request, validation error about missing schema/fields.

---

## Source References

- ODCS spec: Open Data Contract Standard v3.0.2
- ODPS spec: Open Data Products Schema v4.1
- Full examples: `examples/contracts/`, `tests/fixtures/odps/`
