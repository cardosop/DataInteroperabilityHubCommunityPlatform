# UC-FILE-UPLOAD: Upload File

**Use Case ID**: UC-FILE-UPLOAD  
**Title**: Upload File  
**Persona**: Data Product Owner, Data Engineer  
**Priority**: High  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-file-upload-upload-file)

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. Have a test file (CSV, JSON, or Parquet). Use `05-SUPPORT-MATERIAL/data/sample-upload.csv` if available.

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** or **Data Engineer**
- [ ] Test file ready (CSV, JSON, Parquet)

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to **Files** | Files list page loads | ☐ |
| 2 | Click **Upload File** | Upload modal opens with dropzone | ☐ |
| 3 | Select file or drop into dropzone | File accepted | ☐ |
| 4 | Wait for upload | Success message; file appears in list | ☐ |
| 5 | Verify file in list | File name, size, format visible | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Invalid format | Upload unsupported file type | Validation error | ☐ |
| A2: File too large | Upload oversized file (if limit exists) | Error message | ☐ |

---

## Traceability

- **Journey**: [JOURNEY-DE-015](../03-USER-JOURNEYS/de/JOURNEY-DE-015.md)
- **E2E Spec**: `frontend/e2e/use-cases/ux/files-upload.spec.ts`
- **API**: `POST /api/v1/files/init/`, `POST /api/v1/files/{id}/complete/` (multipart upload flow)
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md)
