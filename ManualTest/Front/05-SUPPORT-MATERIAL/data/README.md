# Sample Data Files for Manual Testing

**Purpose**: Use these files when testing asset creation, file upload, schema inference, and data-first flows.

---

## Files

| File | Columns | Use Case |
|------|---------|----------|
| `sample-upload.csv` | id, name, value, created_at | Data-first flow (JOURNEY-DPO-001). Schema inference, DQ checks. |
| `sample-upload.json` | id, name, value, created_at | Same as CSV but JSON format. |
| `sample-with-email.csv` | id, email, created_at | Use with `odcs-with-quality-rules.json` (email validation). |

---

## How to Use

### Data-First Flow (JOURNEY-DPO-001)

1. Create asset (draft).
2. Upload `sample-upload.csv` or `sample-upload.json`.
3. Create dataset from uploaded file.
4. **Expected**: Schema inferred (id: string, name: string, value: number, created_at: timestamp).
5. Run compliance and DQ checks.
6. Create contract (use `odcs-minimal.json` with matching schema).
7. Activate asset.

### Schema Matching

- `sample-upload.csv` columns map to `odcs-minimal.json` schema fields (id, name, value).
- `sample-with-email.csv` maps to `odcs-with-quality-rules.json` (id, email, created_at).
