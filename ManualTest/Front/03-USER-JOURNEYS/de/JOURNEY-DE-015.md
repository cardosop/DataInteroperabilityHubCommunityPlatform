# JOURNEY-DE-015: Upload File via Files Page

**Journey ID**: JOURNEY-DE-015  
**Title**: Upload File via Files Page  
**Persona**: Data Engineer, Data Product Owner  
**Priority**: High  
**Estimated Duration**: 3 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-015-upload-file-via-files-page-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** or **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] Test file ready: `05-SUPPORT-MATERIAL/data/sample-upload.csv` or similar (CSV, JSON, Parquet)

---

## What You Will Do

Upload a data file via the Files page. File can later be used to create a dataset.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to Files | Go to **Files** (sidebar). | Files list page loads | ☐ |
| 2 | Open upload | Click **Upload File**. | Upload modal with dropzone | ☐ |
| 3 | Select file | Choose file or drop into dropzone. | File accepted | ☐ |
| 4 | Wait for upload | Wait for upload to complete. | Success; file in list | ☐ |
| 5 | Verify | Check file in list. | Name, size, format visible | ☐ |

---

## Success Criteria

- File uploaded successfully
- File appears in Files list
- File available for dataset creation (Datasets → Create Dataset → Select File)

---

## Traceability

- **Use Case**: [UC-FILE-UPLOAD](../../02-USE-CASES/UC-FILE-UPLOAD.md)
- **E2E Spec**: `frontend/e2e/use-cases/ux/files-upload.spec.ts`
- **API**: `POST /api/v1/files/init/`, `POST /api/v1/files/{id}/complete/` (multipart upload flow)
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
