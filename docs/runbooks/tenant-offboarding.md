# Tenant offboarding — Files & Datasets plane (Phase 260.0.10)

## Goals

Remove tenant access while preserving legal retention + audit evidence.

## Steps

1. **Freeze ingress** — disable `files` + `datasets` capabilities / kill switches per contract.
2. **Export package** — Presign read-only manifest for customer success (metadata + optional bucket prefix copy).
3. **Purge pipeline** — enqueue soft-delete → distributed-lock guarded hard delete after grace (`file-retention` runbook).
4. **DSAR alignment** — confirm erasure tickets closed or legal hold extended.
5. **Observability** — watch `DATASET_FILE_PURGED` + `FILES_DISABLED` codes in Support dashboards.

## SLA touchpoints

Support + Legal + DPO must sign the closure checklist before Terraform removes tenant-scoped IAM roles.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
