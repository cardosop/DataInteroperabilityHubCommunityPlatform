# Visual Verification: UX Components (Phase 29.66.18.3)

**Reference**: tasks.md 29.66.18.3  
**Scope**: Asset upload, dataset edit, UUID copy, breadcrumbs, toast, ConfirmDialog

---

## Checklist

| # | Item | Steps | Expected | Pass |
|---|------|-------|----------|------|
| 1 | **Asset upload** | Assets → Create Asset → Upload File → select CSV | File uploads; dataset created or file in list | ☐ |
| 2 | **Dataset edit** | Datasets → select dataset → Edit / Link to Asset → paste asset UUID → Save | Success toast; dataset shows linked asset | ☐ |
| 3 | **UUID copy** | Open any detail page with UUID (Asset, Dataset, Contract) → click copy | UUID copied to clipboard; feedback | ☐ |
| 4 | **Breadcrumbs** | Navigate to detail page (e.g. Asset detail) | Breadcrumbs visible (Home / Assets / Asset name) | ☐ |
| 5 | **Toast** | Trigger success (e.g. save dataset) or error (invalid UUID) | Toast appears; auto-dismisses or closable | ☐ |
| 6 | **ConfirmDialog** | Trigger delete (e.g. File list → Delete) | Dialog opens; Cancel closes; Confirm performs action | ☐ |

---

## Feature flags (optional)

- `VITE_FEATURE_TOAST_ENABLED=false` → Toast disabled
- `VITE_FEATURE_BREADCRUMBS_ENABLED=false` → Breadcrumbs hidden
- `VITE_FEATURE_RESOURCE_PICKERS_ENABLED=false` → Pickers render text inputs for manual UUID entry

---

## Run commands

- Unit: `cd frontend && npm run test:run -- src/shared/components/ src/shared/config src/shared/utils/__tests__/validation.test.ts`
- E2E UX: `./scripts/run_frontend_ux_tests.sh`
