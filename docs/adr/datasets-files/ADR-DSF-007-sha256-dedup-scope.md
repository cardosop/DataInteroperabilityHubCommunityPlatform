# ADR-DSF-007 — SHA‑256 uniqueness & tenant isolation scope

**Status**: Accepted (Phase 260.0 / pass-3 B3-3)

## Context

Several services persist `content_sha256` alongside file rows (`hub/apps/files/services.py`). Reviewers flagged potential cross-tenant deduplication exploits if two tenants could coerce identical ciphertext into sharing storage objects.

## Decision

1. **No cross-tenant object-level dedup.** Every presigned PUT path includes immutable `tenant_id` + `file_id`, so collisions only aid cache-friendly verification within the SAME tenant lineage.
2. **Integrity signalling only.** Matching SHA-256 between tenants MAY raise observability alarms (possible data exfil) but MUST NOT silently link rows.
3. **Detection surfaces** reference `DATASET_FILE_PURGED`/`FILE_DOWNLOAD_CHECKSUM_MISMATCH` codes documented in Phase 260 error catalogue additions.

## Consequences

+ Preserves contractual isolation demanded by SOC2/GDPR DPA Annex.
− Additional storage duplication vs hypothetical global dedupe (explicitly declined).

