# Phase 260 External Pen-Test Scope — Datasets & Files Surface

> **Audience**: External pen-test vendor, P2 release manager, Platform security.  
> **Phase**: 260.2.I.3 — companion to [threat-model-datasets-files.md](threat-model-datasets-files.md).  
> **Last updated**: 2026-05-06.  
> **Status**: Contractual scope for external testing before **P2 prod-GA** (see § **P2 exit criterion**).

The vendor SHALL execute every test case below (or document a formally approved deferral with compensating controls) and deliver a written report with reproduction steps.

---

## P2 exit criterion

Per Phase **260.2.I.4**, **the external pen test is a P2 prod-GA exit criterion**. P2 prod-GA cannot ship until:

1. Every case in this document has been executed or explicitly deferred with platform-security approval.  
2. **CRITICAL** and **HIGH** findings are remediated or have written risk acceptance + dated ticket.  
3. Final report filed under `docs/security/pen-test-reports/p2-260-<vendor>-<YYYY-MM-DD>.md` (path confirmed by release manager).  
4. Platform security + P2 release manager sign off on closure (align with threat-model § Sign-off).

Merge hygiene: CI structural test `hub/tests/test_security_docs_phase_260_2_i.py::TestPenTestScopeStructure::test_pen_test_scope_marks_p2_exit_criterion` asserts this section remains present.

---

## Surface 1 — Federated-import-disabled file operations

**Scope**: All **File** and **Dataset** REST operations for tenants with **`federated_import_enabled=False`** (default). Confirm no auxiliary code path grants federated-import capabilities or leaks federated-only fields through these endpoints.

**The vendor SHALL execute**:

1. **Flag-off bypass** — With `federated_import_enabled=False`, attempt any documented or guessed federated-only parameter on `POST /api/v1/files/init/`, `POST /api/v1/datasets/`, or asset-linked flows that might create `File` rows without normal upload. Confirm rejection at gate.  
2. **Cross-feature confusion** — Call File endpoints with bodies or query params resembling federated import (`source_metadata`, `marketplace_type`, etc.). Confirm ignored or 400, never silent acceptance.  
3. **Capability header leak** — Responses must not expose internal “federated capable” hints that differ by tenant when flag is off.  
4. **OpenAPI drift** — Snapshot `GET /api/v1/openapi.json` and confirm federated paths are not advertised as enabled for the test tenant profile.

---

## Surface 2 — IDOR across all File endpoints

**Endpoints** (non-exhaustive; derive from `FileViewSet`):

* `GET/POST /api/v1/files/`  
* `GET/PATCH/DELETE /api/v1/files/{id}/`  
* `POST /api/v1/files/init/`  
* `POST /api/v1/files/{id}/complete/`  
* `GET /api/v1/files/{id}/download/`  
* Chunk init / upload URLs under `/api/v1/files/{id}/chunks/…`

**The vendor SHALL execute**:

1. **Cross-tenant retrieve** — Without entitlement: expect **404**, never 403 with existence proof; body must not contain victim file `name`, `storage_path`, or `content_sha256`.  
2. **Cross-tenant download** — Same as retrieve; confirm presign never issued.  
3. **Cross-tenant delete / complete** — Confirm 404 or 403 without mutation.  
4. **Malformed UUID** — Path segment non-UUID → **400** (Phase 260.2.A).  
5. **Entitled consumer** — With active `Entitlement`, retrieve returns **200**; audit `FILE_METADATA_VIEWED` (if sampled) includes `consumer_tenant_id`.  
6. **List enumeration** — Paginate `GET /files/`; confirm no other-tenant rows.  
7. **UUID timing** — Compare response-time distributions for non-existent vs other-tenant ids (should not materially leak).  
8. **Cache headers** — `ETag` / `Cache-Control` must not encode cross-tenant metadata.

Pinned by automated suite: `hub/apps/files/tests/security/test_idor.py` + `test_file_metadata_view_audit.py`.

---

## Surface 3 — Magic-byte / MIME bypass (`complete_upload`)

**The vendor SHALL execute**:

1. **Declared-safe / actual-malicious** — Upload benign-declared type with executable or archive magic; expect rejection and `FILE_FORMAT_MISMATCH_REJECTED` audit when gate is active.  
2. **Double extension** — `report.pdf.exe` style names (path + completion).  
3. **Sniff order** — Attempt to bypass by declaring octet-stream while serving polyglot bytes.  
4. **Partial upload** — Complete with wrong declared size vs actual (if applicable to implementation).

---

## Surface 4 — Multipart abandonment attack

**The vendor SHALL execute**:

1. **Init multipart** — Start upload; never call complete; verify object lifecycle (aborted or deleted per policy).  
2. **Stale part URLs** — Reuse expired presigned part URL; expect failure.  
3. **Race** — Two clients same `upload_id`; document behaviour (one wins; no cross-tenant merge).  
4. **Storage cost** — Confirm cleanup job (`abandoned_multipart_cleanup` / cron) removes orphan multipart metadata within documented SLA.

---

## Surface 5 — Rate-limit bypass

Coverage includes **ratelimit-bypass** attempts (forged `X-Forwarded-For`, rotating egress, distributed floods, ignoring `Retry-After`, and any middleware vs DRF throttle gap).

**The vendor SHALL execute**:

1. **`POST /files/init/`** — Exceed per-user **60/min** and per-tenant **600/min** (DRF throttles 260.2.E); expect **429** + `Retry-After` + standardized error envelope.  
2. **IP rotation** — Same user token, varying `X-Forwarded-For` (if infra allows); user bucket must still apply.  
3. **Many users one tenant** — Confirm tenant bucket caps aggregate traffic.  
4. **Platform middleware** — With `RATE_LIMIT_ENABLED=True` in staging, confirm middleware + DRF limits don’t leave an unbounded hole (document effective worst case).  
5. **Throttle header parsing** — Burst clients that ignore `Retry-After`; service must remain stable (no crash).

---

## Reporting format

1. Executive summary + severity table (CRITICAL/HIGH/MEDIUM/LOW/INFO).  
2. Per-finding: steps, evidence, affected endpoint, CWE if applicable, remediation.  
3. Residual risk register for deferred items.
